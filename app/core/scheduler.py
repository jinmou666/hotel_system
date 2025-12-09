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

    def pause_simulation(self):
        self.physics_paused = True
        print(">>> [系统] 物理引擎已暂停。")

    def resume_simulation(self):
        self.simulation_start_time = datetime.now()
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

                # === 核心逻辑：会话管理 ===
                # 如果之前是关机状态，或者没有会话ID，说明是新的一次“入住/使用”
                if room.power_status == 'OFF' or not room.active_session_id:
                    room.active_session_id = str(uuid.uuid4())
                    # print(f">>> [Session] Room {room_id} Start Session: {room.active_session_id}")

                room.target_temp = float(target_temp)
                room.fan_speed = fan_speed
                room.power_status = 'ON'
                room.fee_rate = self._get_fee_rate(fan_speed)

                if room.room_id in self.temp_hysteresis_set:
                    self.temp_hysteresis_set.remove(room.room_id)

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
                # === 核心逻辑：会话结束 ===
                # print(f">>> [Session] Room {room_id} End Session: {room.active_session_id}")
                room.active_session_id = None  # 清空会话ID

                if room.room_id in self.temp_hysteresis_set:
                    self.temp_hysteresis_set.remove(room.room_id)

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

    # ... (调度逻辑、物理引擎逻辑 与上一版完全一致，省略以节省篇幅) ...
    # 唯一需要修改的是 _start_new_record，需要写入 session_id

    def _start_new_record(self, room):
        try:
            new_record = DetailRecord(
                room_id=room.room_id,
                session_id=room.active_session_id,  # 写入当前会话ID
                start_time=datetime.now(),
                fan_speed=room.fan_speed,
                fee_rate=room.fee_rate,
                fee=0.0,
                duration=0.0
            )
            db.session.add(new_record)
            db.session.commit()
        except:
            db.session.rollback()

    # ... (以下所有方法与之前版本完全一致，请确保不要覆盖掉上面的 request_power/stop_power/_start_new_record) ...

    def _needs_service(self, room):
        curr = float(room.current_temp)
        target = float(room.target_temp)
        if room.room_id in self.temp_hysteresis_set:
            if self.current_mode == 'COOL':
                if curr >= (target + 1.0):
                    self.temp_hysteresis_set.remove(room.room_id)
                    print(f">>> [重启] R{room.room_id} 回温满1度")
                    return True
                return False
            else:
                if curr <= (target - 1.0):
                    self.temp_hysteresis_set.remove(room.room_id)
                    print(f">>> [重启] R{room.room_id} 回温满1度")
                    return True
                return False
        if self.current_mode == 'COOL':
            return curr > (target + 0.001)
        else:
            return curr < (target - 0.001)

    def _handle_scheduling(self, room_id):
        room = Room.query.get(room_id)
        if not room: return
        old_svc_time = self.service_start_times.get(room_id)
        self._remove_from_service(room_id)
        self._remove_from_wait(room_id)
        if not self._needs_service(room): return
        if len(self.service_queue) < SystemConstants.MAX_SERVICE:
            self._add_to_service(room, original_start_time=old_svc_time)
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
        if req_prio > lowest_prio_val:
            lowest_rooms.sort(key=lambda x: x[2], reverse=True)
            target_to_kick = lowest_rooms[0][0]
            if target_to_kick:
                print(f">>> [抢占] R{room_id} 抢占 R{target_to_kick}")
                r_kicked = Room.query.get(target_to_kick)
                self._move_to_wait(r_kicked)
                self._add_to_service(room, original_start_time=old_svc_time)
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
            self._move_to_service(best_room)

    def _simulation_loop(self):
        step_real_sec = 0.2
        while self.is_running:
            if self.physics_paused:
                time.sleep(1)
                self.last_tick_time = datetime.now()
                continue
            with db.app.app_context():
                try:
                    now = datetime.now()
                    actual_delta = (now - self.last_tick_time).total_seconds()
                    self.last_tick_time = now
                    if actual_delta > 1.0: actual_delta = 1.0
                    if actual_delta > 0.01: self._tick(actual_delta)
                except Exception as e:
                    print(f"Physics Error: {e}")
                finally:
                    db.session.remove()
            time.sleep(step_real_sec)

    def _tick(self, step_real_sec):
        with self._lock:
            self._tick_time_slice_check()
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
            step = (SystemConstants.RECOVER_RATE / 60.0) * delta_sys_sec
            if self.current_mode == 'COOL':
                new_temp = current_temp + step
                if new_temp > initial_temp: new_temp = initial_temp
            else:
                new_temp = current_temp - step
                if new_temp < initial_temp: new_temp = initial_temp
        room.current_temp = round(new_temp, 4)

        if is_serving:
            reached = False
            if self.current_mode == 'COOL' and room.current_temp <= (target_temp + 0.001): reached = True
            if self.current_mode == 'HEAT' and room.current_temp >= (target_temp - 0.001): reached = True
            if reached:
                self.temp_hysteresis_set.add(room.room_id)
                with self._lock:
                    self._remove_from_service(room.room_id)
                    self._schedule_next()

        if room.power_status == 'ON' and room.room_id not in self.service_queue and \
                room.room_id not in self.wait_queue and room.room_id in self.temp_hysteresis_set:
            if self._needs_service(room):
                with self._lock: self._handle_scheduling(room.room_id)

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

    def _add_to_service(self, room, original_start_time=None):
        if room.room_id not in self.service_queue:
            self.service_queue.append(room.room_id)
            if original_start_time:
                self.service_start_times[room.room_id] = original_start_time
            else:
                self.service_start_times[room.room_id] = datetime.now()
            with db.app.app_context():
                self._start_new_record(room)

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
                    room.active_session_id = None  # 重置
            db.session.commit()
        return True