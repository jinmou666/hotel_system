from app import db
from app.models import DetailRecord, Invoice, Room
from config import SystemConstants
from sqlalchemy import func
from datetime import datetime
import uuid


class BillService:
    @staticmethod
    def calculate_total_fee(room_id):
        total_fee = db.session.query(func.sum(DetailRecord.fee)) \
            .filter(DetailRecord.room_id == room_id) \
            .scalar()
        return float(total_fee) if total_fee is not None else 0.0

    @staticmethod
    def calculate_stay_days(room_id):
        """
        计算入住天数：
        逻辑：统计不重复的 session_id 数量。
        每个 session_id 对应一次完整的开机-关机周期。
        """
        count = db.session.query(func.count(func.distinct(DetailRecord.session_id))) \
            .filter(DetailRecord.room_id == room_id) \
            .scalar()

        # 如果 count 为 0 (比如只开了机没关机，或者刚开机)，至少算 1 天
        return count if count and count > 0 else 1

    @staticmethod
    def create_invoice(room_id):
        try:
            room = Room.query.get(room_id)
            if not room: return None

            ac_fee = BillService.calculate_total_fee(room_id)

            # 使用新逻辑计算天数
            stay_days = BillService.calculate_stay_days(room_id)

            rate_key = str(room_id)
            daily_rate = SystemConstants.ROOM_DAILY_RATES.get(rate_key, 100.0)
            accommodation_fee = stay_days * daily_rate

            total_amount = ac_fee + accommodation_fee

            check_out_date = datetime.now()
            check_in_date = room.customer_ref.registration_date if room.customer_ref else check_out_date

            new_invoice = Invoice(
                invoice_id=uuid.uuid4().hex,
                room_id=room_id,
                customer_id=room.customer_id if room.customer_id else "UNKNOWN",
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                stay_days=stay_days,
                accommodation_fee=accommodation_fee,
                ac_fee=ac_fee,
                total_amount=total_amount,
                create_time=datetime.now()
            )

            db.session.add(new_invoice)
            db.session.commit()
            return new_invoice
        except Exception as e:
            db.session.rollback()
            print(f"Error creating invoice: {e}")
            return None