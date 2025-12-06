import threading
import time
import datetime
from app import db
from app.models import Room, DetailRecord
from config import SystemConstants


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
                    cls._instance.app = None
                    cls._instance.current_mode = 'COOL'
        return cls._instance

    def init_app(self, app):
        self.app = app
        monitor_thread = threading.Thread(target=self._time_slice_monitor)
        monitor_thread.daemon = True
        monitor_thread.start()

    def request_power(self, room_id, fan_speed, target_temp):
        with self._lock:
            with self.app.app_context():
                print(f"[Request] Room:{room_id}, Speed:{fan_speed}")

                # 更新参数
                self._update_room_params(room_id, fan_speed, target_temp)

                # 如果已在队列，先移除（视为新请求）
                if room_id in self.service_queue:
                    self._stop_service_billing(room_id)
                    self.service_queue.remove(room_id)
                elif room_id in self.wait_queue:
                    self.wait_queue.remove(room_id)

                # 尝试调度
                return self._try_dispatch(room_id, fan_speed)

    def change_temp(self, room_id, target_temp):
        with self.app.app_context():
            room = Room.query.get(room_id)
            if room:
                room.target_temp = target_temp
                db.session.commit()
            return True

    def _try_dispatch(self, room_id, fan_speed):
        # 1. 资源充足
        if len(self.service_queue) < 3:
            self._start_service(room_id)
            return True

        # 2. 资源不足，抢占
        my_p = self._get_priority(fan_speed)
        victim_id, victim_p = self._find_lowest_priority_in_service()

        if my_p > victim_p:
            print(f"[Preempt] {room_id} replaced {victim_id}")
            self._preempt_room(victim_id)
            self._start_service(room_id)
            return True
        else:
            self._add_to_wait(room_id)
            return False

    def _time_slice_monitor(self):
        while True:
            time.sleep(1)
            if not self.app: continue
            with self._lock:
                with self.app.app_context():
                    if self.wait_queue and len(self.service_queue) == 3:
                        self._check_and_rotate()

    def _check_and_rotate(self):
        real_seconds_limit = SystemConstants.TIME_SLICE / (SystemConstants.TIME_SCALE / 10.0)
        now = datetime.datetime.now()

        candidate_id = self._find_highest_priority_in_wait()
        if not candidate_id: return

        candidate_p = self._get_priority(Room.query.get(candidate_id).fan_speed)

        longest_duration = 0
        victim_id = None

        for rid in self.service_queue:
            room = Room.query.get(rid)
            if not room.serve_start_time: continue
            duration = (now - room.serve_start_time).total_seconds()

            # 超时且优先级 <= 等待者
            if duration > real_seconds_limit and self._get_priority(room.fan_speed) <= candidate_p:
                if duration > longest_duration:
                    longest_duration = duration
                    victim_id = rid

        if victim_id:
            print(f"[Rotate] {victim_id} -> {candidate_id}")
            self._preempt_room(victim_id)
            self._start_service(candidate_id)
            self.wait_queue.remove(candidate_id)

    # --- 辅助 ---
    def _start_service(self, room_id):
        if room_id not in self.service_queue: self.service_queue.append(room_id)
        room = Room.query.get(room_id)
        room.status = 'SERVING'
        room.power_status = 'ON'
        room.serve_start_time = datetime.datetime.now()
        # 创建详单
        new_record = DetailRecord(
            room_id=room_id, start_time=datetime.datetime.now(),
            fan_speed=room.fan_speed, fee_rate=self._get_fee_rate(room.fan_speed)
        )
        db.session.add(new_record)
        db.session.commit()

    def _preempt_room(self, room_id):
        self._stop_service_billing(room_id)
        if room_id in self.service_queue: self.service_queue.remove(room_id)
        self._add_to_wait(room_id)

    def _add_to_wait(self, room_id):
        if room_id not in self.wait_queue: self.wait_queue.append(room_id)
        room = Room.query.get(room_id)
        room.status = 'WAITING'
        db.session.commit()

    def _stop_service_billing(self, room_id):
        room = Room.query.get(room_id)
        last_record = DetailRecord.query.filter_by(room_id=room_id, end_time=None).first()
        if last_record:
            now = datetime.datetime.now()
            last_record.end_time = now
            duration = (now - last_record.start_time).total_seconds()
            last_record.duration = int(duration)

            scale = SystemConstants.TIME_SCALE / 10.0
            sys_minutes = (duration * scale) / 60.0
            fee = sys_minutes * float(last_record.fee_rate)

            last_record.fee = round(fee, 2)
            room.current_fee = float(room.current_fee) + fee
            room.total_fee = float(room.total_fee) + fee
            db.session.commit()

    def _update_room_params(self, room_id, fan_speed, target_temp):
        room = Room.query.get(room_id)
        room.fan_speed = fan_speed
        room.target_temp = target_temp
        if room.power_status == 'OFF': room.power_status = 'ON'
        db.session.commit()

    def _get_priority(self, fan_speed):
        return {'HIGH': 3, 'MID': 2, 'LOW': 1}.get(fan_speed, 1)

    def _get_fee_rate(self, fan_speed):
        if fan_speed == 'HIGH': return SystemConstants.FEE_RATE_HIGH
        if fan_speed == 'MID': return SystemConstants.FEE_RATE_MID
        return SystemConstants.FEE_RATE_LOW

    def _find_lowest_priority_in_service(self):
        min_p = 99
        victim = None
        for rid in self.service_queue:
            p = self._get_priority(Room.query.get(rid).fan_speed)
            if p < min_p:
                min_p = p
                victim = rid
        return victim, min_p

    def _find_highest_priority_in_wait(self):
        max_p = -1
        candidate = None
        for rid in self.wait_queue:
            p = self._get_priority(Room.query.get(rid).fan_speed)
            if p > max_p:
                max_p = p
                candidate = rid
        return candidate

    # --- 验收专用 ---
    def reset_mode(self, mode):
        if mode == 'HEAT':
            config = SystemConstants.HEAT_MODE_DEFAULTS
            self.current_mode = 'HEAT'
        else:
            config = SystemConstants.COOL_MODE_DEFAULTS
            self.current_mode = 'COOL'

        print(f">>> RESET MODE TO: {self.current_mode}")
        self.service_queue.clear()
        self.wait_queue.clear()

        rooms = Room.query.all()
        for room in rooms:
            if room.room_id in config['rooms']:
                room.current_temp = config['rooms'][room.room_id]
                room.target_temp = config['default_target']
                room.fan_speed = 'MEDIUM'
                room.power_status = 'OFF'
                room.status = 'AVAILABLE'
                room.current_fee = 0.0
                room.total_fee = 0.0
                room.serve_start_time = None

        db.session.commit()