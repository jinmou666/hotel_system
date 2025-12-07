from app import db
from app.models import DetailRecord, Invoice, Room
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
    def create_invoice(room_id):
        try:
            room = Room.query.get(room_id)
            if not room: return None

            ac_fee = BillService.calculate_total_fee(room_id)
            accommodation_fee = 0.0  # 简化
            total_amount = ac_fee + accommodation_fee

            check_out_date = datetime.now()
            check_in_date = room.customer_ref.registration_date if room.customer_ref else check_out_date

            new_invoice = Invoice(
                invoice_id=uuid.uuid4().hex,
                room_id=room_id,
                customer_id=room.customer_id if room.customer_id else "UNKNOWN",
                check_in_date=check_in_date,
                check_out_date=check_out_date,
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