from app import db
from app.models import Room, DetailRecord, Invoice
from config import SystemConstants
from datetime import datetime
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
                    cls._instance.current_mode = 'COOL'
                    cls._instance.is_running = False
                    cls._instance.start_simulation()
        return cls._instance

    def start_simulation(self):
        if not self.is_running:
            self.is_running = True
            t = threading.Thread(target=self._simulation_loop, daemon=True)
            t.start()

    # ================= 接口方法 =================

    def request_power(self, room_id, fan_speed, target_temp):
        with db.app.app_context():
            room = Room.query.get(room_id)
            if not room: return False

            self._close_current_record(room)

            room.target_temp = float(target_temp)
            room.fan_speed = fan_speed
            room.power_status = 'ON'
            room.fee_rate = self._get_fee_rate(fan_speed)

            # 调度逻辑
            if room_id in self.service_queue:
                self._start_new_record(room)
            elif room_id in self.wait_queue:
                pass
            else:
                self._add_to_queue(room_id)

            db.session.commit()
            return True

    def stop_power(self, room_id):
        with db.app.app_context():
            room = Room.query.get(room_id)
            if not room: return False

            self._close_current_record(room)
            room.power_status = 'OFF'

            if room_id in self.service_queue:
                self.service_queue.remove(room_id)
                self._schedule_next()

            if room_id in self.wait_queue:
                self.wait_queue.remove(room_id)

            db.session.commit()
            return True

    # ================= 内部调度逻辑 =================

    def _add_to_queue(self, room_id):
        if len(self.service_queue) < SystemConstants.MAX_SERVICE:
            self.service_queue.append(room_id)
            with db.app.app_context():
                room = Room.query.get(room_id)
                self._start_new_record(room)
        else:
            if room_id not in self.wait_queue:
                self.wait_queue.append(room_id)

    def _schedule_next(self):
        if len(self.wait_queue) > 0 and len(self.service_queue) < SystemConstants.MAX_SERVICE:
            next_room_id = self.wait_queue.pop(0)
            self.service_queue.append(next_room_id)
            with db.app.app_context():
                room = Room.query.get(next_room_id)
                self._start_new_record(room)

    # ================= 详单管理 =================

    def _start_new_record(self, room):
        new_record = DetailRecord(
            room_id=room.room_id,
            start_time=datetime.now(),
            fan_speed=room.fan_speed,
            fee_rate=room.fee_rate,
            fee=0.0,
            duration=0
        )
        db.session.add(new_record)
        db.session.commit()

    def _close_current_record(self, room):
        record = DetailRecord.query.filter_by(room_id=room.room_id, end_time=None).first()
        if record:
            record.end_time = datetime.now()
            db.session.add(record)

    # ================= 物理引擎 =================

    def _simulation_loop(self):
        while self.is_running:
            with db.app.app_context():
                try:
                    self._tick()
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    print(f"Physics Error: {e}")
            time.sleep(1)

    def _tick(self):
        delta_sec = SystemConstants.TIME_KX
        rooms = Room.query.all()
        for room in rooms:
            self._update_room_one_tick(room, delta_sec)

    def _update_room_one_tick(self, room, delta_sec):
        is_serving = (room.room_id in self.service_queue) and (room.power_status == 'ON')

        temp_change = 0.0
        cost_increase = 0.0

        if is_serving:
            # 送风模式
            rate_per_min = self._get_temp_change_rate(room.fan_speed)
            change_per_sec = rate_per_min / 60.0
            total_change = change_per_sec * delta_sec

            if self.current_mode == 'COOL':
                temp_change = -total_change
            else:
                temp_change = total_change

            fee_per_min = self._get_fee_rate(room.fan_speed)
            cost_increase = (fee_per_min / 60.0) * delta_sec

            room.current_fee = float(room.current_fee) + cost_increase
            room.total_fee = float(room.total_fee) + cost_increase

            record = DetailRecord.query.filter_by(room_id=room.room_id, end_time=None).first()
            if record:
                record.fee = float(record.fee) + cost_increase
                record.duration = int(record.duration) + int(delta_sec)

        else:
            # 回温模式
            recover_per_sec = SystemConstants.RECOVER_RATE / 60.0
            change = recover_per_sec * delta_sec

            if self.current_mode == 'COOL':
                temp_change = change  # 回温上升
            else:
                temp_change = -change  # 回温下降

        # 应用变化
        new_temp = float(room.current_temp) + temp_change

        # --- 核心修复：回温边界限制 ---
        # 获取当前模式下的初始温度配置
        if self.current_mode == 'COOL':
            config = SystemConstants.COOL_MODE_DEFAULTS
            initial_temp = config['initial_temps'].get(room.room_id, 30.0)
            # 制冷模式：回温是上升，不能超过初始温度
            if not is_serving and new_temp > initial_temp:
                new_temp = initial_temp
        else:
            config = SystemConstants.HEAT_MODE_DEFAULTS
            initial_temp = config['initial_temps'].get(room.room_id, 10.0)
            # 制热模式：回温是下降，不能低于初始温度
            if not is_serving and new_temp < initial_temp:
                new_temp = initial_temp
        # ---------------------------

        room.current_temp = round(new_temp, 4)

        # 自动温控 (到达目标停止送风)
        if is_serving:
            target = float(room.target_temp)
            if (self.current_mode == 'COOL' and room.current_temp <= target) or \
                    (self.current_mode == 'HEAT' and room.current_temp >= target):
                self.service_queue.remove(room.room_id)
                self.wait_queue.append(room.room_id)
                self._close_current_record(room)
                self._schedule_next()

    # ================= 辅助方法 =================

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

        with db.app.app_context():
            db.session.query(DetailRecord).delete()
            db.session.query(Invoice).delete()  # 账单也清空

            rooms = Room.query.all()
            for room in rooms:
                if room.room_id in config['initial_temps']:
                    room.current_temp = config['initial_temps'][room.room_id]
                    room.target_temp = config['default_target']
                    room.fan_speed = 'MEDIUM'
                    room.power_status = 'OFF'
                    room.current_fee = 0.0
                    room.total_fee = 0.0
                    room.status = 'AVAILABLE'
            db.session.commit()
        return True