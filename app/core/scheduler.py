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

    def start_simulation_api(self):
        now = datetime.now()
        self.simulation_start_time = now
        self.last_tick_time = now
        self.physics_paused = False
        print(">>> [System] Physics Engine Started. Timebase Reset.")

    def stop_simulation_api(self):
        self.physics_paused = True
        print(">>> [System] Physics Engine Paused.")

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

                self._close_current_record(room.room_id)

                if room.power_status == 'OFF' or not room.active_session_id:
                    room.active_session_id = str(uuid.uuid4())

                room.target_temp = float(target_temp)
                clean_fan = str(fan_speed).strip().upper()
                room.fan_speed = clean_fan
                room.power_status = 'ON'
                room.fee_rate = self._get_fee_rate(clean_fan)

                if room.room_id in self.temp_hysteresis_set:
                    self.temp_hysteresis_set.remove(room.room_id)

                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"DB Error R{room_id}: {e}")
                return False

        with self._lock:
            with db.app.app_context():
                room = Room.query.get(room_id)
                if not self._needs_service(room):
                    self.temp_hysteresis_set.add(room.room_id)
                    self._remove_from_service(room_id)
                    self._remove_from_wait(room_id)
                else:
                    self._handle_scheduling(room.room_id)
        return True

    def stop_power(self, room_id):
        with db.app.app_context():
            try:
                self._close_current_record(room_id)
                room = Room.query.get(room_id)
                if room:
                    room.power_status = 'OFF'
                    room.active_session_id = None
                    db.session.commit()
            except Exception as e:
                print(f"DB Error Stop R{room_id}: {e}")

        with self._lock:
            self._remove_from_service(room_id)
            self._remove_from_wait(room_id)
            if room_id in self.temp_hysteresis_set:
                self.temp_hysteresis_set.remove(room_id)
            self._schedule_next()
        return True

    # ================= 调度核心 =================

    def _handle_scheduling(self, room_id):
        room = Room.query.get(room_id)
        if not room: return

        old_svc_time = self.service_start_times.get(room_id)

        self._remove_from_service(room_id)
        self._remove_from_wait(room_id)

        if len(self.service_queue) < SystemConstants.MAX_SERVICE:
            self._add_to_service(room, original_start_time=old_svc_time)
            return

        req_prio = self._get_priority(room.fan_speed)
        lowest_prio_val = 999
        candidates = []

        for rid in self.service_queue:
            r_srv = Room.query.get(rid)
            if not r_srv: continue

            p = self._get_priority(r_srv.fan_speed)
            d = self._get_service_duration(rid)

            if p < lowest_prio_val:
                lowest_prio_val = p
                candidates = [(rid, p, d)]
            elif p == lowest_prio_val:
                candidates.append((rid, p, d))

        if req_prio > lowest_prio_val:
            candidates.sort(key=lambda x: x[2], reverse=True)
            target_to_kick = candidates[0][0]
            print(f">>> [Preempt] R{room_id} kicks R{target_to_kick}")
            r_kicked = Room.query.get(target_to_kick)
            self._move_to_wait(r_kicked)
            self._add_to_service(room, original_start_time=old_svc_time)
            return

        self._add_to_wait(room)

    def _schedule_next(self):
        if len(self.wait_queue) == 0: return
        if len(self.service_queue) >= SystemConstants.MAX_SERVICE: return

        with db.app.app_context():
            candidates = []
            for rid in list(self.wait_queue):
                r = Room.query.get(rid)
                if not r or not self._needs_service(r):
                    self.wait_queue.remove(rid)
                    continue
                p = self._get_priority(r.fan_speed)
                t = self.wait_start_times.get(rid, datetime.now())
                candidates.append({'rid': rid, 'prio': p, 'time': t, 'room': r})

            candidates.sort(key=lambda x: (-x['prio'], x['time']))

            if candidates:
                best = candidates[0]
                print(f">>> [Fill Slot] R{best['rid']} starts service")
                self._move_to_service(best['room'])

    def _check_dynamic_preemption(self):
        if not self.wait_queue: return

        with db.app.app_context():
            min_serv = None
            for rid in self.service_queue:
                r = Room.query.get(rid)
                if not r: continue
                p = self._get_priority(r.fan_speed)
                d = self._get_service_duration(rid)

                if min_serv is None or p < min_serv['prio']:
                    min_serv = {'rid': rid, 'prio': p, 'dur': d}
                elif p == min_serv['prio'] and d > min_serv['dur']:
                    min_serv = {'rid': rid, 'prio': p, 'dur': d}

            if not min_serv: return

            max_wait = None
            for rid in self.wait_queue:
                r = Room.query.get(rid)
                if not r or not self._needs_service(r): continue
                p = self._get_priority(r.fan_speed)

                if max_wait is None or p > max_wait['prio']:
                    max_wait = {'rid': rid, 'prio': p}

            if not max_wait: return

            if max_wait['prio'] > min_serv['prio']:
                print(f">>> [Dynamic Swap] R{max_wait['rid']} replaces R{min_serv['rid']}")
                r_w = Room.query.get(max_wait['rid'])
                r_s = Room.query.get(min_serv['rid'])
                self._move_to_wait(r_s)
                self._move_to_service(r_w)

    def _tick_time_slice_check(self):
        now = datetime.now()
        with db.app.app_context():
            for wid in list(self.wait_queue):
                st = self.wait_start_times.get(wid)
                if not st: continue

                dur = (now - st).total_seconds() * SystemConstants.TIME_KX
                if dur >= SystemConstants.TIME_SLICE:
                    wroom = Room.query.get(wid)
                    if not wroom: continue
                    wprio = self._get_priority(wroom.fan_speed)

                    target_sid = None
                    max_d = -1

                    for sid in self.service_queue:
                        sroom = Room.query.get(sid)
                        if not sroom: continue
                        sprio = self._get_priority(sroom.fan_speed)

                        if sprio == wprio:
                            d = self._get_service_duration(sid)
                            if d > max_d:
                                max_d = d
                                target_sid = sid

                    if target_sid:
                        print(f">>> [RR Slice] R{wid} rotates R{target_sid}")
                        r_wait = Room.query.get(wid)
                        r_serv = Room.query.get(target_sid)
                        self._move_to_wait(r_serv)
                        self._move_to_service(r_wait)
                        return

                        # ================= 物理循环 (优化版) =================

    def _simulation_loop(self):
        # 优化 1: 增加间隔至 0.5s，降低 DB 竞争频率
        step_real_sec = 0.5

        while self.is_running:
            if self.physics_paused:
                time.sleep(1)
                self.last_tick_time = datetime.now()
                continue

            with db.app.app_context():
                try:
                    now = datetime.now()
                    actual_delta = (now - self.last_tick_time).total_seconds()

                    if actual_delta > 0.05:
                        self.last_tick_time = now
                        # 优化 2: 放宽追赶限制，允许一次追赶 5秒的物理时间，防止跳变
                        if actual_delta > 5.0: actual_delta = 5.0

                        delta_sys_sec = actual_delta * SystemConstants.TIME_KX
                        self._update_all_physics(delta_sys_sec)
                except Exception as e:
                    print(f"Phys Loop Err: {e}")

            time.sleep(0.05)

            with db.app.app_context():
                try:
                    with self._lock:
                        self._tick_time_slice_check()
                        self._check_dynamic_preemption()
                except Exception as e:
                    pass

            time.sleep(step_real_sec)

    def _update_all_physics(self, delta_sys_sec):
        # 优化 3: 强制按 ID 排序更新，防止死锁 (Deadlock Prevention)
        rooms = Room.query.order_by(Room.room_id).all()
        for room in rooms:
            self._update_single_room(room, delta_sys_sec)
        db.session.commit()

    def _update_single_room(self, room, delta_sys_sec):
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
            clean_fan = str(room.fan_speed).strip().upper()
            rate = self._get_temp_change_rate(clean_fan)
            temp_delta = (rate / 60.0) * delta_sys_sec
            effective_time_sec = delta_sys_sec

            if self.current_mode == 'COOL':
                if (current_temp - temp_delta) < target_temp:
                    needed = current_temp - target_temp
                    if needed < 0: needed = 0
                    if rate > 0: effective_time_sec = needed / (rate / 60.0)
                    new_temp = target_temp
                else:
                    new_temp = current_temp - temp_delta
            else:
                if (current_temp + temp_delta) > target_temp:
                    needed = target_temp - current_temp
                    if needed < 0: needed = 0
                    if rate > 0: effective_time_sec = needed / (rate / 60.0)
                    new_temp = target_temp
                else:
                    new_temp = current_temp + temp_delta

            fee_rate_per_min = self._get_fee_rate(clean_fan)
            cost = (fee_rate_per_min / 60.0) * effective_time_sec

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
                print(f">>> [Reached] R{room.room_id} temp target reached.")
                self.temp_hysteresis_set.add(room.room_id)
                with self._lock:
                    self._remove_from_service(room.room_id)
                    self._schedule_next()

        if room.power_status == 'ON' and room.room_id not in self.service_queue and \
                room.room_id not in self.wait_queue:
            if self._needs_service(room):
                with self._lock:
                    self._handle_scheduling(room.room_id)

    # ================= 工具方法 =================

    def _needs_service(self, room):
        curr = float(room.current_temp)
        target = float(room.target_temp)

        if room.room_id in self.temp_hysteresis_set:
            if self.current_mode == 'COOL':
                if curr >= (target + 1.0):
                    self.temp_hysteresis_set.remove(room.room_id)
                    return True
                return False
            else:
                if curr <= (target - 1.0):
                    self.temp_hysteresis_set.remove(room.room_id)
                    return True
                return False

        if self.current_mode == 'COOL':
            return curr > target
        else:
            return curr < target

    def _add_to_service(self, room, original_start_time=None):
        if room.room_id not in self.service_queue:
            self.service_queue.append(room.room_id)
            if original_start_time:
                self.service_start_times[room.room_id] = original_start_time
            else:
                self.service_start_times[room.room_id] = datetime.now()
            self._start_new_record(room)

    def _start_new_record(self, room):
        try:
            self._close_current_record(room.room_id)
            clean_fan = str(room.fan_speed).strip().upper()
            new_record = DetailRecord(
                room_id=room.room_id, session_id=room.active_session_id,
                start_time=datetime.now(), fan_speed=clean_fan,
                fee_rate=self._get_fee_rate(clean_fan),
                fee=0.0, duration=0.0
            )
            db.session.add(new_record)
            db.session.commit()
        except Exception as e:
            db.session.rollback()

    def _close_current_record(self, room_id):
        try:
            records = DetailRecord.query.filter_by(room_id=room_id, end_time=None).all()
            for r in records:
                r.end_time = datetime.now()
                db.session.add(r)
            db.session.commit()
        except Exception as e:
            db.session.rollback()

    def _add_to_wait(self, room):
        if room.room_id not in self.wait_queue:
            self.wait_queue.append(room.room_id)
            self.wait_start_times[room.room_id] = datetime.now()

    def _remove_from_service(self, room_id):
        if room_id in self.service_queue:
            self.service_queue.remove(room_id)
            self.service_start_times.pop(room_id, None)
            self._close_current_record(room_id)

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
        f = str(fan).strip().upper()
        if f == 'HIGH': return 3
        if f in ['MEDIUM', 'MID']: return 2
        return 1

    def _get_fee_rate(self, fan):
        if not fan: return 0.5
        f = str(fan).strip().upper()
        if f == 'HIGH': return float(SystemConstants.FEE_RATE_HIGH)
        if f in ['MEDIUM', 'MID']: return float(SystemConstants.FEE_RATE_MID)
        if f == 'LOW': return float(SystemConstants.FEE_RATE_LOW)
        return 0.5

    def _get_temp_change_rate(self, fan):
        f = str(fan).strip().upper()
        if f == 'HIGH': return SystemConstants.TEMP_XH_HIGH
        if f in ['MEDIUM', 'MID']: return SystemConstants.TEMP_XH_MID
        if f == 'LOW': return SystemConstants.TEMP_XH_LOW
        return 0.5

    def reset_mode(self, mode):
        with db.app.app_context():
            if mode == 'HEAT':
                self.current_mode = 'HEAT'
                config = SystemConstants.HEAT_MODE_DEFAULTS
            else:
                self.current_mode = 'COOL'
                config = SystemConstants.COOL_MODE_DEFAULTS

            with self._lock:
                self.service_queue.clear()
                self.wait_queue.clear()
                self.service_start_times.clear()
                self.wait_start_times.clear()
                self.temp_hysteresis_set.clear()

            self.physics_paused = True

            db.session.query(DetailRecord).delete()
            db.session.query(Invoice).delete()
            rooms = Room.query.all()
            for room in rooms:
                str_id = str(room.room_id)
                int_id = int(room.room_id)
                val = config['initial_temps'].get(int_id) or config['initial_temps'].get(str_id)

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