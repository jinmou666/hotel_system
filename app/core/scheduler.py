from app import db
from app.models import Room, DetailRecord, Invoice
from config import SystemConstants
from datetime import datetime, timedelta
import threading
import time
import uuid


class Scheduler:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(Scheduler, cls).__new__(cls)
                    cls._instance.service_queue = []
                    cls._instance.wait_queue = []
                    cls._instance.service_start_times = {}
                    cls._instance.wait_start_times = {}
                    cls._instance.temp_hysteresis_set = set()

                    cls._instance.current_mode = 'COOL'
                    cls._instance.is_running = False
                    cls._instance.physics_paused = True
                    cls._instance.simulation_start_time = datetime.now()
                    cls._instance.last_tick_time = datetime.now()
                    cls._instance.start_simulation()
        return cls._instance

    def start_simulation(self):
        if not self.is_running:
            self.is_running = True
            t = threading.Thread(target=self._simulation_loop, daemon=True)
            t.start()

    # === 给前端调用的专用启动接口 ===
    def start_simulation_api(self):
        # 核心修复：点击“开始测试”的瞬间，重置所有时间基准
        # 确保第 0 分钟的指令记录的时间也是 0.00
        now = datetime.now()
        self.simulation_start_time = now
        self.last_tick_time = now
        self.physics_paused = False
        print(">>> [系统] 物理引擎启动！时间基准已重置。")

    def stop_simulation_api(self):
        self.physics_paused = True
        print(">>> [系统] 物理引擎已暂停。")

    def get_scheduling_status(self, room_id):
        if self.physics_paused and room_id in self.service_queue: return 'READY'
        if room_id in self.service_queue:
            return 'RUNNING'
        elif room_id in self.wait_queue:
            return 'WAITING'
        else:
            return 'IDLE'

    # ================= 接口方法 (强化健壮性) =================

    def request_power(self, room_id, fan_speed, target_temp):
        with db.app.app_context():
            try:
                room = Room.query.get(room_id)
                if not room: return False

                # 必须先关闭旧记录
                self._close_current_record(room)

                # 会话管理
                if room.power_status == 'OFF' or not room.active_session_id:
                    room.active_session_id = str(uuid.uuid4())

                room.target_temp = float(target_temp)
                room.fan_speed = fan_speed
                room.power_status = 'ON'
                room.fee_rate = self._get_fee_rate(fan_speed)

                if room.room_id in self.temp_hysteresis_set:
                    self.temp_hysteresis_set.remove(room.room_id)

                db.session.commit()

                with self._lock:
                    # 只有当温度未达标时，才申请调度；否则进入迟滞监控
                    if not self._needs_service(room):
                        self.temp_hysteresis_set.add(room.room_id)
                        # 确保不占用调度资源
                        self._remove_from_service(room_id)
                        self._remove_from_wait(room_id)
                    else:
                        self._handle_scheduling(room.room_id)

                return True
            except Exception as e:
                db.session.rollback()
                print(f"Request Error R{room_id}: {e}")
                return False
            finally:
                db.session.remove()

    def stop_power(self, room_id):
        # 内存操作优先，确保即使DB挂了，调度队列也是干净的
        with self._lock:
            self._remove_from_service(room_id)
            self._remove_from_wait(room_id)
            if room_id in self.temp_hysteresis_set:
                self.temp_hysteresis_set.remove(room_id)

            # 腾出位置后立刻补位
            self._schedule_next()

        with db.app.app_context():
            try:
                room = Room.query.get(room_id)
                if room:
                    self._close_current_record(room)
                    room.power_status = 'OFF'
                    room.active_session_id = None
                    db.session.commit()
                return True
            except Exception as e:
                db.session.rollback()
                print(f"Stop Error R{room_id}: {e}")
                return False
            finally:
                db.session.remove()

    # ================= 调度逻辑 (保持一致性) =================

    def _needs_service(self, room):
        curr = float(room.current_temp)
        target = float(room.target_temp)

        # 迟滞状态检查：严格 1.0 度回温
        if room.room_id in self.temp_hysteresis_set:
            if self.current_mode == 'COOL':
                if curr >= (target + 1.0):
                    self.temp_hysteresis_set.remove(room.room_id)
                    print(f">>> [重启] R{room.room_id} 回温满1度，重入队列")
                    return True
                return False
            else:
                if curr <= (target - 1.0):
                    self.temp_hysteresis_set.remove(room.room_id)
                    print(f">>> [重启] R{room.room_id} 回温满1度，重入队列")
                    return True
                return False

        # 正常状态
        if self.current_mode == 'COOL':
            return curr > (target + 0.001)
        else:
            return curr < (target - 0.001)

    def _handle_scheduling(self, room_id):
        room = Room.query.get(room_id)
        if not room: return

        old_svc_time = self.service_start_times.get(room_id)

        # 先清理旧状态
        self._remove_from_service(room_id)
        self._remove_from_wait(room_id)

        if not self._needs_service(room): return

        # 尝试进入服务队列
        if len(self.service_queue) < SystemConstants.MAX_SERVICE:
            self._add_to_service(room, original_start_time=old_svc_time)
            return

        # 抢占逻辑
        req_prio = self._get_priority(room.fan_speed)
        lowest_prio_val = 999
        lowest_rooms = []

        for rid in self.service_queue:
            r_srv = Room.query.get(rid)
            if not r_srv: continue
            p = self._get_priority(r_srv.fan_speed)
            d = self._get_service_duration(rid)
            if p < lowest_prio_val:
                lowest_prio_val = p
                lowest_rooms = [(rid, p, d)]
            elif p == lowest_prio_val:
                lowest_rooms.append((rid, p, d))

        if req_prio > lowest_prio_val:
            # 踢掉服务时间最长的
            lowest_rooms.sort(key=lambda x: x[2], reverse=True)
            target_to_kick = lowest_rooms[0][0]
            if target_to_kick:
                print(f">>> [抢占] R{room_id} 抢占 R{target_to_kick}")
                r_kicked = Room.query.get(target_to_kick)
                self._move_to_wait(r_kicked)
                self._add_to_service(room, original_start_time=old_svc_time)
                return

        # 没抢过，进等待
        self._add_to_wait(room)

    def _schedule_next(self):
        if len(self.wait_queue) == 0: return
        if len(self.service_queue) >= SystemConstants.MAX_SERVICE: return

        candidates = []
        # 必须重新获取对象判断是否真的需要服务
        with db.app.app_context():
            # 复制一份 wait_queue 避免遍历时修改
            for rid in list(self.wait_queue):
                r = Room.query.get(rid)
                if r and self._needs_service(r):
                    p = self._get_priority(r.fan_speed)
                    t = self.wait_start_times.get(rid, datetime.now())
                    candidates.append({'rid': rid, 'prio': p, 'time': t, 'room': r})
                else:
                    # 不需要服务了（可能回温期间被关机了或逻辑移除）
                    self.wait_queue.remove(rid)

        # 优先级高优先 > 等待时间长优先
        candidates.sort(key=lambda x: (-x['prio'], x['time']))

        if candidates:
            best_room = candidates[0]['room']
            print(f">>> [补位] R{best_room.room_id} 上位")
            self._move_to_service(best_room)

    # ================= 物理引擎 =================

    def _simulation_loop(self):
        step_real_sec = 0.2
        while self.is_running:
            if self.physics_paused:
                time.sleep(1)
                self.last_tick_time = datetime.now()
                continue

            # 使用独立上下文，并在 finally 中移除，防止连接泄露
            with db.app.app_context():
                try:
                    now = datetime.now()
                    actual_delta = (now - self.last_tick_time).total_seconds()
                    self.last_tick_time = now

                    if actual_delta > 1.0: actual_delta = 1.0  # 钳位防止跳变
                    if actual_delta > 0.01: self._tick(actual_delta)
                except Exception as e:
                    # print(f"Physics Error: {e}")
                    pass
                finally:
                    db.session.remove()
            time.sleep(step_real_sec)

    def _tick(self, step_real_sec):
        with self._lock:
            self._tick_time_slice_check()
            self._check_dynamic_preemption()

        delta_sys_sec = step_real_sec * SystemConstants.TIME_KX

        room_ids = []
        with db.app.app_context():
            room_ids = [r.room_id for r in Room.query.all()]

        for rid in room_ids:
            with db.app.app_context():
                try:
                    room = Room.query.get(rid)
                    if room:
                        self._update_room_physics(room, delta_sys_sec)
                        db.session.commit()
                except:
                    db.session.rollback()

    def _check_dynamic_preemption(self):
        if not self.wait_queue: return

        # 快速检查，不进行复杂DB操作
        with db.app.app_context():
            min_serv_prio = 999
            min_serv_rid = None
            max_serv_duration = -1

            for rid in self.service_queue:
                r = Room.query.get(rid)
                p = self._get_priority(r.fan_speed)
                d = self._get_service_duration(rid)
                if p < min_serv_prio:
                    min_serv_prio = p
                    min_serv_rid = rid
                    max_serv_duration = d
                elif p == min_serv_prio:
                    if d > max_serv_duration:
                        max_serv_duration = d
                        min_serv_rid = rid

            max_wait_prio = -1
            max_wait_rid = None
            for rid in self.wait_queue:
                r = Room.query.get(rid)
                if self._needs_service(r):
                    p = self._get_priority(r.fan_speed)
                    if p > max_wait_prio:
                        max_wait_prio = p
                        max_wait_rid = rid

            if max_wait_rid and min_serv_rid:
                if max_wait_prio > min_serv_prio:
                    print(f">>> [动态抢占] R{max_wait_rid} 抢占 R{min_serv_rid}")
                    r_wait = Room.query.get(max_wait_rid)
                    r_serv = Room.query.get(min_serv_rid)
                    self._move_to_wait(r_serv)
                    self._move_to_service(r_wait)

    def _update_room_physics(self, room, delta_sys_sec):
        is_serving = (room.room_id in self.service_queue) and (room.power_status == 'ON')
        current_temp = float(room.current_temp)
        target_temp = float(room.target_temp)

        try:
            key = int(room.room_id)
            if self.current_mode == 'COOL':
                initial_temp = SystemConstants.COOL_MODE_DEFAULTS['initial_temps'][key]
            else:
                initial_temp = SystemConstants.HEAT_MODE_DEFAULTS['initial_temps'][key]
        except:
            initial_temp = 25.0

        if is_serving:
            rate = self._get_temp_change_rate(room.fan_speed)
            temp_delta = (rate / 60.0) * delta_sys_sec
            effective_time_sec = delta_sys_sec

            if self.current_mode == 'COOL':
                if (current_temp - temp_delta) < target_temp:
                    needed = current_temp - target_temp
                    if needed < 0: needed = 0
                    if rate > 0: effective_time_sec = (needed / (rate / 60.0))
                    new_temp = target_temp
                else:
                    new_temp = current_temp - temp_delta
            else:
                if (current_temp + temp_delta) > target_temp:
                    needed = target_temp - current_temp
                    if needed < 0: needed = 0
                    if rate > 0: effective_time_sec = (needed / (rate / 60.0))
                    new_temp = target_temp
                else:
                    new_temp = current_temp + temp_delta

            fee_rate = self._get_fee_rate(room.fan_speed)
            cost = (fee_rate / 60.0) * effective_time_sec

            room.current_fee = float(room.current_fee) + cost
            room.total_fee = float(room.total_fee) + cost

            record = DetailRecord.query.filter_by(room_id=room.room_id, end_time=None).first()
            if record:
                record.fee = float(record.fee) + cost
                record.duration = float(record.duration) + effective_time_sec
        else:
            # 回温模式
            step = (SystemConstants.RECOVER_RATE / 60.0) * delta_sys_sec
            if self.current_mode == 'COOL':
                new_temp = current_temp + step
                if new_temp > initial_temp: new_temp = initial_temp
            else:
                new_temp = current_temp - step
                if new_temp < initial_temp: new_temp = initial_temp
        room.current_temp = round(new_temp, 4)

        # 自动温控达标
        if is_serving:
            reached = False
            if self.current_mode == 'COOL' and room.current_temp <= (target_temp + 0.001): reached = True
            if self.current_mode == 'HEAT' and room.current_temp >= (target_temp - 0.001): reached = True

            if reached:
                print(f">>> [温控] R{room.room_id} 达标，暂停服务")
                self.temp_hysteresis_set.add(room.room_id)
                with self._lock:
                    self._remove_from_service(room.room_id)
                    self._schedule_next()

        # 回温重启监测
        # 只要是开机状态，不管在哪，只要满足条件就尝试调度
        if room.power_status == 'ON' and room.room_id not in self.service_queue and \
                room.room_id not in self.wait_queue:

            if self._needs_service(room):
                with self._lock: self._handle_scheduling(room.room_id)

    # ... (辅助方法) ...
    def _add_to_service(self, room, original_start_time=None):
        if room.room_id not in self.service_queue:
            self.service_queue.append(room.room_id)
            if original_start_time:
                self.service_start_times[room.room_id] = original_start_time
            else:
                self.service_start_times[room.room_id] = datetime.now()
            with db.app.app_context():
                self._start_new_record(room)

    def _start_new_record(self, room):
        try:
            new_record = DetailRecord(
                room_id=room.room_id, session_id=room.active_session_id,
                start_time=datetime.now(), fan_speed=room.fan_speed,
                fee_rate=room.fee_rate, fee=0.0, duration=0.0
            )
            db.session.add(new_record)
            db.session.commit()
        except:
            db.session.rollback()

    def _close_current_record(self, room):
        try:
            record = DetailRecord.query.filter_by(room_id=room.room_id, end_time=None).first()
            if record:
                record.end_time = datetime.now()
                db.session.add(record)
                db.session.commit()
        except:
            db.session.rollback()

    def _tick_time_slice_check(self):
        now = datetime.now()
        ids = list(self.wait_queue)
        for wid in ids:
            st = self.wait_start_times.get(wid)
            if not st: continue
            dur = (now - st).total_seconds() * SystemConstants.TIME_KX
            if dur >= SystemConstants.TIME_SLICE:
                with db.app.app_context():
                    wroom = Room.query.get(wid)
                    if not wroom: continue
                    wprio = self._get_priority(wroom.fan_speed)
                    tid = None
                    max_d = -1
                    for sid in self.service_queue:
                        sroom = Room.query.get(sid)
                        if not sroom: continue
                        if self._get_priority(sroom.fan_speed) == wprio:
                            d = self._get_service_duration(sid)
                            if d > max_d: max_d = d; tid = sid
                    if tid:
                        print(f">>> [轮转] R{wid} 替换 R{tid}")
                        r_wait = Room.query.get(wid)
                        r_targ = Room.query.get(tid)
                        self._move_to_wait(r_targ)
                        self._move_to_service(r_wait)

    def _add_to_wait(self, room):
        if room.room_id not in self.wait_queue:
            self.wait_queue.append(room.room_id)
            self.wait_start_times[room.room_id] = datetime.now()

    def _remove_from_service(self, room_id):
        if room_id in self.service_queue:
            self.service_queue.remove(room_id)
            self.service_start_times.pop(room_id, None)
            with db.app.app_context():
                r = Room.query.get(room_id)
                self._close_current_record(r)

    def _remove_from_wait(self, room_id):
        if room_id in self.wait_queue:
            self.wait_queue.remove(room_id)
            self.wait_start_times.pop(room_id, None)

    def _move_to_wait(self, room):
        self._remove_from_service(room.room_id)
        self._add_to_wait(room)

    def _move_to_service(self, room):
        self._remove_from_wait(room.room_id)
        self._add_to_service(room)

    def _get_service_duration(self, room_id):
        start = self.service_start_times.get(room_id)
        if not start: return 0
        return (datetime.now() - start).total_seconds()

    def _get_priority(self, fan):
        if fan == 'HIGH': return 3
        if fan in ['MEDIUM', 'MID']: return 2
        return 1

    def _get_fee_rate(self, fan):
        if fan == 'HIGH': return 1.0
        if fan == 'LOW': return 1.0 / 3.0
        return 0.5

    def _get_temp_change_rate(self, fan):
        if fan == 'HIGH': return 1.0
        if fan == 'LOW': return 1.0 / 3.0
        return 0.5

    def reset_mode(self, mode):
        if mode == 'HEAT':
            self.current_mode = 'HEAT'
            config = SystemConstants.HEAT_MODE_DEFAULTS
        else:
            self.current_mode = 'COOL'
            config = SystemConstants.COOL_MODE_DEFAULTS
        self.service_queue.clear()
        self.wait_queue.clear()
        self.service_start_times.clear()
        self.wait_start_times.clear()
        self.temp_hysteresis_set.clear()
        self.physics_paused = True

        with db.app.app_context():
            db.session.query(DetailRecord).delete()
            db.session.query(Invoice).delete()
            rooms = Room.query.all()
            for room in rooms:
                str_id = str(room.room_id)
                int_id = int(room.room_id)
                val = config['initial_temps'].get(int_id)
                if val is None: val = config['initial_temps'].get(str_id)
                if val is not None:
                    room.current_temp = val
                    room.target_temp = config['default_target']
                    room.fan_speed = 'MEDIUM'
                    room.power_status = 'OFF'
                    room.current_fee = 0.0
                    room.total_fee = 0.0
                    room.status = 'AVAILABLE'
                    room.active_session_id = None
            db.session.commit()
        return True