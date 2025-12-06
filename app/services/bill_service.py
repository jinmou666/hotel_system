from app import db
from app.models import DetailRecord, Invoice, Room
from config import SystemConstants
from sqlalchemy import func
from datetime import datetime
import uuid

class BillService:
    
    @staticmethod
    def get_fee_rate(fan_speed):
        """
        根据 SystemConstants 获取当前费率
        (辅助方法，用于生成详单或计算实时费用时参考)
        """
        if fan_speed == 'HIGH':
            return SystemConstants.FEE_RATE_HIGH
        elif fan_speed == 'MID':
            return SystemConstants.FEE_RATE_MID
        elif fan_speed == 'LOW':
            return SystemConstants.FEE_RATE_LOW
        return 1.0 # 默认兜底

    @staticmethod
    def calculate_total_fee(room_id):
        """
        查询该房间所有 DetailRecord，累加 fee 字段。
        :param room_id: 房间号
        :return: float 总空调费用
        """
        # 使用 SQLAlchemy 的 sum 聚合函数直接在数据库层面计算
        total_fee = db.session.query(func.sum(DetailRecord.fee))\
            .filter(DetailRecord.room_id == room_id)\
            .scalar()

        # 如果没有记录，scalar() 返回 None，处理为 0.0
        return float(total_fee) if total_fee is not None else 0.0

    @staticmethod
    def create_invoice(room_id):
        """
        计算总金额，创建 Invoice 对象写入数据库，并返回 Invoice 信息。
        :param room_id: 房间号
        :return: Invoice 对象 或 None
        """
        try:
            # 1. 获取房间信息以确定客户
            room = Room.query.get(room_id)
            if not room or not room.customer_id:
                raise ValueError(f"Room {room_id} not found or not occupied.")

            # 2. 计算空调总费用
            ac_fee = BillService.calculate_total_fee(room_id)
            
            # 3. 计算住宿费 (此处暂设为0，或者可以根据业务逻辑扩展)
            accommodation_fee = 0.0 
            
            # 4. 计算总金额
            total_amount = ac_fee + accommodation_fee

            # 5. 确定时间信息
            # 结束时间为当前
            check_out_date = datetime.now()
            # 开始时间：尝试获取客户注册时间，如果没有则默认为当前
            check_in_date = room.customer_ref.registration_date if room.customer_ref else check_out_date

            # 6. 创建 Invoice 对象
            new_invoice = Invoice(
                invoice_id=uuid.uuid4().hex,  # 生成唯一ID
                room_id=room_id,
                customer_id=room.customer_id,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                accommodation_fee=accommodation_fee,
                ac_fee=ac_fee,
                total_amount=total_amount,
                create_time=datetime.now()
            )

            # 7. 写入数据库
            db.session.add(new_invoice)
            
            # 可选：更新房间的总费用字段以保持同步
            room.total_fee = total_amount
            
            db.session.commit()
            
            return new_invoice

        except Exception as e:
            db.session.rollback()
            print(f"Error creating invoice for room {room_id}: {str(e)}")
            # 在实际项目中应记录日志或抛出自定义异常
            return None