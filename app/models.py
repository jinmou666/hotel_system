from app import db
from datetime import datetime


class Customer(db.Model):
    __tablename__ = 'customer'
    customer_id = db.Column(db.String(32), primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    id_number = db.Column(db.String(18), nullable=False)
    phone = db.Column(db.String(11))
    registration_date = db.Column(db.DateTime, default=datetime.now)

    rooms = db.relationship('Room', backref='customer_ref', lazy=True)
    invoices = db.relationship('Invoice', backref='customer_ref', lazy=True)

    def to_dict(self):
        return {
            'customer_id': self.customer_id,
            'name': self.name,
            'id_number': self.id_number,
            'phone': self.phone,
            'registration_date': self.registration_date.isoformat() if self.registration_date else None
        }


class Room(db.Model):
    __tablename__ = 'room'

    room_id = db.Column(db.String(10), primary_key=True)
    # 精度配合 Config 和 SQL
    current_temp = db.Column(db.Numeric(8, 4), default=22.0000)
    target_temp = db.Column(db.Numeric(8, 4), default=22.0000)
    fan_speed = db.Column(db.String(10), default='MEDIUM')
    power_status = db.Column(db.String(5), default='OFF')
    fee_rate = db.Column(db.Numeric(8, 4), default=1.0000)
    current_fee = db.Column(db.Numeric(12, 4), default=0.0000)
    total_fee = db.Column(db.Numeric(12, 4), default=0.0000)

    customer_id = db.Column(db.String(32), db.ForeignKey('customer.customer_id'))
    status = db.Column(db.String(20), default='AVAILABLE')

    detail_records = db.relationship('DetailRecord', backref='room_ref', lazy=True)
    invoices = db.relationship('Invoice', backref='room_ref', lazy=True)

    def to_dict(self):
        # 内部高精度，返回给前端展示时保留2位
        return {
            'room_id': self.room_id,
            'current_temp': round(float(self.current_temp), 2) if self.current_temp is not None else 0.0,
            'target_temp': float(self.target_temp) if self.target_temp is not None else 0.0,
            'fan_speed': self.fan_speed,
            'power_status': self.power_status,
            'fee_rate': float(self.fee_rate) if self.fee_rate is not None else 0.0,
            'current_fee': round(float(self.current_fee), 2) if self.current_fee is not None else 0.0,
            'total_fee': round(float(self.total_fee), 2) if self.total_fee is not None else 0.0,
            'customer_id': self.customer_id,
            'status': self.status
        }

    def check_in(self, customer_id):
        self.customer_id = customer_id
        self.status = 'OCCUPIED'
        db.session.commit()
        return self

    def check_out(self):
        self.customer_id = None
        self.status = 'AVAILABLE'
        self.power_status = 'OFF'
        self.current_fee = 0.00
        db.session.commit()
        return self


class DetailRecord(db.Model):
    __tablename__ = 'detail_record'

    record_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    room_id = db.Column(db.String(10), db.ForeignKey('room.room_id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    duration = db.Column(db.Integer, default=0)
    fan_speed = db.Column(db.String(10), nullable=False)
    fee_rate = db.Column(db.Numeric(8, 4), nullable=False)
    fee = db.Column(db.Numeric(12, 4), default=0.0000)

    def to_dict(self):
        return {
            'record_id': self.record_id,
            'room_id': self.room_id,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration': self.duration,
            'fan_speed': self.fan_speed,
            'fee_rate': float(self.fee_rate) if self.fee_rate is not None else 0.0,
            'fee': float(self.fee) if self.fee is not None else 0.0
        }


class Invoice(db.Model):
    __tablename__ = 'invoice'

    invoice_id = db.Column(db.String(32), primary_key=True)
    room_id = db.Column(db.String(10), db.ForeignKey('room.room_id'), nullable=False)
    customer_id = db.Column(db.String(32), db.ForeignKey('customer.customer_id'), nullable=False)
    check_in_date = db.Column(db.DateTime, nullable=False)
    check_out_date = db.Column(db.DateTime, nullable=False)
    accommodation_fee = db.Column(db.Numeric(12, 2), default=0.00)
    ac_fee = db.Column(db.Numeric(12, 4), default=0.0000)
    total_amount = db.Column(db.Numeric(12, 2), default=0.00)
    create_time = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'invoice_id': self.invoice_id,
            'room_id': self.room_id,
            'customer_id': self.customer_id,
            'check_in_date': self.check_in_date.isoformat() if self.check_in_date else None,
            'check_out_date': self.check_out_date.isoformat() if self.check_out_date else None,
            'accommodation_fee': float(self.accommodation_fee) if self.accommodation_fee else None,
            'ac_fee': float(self.ac_fee) if self.ac_fee else None,
            'total_amount': float(self.total_amount) if self.total_amount else None,
            'create_time': self.create_time.isoformat() if self.create_time else None
        }