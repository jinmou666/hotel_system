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

    # ================= 调度逻辑 =================

    def _needs_service(self, room):
        curr = float(room.current_temp)
        target = float(room.target_temp)
        epsilon = 0.01
        if self.current_mode == 'COOL':
            return curr > (target + epsilon)
        else:
            return curr < (target - epsilon)

    def _handle_scheduling(self, room_id):
        room = Room.query.get(room_id)
        if not room: return

        self._remove_from_service(room_id)
        self._remove_from_wait(room_id)

        if not self._needs_service(room): return

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

        if req_prio > lowest_prio_val:
            lowest_rooms.sort(key=lambda x: x[2], reverse=True)
            target_to_kick = lowest_rooms[0][0]
            if target_to_kick:
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
            self._move_to_service(best_room)

    # ================= 物理引擎 (高频采样 + 误差修正) =================

    def _simulation_loop(self):
        # 核心改动：提高采样频率到 0.2s (5Hz)
        # 这意味着每次计算只推进 1.2秒系统时间，大幅减少过冲误差
        step_real_sec = 0.2

        while self.is_running:
            if self.physics_paused:
                time.sleep(1)
                self.last_tick_time = datetime.now()
                continue

            with db.app.app_context():
                try:
                    now = datetime.now()
                    # 计算真实流逝时间，防止线程调度导致的误差
                    actual_delta = (now - self.last_tick_time).total_seconds()
                    self.last_tick_time = now

                    # 钳位：如果卡顿太久，最多只算 1秒的物理量，防止瞬移
                    if actual_delta > 1.0: actual_delta = 1.0

                    if actual_delta > 0.01:
                        self._tick(actual_delta)
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
            # 理论变化量
            temp_delta = (rate / 60.0) * delta_sys_sec

            # === 误差修正：检查是否会过冲 ===
            # 如果这一步走完会超过目标温度，我们只走“刚好到达”的那一步
            # 并且只收“刚好到达”那一部分的钱

            effective_time_sec = delta_sys_sec  # 实际有效计费时间

            if self.current_mode == 'COOL':
                # 降温中
                if (current_temp - temp_delta) < target_temp:
                    # 会过冲，只计算到达 target 所需的时间
                    needed_drop = current_temp - target_temp
                    if needed_drop < 0: needed_drop = 0
                    # 重新计算需要的秒数
                    if rate > 0:
                        effective_time_sec = (needed_drop / (rate / 60.0))
                    new_temp = target_temp
                else:
                    new_temp = current_temp - temp_delta
            else:
                # 升温中
                if (current_temp + temp_delta) > target_temp:
                    needed_rise = target_temp - current_temp
                    if needed_rise < 0: needed_rise = 0
                    if rate > 0:
                        effective_time_sec = (needed_rise / (rate / 60.0))
                    new_temp = target_temp
                else:
                    new_temp = current_temp + temp_delta

            # 计费 (使用修正后的有效时间)
            fee_rate = self._get_fee_rate(room.fan_speed)
            cost = (fee_rate / 60.0) * effective_time_sec

            room.current_fee = float(room.current_fee) + cost
            room.total_fee = float(room.total_fee) + cost

            record = DetailRecord.query.filter_by(room_id=room.room_id, end_time=None).first()
            if record:
                record.fee = float(record.fee) + cost
                record.duration = int(record.duration) + int(effective_time_sec)
        else:
            # 回温 (不需要精确计费，直接走)
            step = (SystemConstants.RECOVER_RATE / 60.0) * delta_sys_sec
            if self.current_mode == 'COOL':
                new_temp = current_temp + step
                if new_temp > initial_temp: new_temp = initial_temp
            else:
                new_temp = current_temp - step
                if new_temp < initial_temp: new_temp = initial_temp

        room.current_temp = round(new_temp, 4)

        # 温控达标检查
        if is_serving:
            reached = False
            # 严格比较
            if self.current_mode == 'COOL' and room.current_temp <= target_temp: reached = True
            if self.current_mode == 'HEAT' and room.current_temp >= target_temp: reached = True

            if reached:
                print(f">>> [温控] R{room.room_id} 达标，暂停服务")
                with self._lock:
                    self._remove_from_service(room.room_id)
                    self._schedule_next()

        # 回温重启逻辑 (1度)
        if room.power_status == 'ON' and \
                room.room_id not in self.service_queue and \
                room.room_id not in self.wait_queue:
            should_restart = False
            if self.current_mode == 'COOL' and room.current_temp >= (target_temp + 0.99): should_restart = True
            if self.current_mode == 'HEAT' and room.current_temp <= (target_temp - 0.99): should_restart = True
            if should_restart:
                print(f">>> [温控] R{room.room_id} 重启")
                with self._lock: self._handle_scheduling(room.room_id)

    # ... (保持其他辅助方法不变) ...
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
                        r_wait = Room.query.get(wid)
                        r_targ = Room.query.get(tid)
                        self._move_to_wait(r_targ)
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
            db.session.commit()
        return True