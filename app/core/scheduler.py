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
                    cls._instance.service_queue = []  # 存 room_id
                    cls._instance.wait_queue = []  # 存 room_id

                    # 核心：记录时间以支持调度策略
                    cls._instance.service_start_times = {}  # {room_id: datetime}
                    cls._instance.wait_start_times = {}  # {room_id: datetime}

                    cls._instance.current_mode = 'COOL'
                    cls._instance.is_running = False
                    cls._instance.start_simulation()
        return cls._instance

    def start_simulation(self):
        if not self.is_running:
            self.is_running = True
            t = threading.Thread(target=self._simulation_loop, daemon=True)
            t.start()

    # ================= 状态查询 =================

    def get_scheduling_status(self, room_id):
        if room_id in self.service_queue:
            return 'RUNNING'
        elif room_id in self.wait_queue:
            return 'WAITING'
        else:
            return 'IDLE'

    # ================= 接口方法 =================

    def request_power(self, room_id, fan_speed, target_temp):
        """开机或修改参数：视为发起一次新的送风请求"""
        with db.app.app_context():
            room = Room.query.get(room_id)
            if not room: return False

            # 无论之前状态如何，先结束旧详单
            self._close_current_record(room)

            # 更新请求参数
            room.target_temp = float(target_temp)
            room.fan_speed = fan_speed
            room.power_status = 'ON'
            room.fee_rate = self._get_fee_rate(fan_speed)
            db.session.commit()

            with self._lock:
                # 调节风速算作新请求，重新调度
                self._handle_scheduling(room)

            return True

    def stop_power(self, room_id):
        with db.app.app_context():
            room = Room.query.get(room_id)
            if not room: return False

            self._close_current_record(room)
            room.power_status = 'OFF'
            db.session.commit()

            with self._lock:
                self._remove_from_service(room_id)
                self._remove_from_wait(room_id)
                # 释放了资源，尝试调度等待队列中的请求 (2.2.3)
                self._schedule_next()

            return True

    # ================= 核心调度算法 (严格遵循文档 2.x 逻辑) =================

    def _handle_scheduling(self, room):
        """处理新的送风请求 (开机或调风)"""
        room_id = room.room_id

        # 0. 先将该房间从所有队列移除 (视为新请求)
        self._remove_from_service(room_id)
        self._remove_from_wait(room_id)

        # 1. 检查服务容量
        if len(self.service_queue) < SystemConstants.MAX_SERVICE:
            # 资源充足，直接服务
            self._add_to_service(room)
            return

        # 2. 资源不足，启动调度策略
        # 获取请求优先级
        req_prio = self._get_priority(room.fan_speed)

        # 获取服务队列中优先级最低的房间列表
        lowest_prio_val = 999
        lowest_rooms = []  # 存 (room_id, priority, duration)

        with db.app.app_context():
            for rid in self.service_queue:
                r = Room.query.get(rid)
                p = self._get_priority(r.fan_speed)
                d = self._get_service_duration(rid)

                if p < lowest_prio_val:
                    lowest_prio_val = p
                    lowest_rooms = [(rid, p, d, r.fan_speed)]
                elif p == lowest_prio_val:
                    lowest_rooms.append((rid, p, d, r.fan_speed))

        # === 逻辑 2.1: 请求优先级 > 服务队列最低优先级 ===
        if req_prio > lowest_prio_val:
            target_to_kick = None

            # 2.1.1 如果只有1个最低优先级
            if len(lowest_rooms) == 1:
                target_to_kick = lowest_rooms[0][0]

            # 2.1.2 多个最低，且风速相等 (优先级相等隐含风速相等)
            # 2.1.3 多个最低，风速不相等 (这在3级风速模型下不太可能出现同优先级但风速不同，除非优先级定义改变。这里假设同优先级即同风速)
            # 依照文档：如果有多个，释放服务时长最大的 (2.1.2)
            # 文档 2.1.3 说风速不相等释放风速最低的，但在我们的模型里，最低优先级就是最低风速。
            # 所以统一逻辑：在最低优先级里，找服务时间最长的。
            else:
                # 按 duration 降序排序，取第一个
                lowest_rooms.sort(key=lambda x: x[2], reverse=True)
                target_to_kick = lowest_rooms[0][0]

            if target_to_kick:
                print(f">>> [抢占] {room_id}(P{req_prio}) 抢占 {target_to_kick}(P{lowest_prio_val})")
                self._move_to_wait(target_to_kick)  # 被踢房间进入等待，分配时长 s
                self._add_to_service(room)  # 新房间进入服务
                return

        # === 逻辑 2.2: 请求优先级 == 服务队列最低优先级 ===
        elif req_prio == lowest_prio_val:
            # 2.2.1 放入等待队列，分配时长 s，倒计时
            print(f">>> [等待] {room_id} 优先级相等，进入时间片等待")
            self._add_to_wait(room)
            return

        # === 逻辑 2.3: 请求优先级 < 服务队列最低优先级 ===
        else:
            # 分配等待时长 s (但在本系统中，低优先级只能等空闲)
            print(f">>> [等待] {room_id} 优先级较低，进入等待")
            self._add_to_wait(room)
            return

    def _tick_time_slice_check(self):
        """逻辑 2.2.2: 检查等待队列中的时间片是否耗尽"""
        # 遍历等待队列，寻找是否有人等待超时
        # 注意：只有当 请求优先级 == 当前服务最低优先级 时，才适用时间片抢占
        # 但为了简化且符合"兼顾公平"，如果等待时间到了 s，且优先级不低于正在服务的某人，尝试轮转

        now = datetime.now()
        ids_to_process = list(self.wait_queue)  # 复制一份以防修改

        for wait_rid in ids_to_process:
            start_t = self.wait_start_times.get(wait_rid)
            if not start_t: continue

            # 计算等待时长 (系统时间秒)
            wait_duration_sys = (now - start_t).total_seconds() * SystemConstants.TIME_KX

            # 2.2.2 当等待服务时长减小到 0 (即等待了 TIME_SLICE)
            if wait_duration_sys >= SystemConstants.TIME_SLICE:
                # 检查是否有资格替换 (逻辑：同优先级轮转)
                with db.app.app_context():
                    wait_room = Room.query.get(wait_rid)
                    wait_prio = self._get_priority(wait_room.fan_speed)

                    # 寻找服务队列中 同优先级 且 服务时长最大 的
                    target_rid = None
                    max_duration = -1

                    for serv_rid in self.service_queue:
                        serv_room = Room.query.get(serv_rid)
                        serv_prio = self._get_priority(serv_room.fan_speed)
                        serv_duration = self._get_service_duration(serv_rid)

                        # 必须优先级相等才能进行时间片轮转 (根据 2.2 定义)
                        if serv_prio == wait_prio:
                            if serv_duration > max_duration:
                                max_duration = serv_duration
                                target_rid = serv_rid

                    if target_rid:
                        print(f">>> [轮转] {wait_rid} 等待超时，替换 {target_rid}")
                        self._move_to_wait(target_rid)  # 服务最长的去等待
                        self._move_to_service(wait_rid)  # 等待超时的去服务

    def _schedule_next(self):
        """逻辑 2.2.3: 服务对象释放时，调度等待队列中最久的对象"""
        # 文档 2.2.3: "等待队列中的等待服务时长最久的对象获得服务对象"
        # 文档 2.2.4: "如果有更高风速...优先级比同风速...的高"
        # 综合：先看优先级，高优先级优先；同优先级下，等待最久的优先。

        if len(self.wait_queue) == 0: return
        if len(self.service_queue) >= SystemConstants.MAX_SERVICE: return

        best_candidate = None

        # 寻找最佳候选人
        with db.app.app_context():
            # 排序依据：(优先级 DESC, 等待开始时间 ASC)
            candidates = []
            for rid in self.wait_queue:
                r = Room.query.get(rid)
                p = self._get_priority(r.fan_speed)
                t = self.wait_start_times.get(rid, datetime.now())
                candidates.append({'rid': rid, 'prio': p, 'time': t, 'room': r})

            # 排序：优先级高在前，时间早(小)在前
            candidates.sort(key=lambda x: (-x['prio'], x['time']))

            if candidates:
                best_candidate = candidates[0]['room']

        if best_candidate:
            print(f">>> [补位] {best_candidate.room_id} 从等待队列补位")
            self._move_to_service(best_candidate.room_id)

    # ================= 队列操作辅助 =================

    def _add_to_service(self, room):
        if room.room_id not in self.service_queue:
            self.service_queue.append(room.room_id)
            self.service_start_times[room.room_id] = datetime.now()
            with db.app.app_context():
                self._start_new_record(room)

    def _add_to_wait(self, room):
        if room.room_id not in self.wait_queue:
            self.wait_queue.append(room.room_id)
            self.wait_start_times[room.room_id] = datetime.now()  # 重置倒计时

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

    def _move_to_wait(self, room_id):
        """将房间从服务移入等待 (被抢占或轮转)"""
        self._remove_from_service(room_id)
        with db.app.app_context():
            r = Room.query.get(room_id)
            self._add_to_wait(r)

    def _move_to_service(self, room_id):
        """将房间从等待移入服务"""
        self._remove_from_wait(room_id)
        with db.app.app_context():
            r = Room.query.get(room_id)
            self._add_to_service(r)

    def _get_service_duration(self, room_id):
        start = self.service_start_times.get(room_id)
        if not start: return 0
        return (datetime.now() - start).total_seconds()

    # ================= 物理引擎与状态维护 =================

    def _simulation_loop(self):
        while self.is_running:
            with db.app.app_context():
                try:
                    self._tick()
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    # print(f"Error: {e}")
            time.sleep(1)  # 现实 1 秒

    def _tick(self):
        # 1. 检查时间片轮转 (2.2.2)
        with self._lock:
            self._tick_time_slice_check()

        delta_sec = SystemConstants.TIME_KX
        rooms = Room.query.all()
        for room in rooms:
            self._update_room_physics(room, delta_sec)

    def _update_room_physics(self, room, delta_sec):
        is_serving = (room.room_id in self.service_queue) and (room.power_status == 'ON')

        temp_change = 0.0
        cost_increase = 0.0

        if is_serving:
            # 送风模式
            rate_per_min = self._get_temp_change_rate(room.fan_speed)
            change = (rate_per_min / 60.0) * delta_sec

            if self.current_mode == 'COOL':
                temp_change = -change
            else:
                temp_change = change

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
            change = (SystemConstants.RECOVER_RATE / 60.0) * delta_sec
            if self.current_mode == 'COOL':
                temp_change = change
            else:
                temp_change = -change

        new_temp = float(room.current_temp) + temp_change

        # 回温边界限制
        if self.current_mode == 'COOL':
            init_t = SystemConstants.COOL_MODE_DEFAULTS['initial_temps'].get(room.room_id, 30.0)
            if not is_serving and new_temp > init_t: new_temp = init_t
        else:
            init_t = SystemConstants.HEAT_MODE_DEFAULTS['initial_temps'].get(room.room_id, 10.0)
            if not is_serving and new_temp < init_t: new_temp = init_t

        room.current_temp = round(new_temp, 4)

        # 达到目标温度逻辑
        if is_serving:
            target = float(room.target_temp)
            if (self.current_mode == 'COOL' and room.current_temp <= target) or \
                    (self.current_mode == 'HEAT' and room.current_temp >= target):
                # 暂停服务，但不关机，也不进等待队列
                # 此时状态：On, IDLE (Monitoring)
                print(f">>> [温控] {room.room_id} 达到目标温度，暂停送风")
                with self._lock:
                    self._remove_from_service(room.room_id)
                    # 释放了资源，调度下一个 (2.2.3)
                    self._schedule_next()

        # 回温重启逻辑：当室温回温 1℃ 时重新发送请求
        # 条件：开机状态，既不在服务也不在等待 (即处于温控暂停状态)
        if room.power_status == 'ON' and \
                room.room_id not in self.service_queue and \
                room.room_id not in self.wait_queue:

            target = float(room.target_temp)
            if abs(room.current_temp - target) >= 1.0:
                print(f">>> [温控] {room.room_id} 回温超过1度，重新请求服务")
                # 重新发送温控请求：请求参数保持与暂停时一致
                with self._lock:
                    self._handle_scheduling(room)

    # ================= 辅助 =================

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

    def _get_priority(self, fan_speed):
        if fan_speed == 'HIGH': return 3
        if fan_speed == 'MEDIUM' or fan_speed == 'MID': return 2
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

        with db.app.app_context():
            db.session.query(DetailRecord).delete()
            db.session.query(Invoice).delete()

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