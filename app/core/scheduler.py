from app.models import Room, DetailRecord, Invoice
from app import db
from config import SystemConstants
import threading


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
                    # 默认为制冷模式
                    cls._instance.current_mode = 'COOL'
        return cls._instance

    def reset_mode(self, mode):
        """
        一键重置系统模式 (用于验收演示切换)
        mode: 'COOL' 或 'HEAT'
        """
        # 1. 确定使用哪套参数
        if mode == 'HEAT':
            config = SystemConstants.HEAT_MODE_DEFAULTS
            self.current_mode = 'HEAT'
        else:
            config = SystemConstants.COOL_MODE_DEFAULTS
            self.current_mode = 'COOL'

        print(f">>> 正在切换系统至 [{self.current_mode}] 模式...")

        # 2. 清空调度队列
        self.service_queue.clear()
        self.wait_queue.clear()

        # 3. 批量重置数据库中的房间状态
        # 注意：这里需要在一个应用上下文中运行，或者由 Controller 调用时自然在上下文中
        rooms = Room.query.all()
        for room in rooms:
            if room.room_id in config['rooms']:
                # 重置为该模式下的初始室温
                room.current_temp = config['rooms'][room.room_id]
                # 重置为该模式下的默认目标温度
                room.target_temp = config['default_target']

                # 重置其他状态为“未开机”
                room.fan_speed = 'MEDIUM'
                room.power_status = 'OFF'
                room.status = 'AVAILABLE'
                room.current_fee = 0.0
                room.total_fee = 0.0  # 可选：是否清空历史费用看你们需求

        # 4. 提交更改到数据库
        try:
            db.session.commit()
            print(f">>> [{self.current_mode}] 模式切换成功，所有房间已重置。")
            return True
        except Exception as e:
            db.session.rollback()
            print(f">>> 模式切换失败: {e}")
            return False

