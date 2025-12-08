from app import db
from app.models import Room, DetailRecord, Invoice
from config import SystemConstants
from datetime import datetime, timedelta
import threading
import time


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
                    cls._instance.current_mode = 'COOL'
                    cls._instance.is_running = False
                    cls._instance.physics_paused = True
                    cls._instance.simulation_start_time = datetime.now()
                    # 记录上一次物理计算的时间点
                    cls._instance.last_tick_time = datetime.now()

                    cls._instance.start_simulation()
        return cls._instance

    def start_simulation(self):
        if not self.is_running:
            self.is_running = True
            t = threading.Thread(target=self._simulation_loop, daemon=True)
            t.start()

    def pause_simulation(self):
        self.physics_paused = True
        print(">>> [系统] 物理引擎已暂停。")

    def resume_simulation(self):
        self.simulation_start_time = datetime.now()
        # 恢复时重置 tick 时间，防止把暂停的时间算进去
        self.last_tick_time = datetime.now()
        self.physics_paused = False
        print(">>> [系统] 物理引擎启动！")

    def get_scheduling_status(self, room_id):
        if self.physics_paused and room_id in self.service_queue: return 'READY'
        if room_id in self.service_queue:
            return 'RUNNING'
        elif room_id in self.wait_queue:
            return 'WAITING'
        else:
            return 'IDLE'

    # ================= 接口方法 =================

    def request_power(self, room_id, fan_speed, target_temp):
        with db.app.app_context():
            try:
                room = Room.query.get(room_id)
                if not room: return False
                self._close_current_record(room)
                room.target_temp = float(target_temp)
                room.fan_speed = fan_speed
                room.power_status = 'ON'
                room.fee_rate = self._get_fee_rate(fan_speed)
                db.session.commit()

                with self._lock:
                    self._handle_scheduling(room.room_id)
                return True
            except:
                db.session.rollback()
                return False
            finally:
                db.session.remove()

    def stop_power(self, room_id):
        with db.app.app_context():
            try:
                room = Room.query.get(room_id)
                if not room: return False
                self._close_current_record(room)
                room.power_status = 'OFF'
                db.session.commit()

                with self._lock:
                    self._remove_from_service(room_id)
                    self._remove_from_wait(room_id)
                    self._schedule_next()
                return True
            except:
                db.session.rollback()
                return False
            finally:
                db.session.remove()

    # ================= 核心调度算法 =================

    def _needs_service(self, room):
        curr = float(room.current_temp)
        target = float(room.target_temp)
        # 只要没达到目标，或者处于回温重启状态，就需要服务
        # 使用宽松判断，防止浮点数在目标值附近抖动导致频繁启停
        if self.current_mode == 'COOL':
            return curr > target
        else:
            return curr < target

    def _handle_scheduling(self, room_id):
        room = Room.query.get(room_id)
        if not room: return

        self._remove_from_service(room_id)
        self._remove_from_wait(room_id)

        # 检查是否需要服务（温控判断）
        if not self._needs_service(room):
            return

        if len(self.service_queue) < SystemConstants.MAX_SERVICE:
            self._add_to_service(room)
            return

        req_prio = self._get_priority(room.fan_speed)
        lowest_prio_val = 999
        lowest_rooms = []

        for rid in self.service_queue:
            r_srv = Room.query.get(rid)
            p = self._get_priority(r_srv.fan_speed)
            d = self._get_service_duration(rid)

            if p < lowest_prio_val:
                lowest_prio_val = p
                lowest_rooms = [(rid, p, d)]
            elif p == lowest_prio_val:
                lowest_rooms.append((rid, p, d))

        print(f">>> [调度] R{room_id}(P{req_prio}) 申请，当前最低 P{lowest_prio_val}")

        # 抢占逻辑：严格大于
        if req_prio > lowest_prio_val:
            lowest_rooms.sort(key=lambda x: x[2], reverse=True)
            target_to_kick = lowest_rooms[0][0]

            if target_to_kick:
                print(f">>> [抢占] R{room_id} 抢占 R{target_to_kick}")
                r_kicked = Room.query.get(target_to_kick)
                self._move_to_wait(r_kicked)
                self._add_to_service(room)
                return

        self._add_to_wait(room)

    def _schedule_next(self):
        if len(self.wait_queue) == 0: return
        if len(self.service_queue) >= SystemConstants.MAX_SERVICE: return

        candidates = []
        for rid in self.wait_queue:
            r = Room.query.get(rid)
            if self._needs_service(r):
                p = self._get_priority(r.fan_speed)
                t = self.wait_start_times.get(rid, datetime.now())
                candidates.append({'rid': rid, 'prio': p, 'time': t, 'room': r})
            else:
                self.wait_queue.remove(rid)

        candidates.sort(key=lambda x: (-x['prio'], x['time']))
        if candidates:
            best_room = candidates[0]['room']
            print(f">>> [补位] R{best_room.room_id} 上位")
            self._move_to_service(best_room)

    # ================= 物理引擎 (动态时间补偿版) =================

    def _simulation_loop(self):
        while self.is_running:
            if self.physics_paused:
                time.sleep(1)
                self.last_tick_time = datetime.now()  # 暂停时持续更新时间，防止恢复瞬间跳变
                continue

            with db.app.app_context():
                try:
                    # 计算真实的物理时间差 (Wall Clock Sync)
                    now = datetime.now()
                    step_real_sec = (now - self.last_tick_time).total_seconds()
                    self.last_tick_time = now

                    # 只有当时间差合理时才计算 (防止休眠过久导致突变)
                    if 0 < step_real_sec < 5.0:
                        self._tick(step_real_sec)

                except Exception as e:
                    print(f"Physics Error: {e}")
                finally:
                    db.session.remove()

            time.sleep(1)

    def _tick(self, step_real_sec):
        # 1. 检查时间片
        with self._lock:
            self._tick_time_slice_check()

        # 2. 动态计算系统时间增量
        # 无论 Python 运行慢了还是快了，我们都按真实流逝的时间来计费
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

    def _update_room_physics(self, room, delta_sys_sec):
        is_serving = (room.room_id in self.service_queue) and (room.power_status == 'ON')
        current_temp = float(room.current_temp)
        target_temp = float(room.target_temp)

        # 核心修正：配置键值兼容处理 (int/str)
        try:
            # 尝试用 int 查 (ac_simulation.py 风格)
            key = int(room.room_id)
            if self.current_mode == 'COOL':
                initial_temp = SystemConstants.COOL_MODE_DEFAULTS['initial_temps'][key]
            else:
                initial_temp = SystemConstants.HEAT_MODE_DEFAULTS['initial_temps'][key]
        except KeyError:
            # 兜底：尝试用 str 查
            key = str(room.room_id)
            if self.current_mode == 'COOL':
                initial_temp = SystemConstants.COOL_MODE_DEFAULTS['initial_temps'].get(key, 30.0)
            else:
                initial_temp = SystemConstants.HEAT_MODE_DEFAULTS['initial_temps'].get(key, 10.0)

        if is_serving:
            rate_per_min = self._get_temp_change_rate(room.fan_speed)
            # 变化量 = (速度 / 60) * 时间
            change = (rate_per_min / 60.0) * delta_sys_sec

            if self.current_mode == 'COOL':
                new_temp = current_temp - change
            else:
                new_temp = current_temp + change

            fee_per_min = self._get_fee_rate(room.fan_speed)
            cost = (fee_per_min / 60.0) * delta_sys_sec

            room.current_fee = float(room.current_fee) + cost
            room.total_fee = float(room.total_fee) + cost

            record = DetailRecord.query.filter_by(room_id=room.room_id, end_time=None).first()
            if record:
                record.fee = float(record.fee) + cost
                record.duration = int(record.duration) + int(delta_sys_sec)
        else:
            # 回温
            rate_recover = SystemConstants.RECOVER_RATE
            step = (rate_recover / 60.0) * delta_sys_sec

            if self.current_mode == 'COOL':
                # 制冷回温：升温
                new_temp = current_temp + step
                if new_temp > initial_temp: new_temp = initial_temp
            else:
                # 制热回温：降温
                new_temp = current_temp - step
                if new_temp < initial_temp: new_temp = initial_temp

        room.current_temp = round(new_temp, 4)

        # 自动温控达标
        if is_serving:
            reached = False
            if self.current_mode == 'COOL' and room.current_temp <= target_temp: reached = True
            if self.current_mode == 'HEAT' and room.current_temp >= target_temp: reached = True

            if reached:
                print(f">>> [温控] R{room.room_id} 达标，暂停服务")
                with self._lock:
                    self._remove_from_service(room.room_id)
                    self._schedule_next()

        # 回温重启逻辑
        if room.power_status == 'ON' and \
                room.room_id not in self.service_queue and \
                room.room_id not in self.wait_queue:

            should_restart = False
            # 宽松一点的判断 (0.99 而不是 1.0)，防止因为 0.999999 而没触发
            if self.current_mode == 'COOL' and room.current_temp >= (target_temp + 0.99): should_restart = True
            if self.current_mode == 'HEAT' and room.current_temp <= (target_temp - 0.99): should_restart = True

            if should_restart:
                print(f">>> [温控] R{room.room_id} 回温到位，重启服务")
                with self._lock:
                    self._handle_scheduling(room.room_id)

    # ... (辅助方法保持不变) ...
    def _start_new_record(self, room):
        try:
            new_record = DetailRecord(
                room_id=room.room_id, start_time=datetime.now(),
                fan_speed=room.fan_speed, fee_rate=room.fee_rate, fee=0.0, duration=0
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
                        r_target = Room.query.get(tid)
                        self._move_to_wait(r_target)
                        self._move_to_service(r_wait)

    def _add_to_service(self, room):
        if room.room_id not in self.service_queue:
            self.service_queue.append(room.room_id)
            self.service_start_times[room.room_id] = datetime.now()
            with db.app.app_context(): self._start_new_record(room)

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
        if fan == 'HIGH': return SystemConstants.FEE_RATE_HIGH
        if fan == 'LOW': return SystemConstants.FEE_RATE_LOW
        return SystemConstants.FEE_RATE_MID

    def _get_temp_change_rate(self, fan):
        if fan == 'HIGH': return SystemConstants.TEMP_XH_HIGH
        if fan == 'LOW': return SystemConstants.TEMP_XH_LOW
        return SystemConstants.TEMP_XH_MID

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
        self.physics_paused = True

        with db.app.app_context():
            db.session.query(DetailRecord).delete()
            db.session.query(Invoice).delete()
            rooms = Room.query.all()
            for room in rooms:
                # 兼容 int/str
                str_id = str(room.room_id)
                int_id = int(room.room_id)

                # 优先匹配 config 里的 key (可能是 int 也可能是 str)
                val = config['initial_temps'].get(int_id)
                if val is None:
                    val = config['initial_temps'].get(str_id)

                if val is not None:
                    room.current_temp = val
                    room.target_temp = config['default_target']
                    room.fan_speed = 'MEDIUM'
                    room.power_status = 'OFF'
                    room.current_fee = 0.0
                    room.total_fee = 0.0
                    room.status = 'AVAILABLE'
            db.session.commit()
        return True