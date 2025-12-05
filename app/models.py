# Database Models
from app import db
from datetime import datetime


class Customer(db.Model):
    """
    客户表模型
    对应SQL表: customer
    """
    __tablename__ = 'customer'

    customer_id = db.Column(db.String(32), primary_key=True, comment='客户唯一标识')
    name = db.Column(db.String(50), nullable=False, comment='姓名')
    id_number = db.Column(db.String(18), nullable=False, comment='身份证号')
    phone = db.Column(db.String(11), comment='联系电话')
    registration_date = db.Column(db.DateTime, default=datetime.now, comment='注册时间')

    # 关系定义（可选，方便查询相关记录）
    rooms = db.relationship('Room', backref='customer_ref', lazy=True)
    invoices = db.relationship('Invoice', backref='customer_ref', lazy=True)

    def to_dict(self):
        """转换为字典格式"""
        return {
            'customer_id': self.customer_id,
            'name': self.name,
            'id_number': self.id_number,
            'phone': self.phone,
            'registration_date': self.registration_date.isoformat() if self.registration_date else None
        }

    def __repr__(self):
        return f'<Customer {self.customer_id}: {self.name}>'


class Room(db.Model):
    """
    房间表模型
    对应SQL表: room
    """
    __tablename__ = 'room'

    room_id = db.Column(db.String(10), primary_key=True, comment='房间号 (101-105)')
    current_temp = db.Column(db.Numeric(5, 2), default=22.00, comment='当前室温')
    target_temp = db.Column(db.Numeric(5, 2), default=22.00, comment='目标温度')
    fan_speed = db.Column(db.String(10), default='MEDIUM', comment='风速')
    power_status = db.Column(db.String(5), default='OFF', comment='开关状态')
    fee_rate = db.Column(db.Numeric(5, 2), default=1.00, comment='当前费率')
    current_fee = db.Column(db.Numeric(10, 2), default=0.00, comment='当前累计费用')
    total_fee = db.Column(db.Numeric(10, 2), default=0.00, comment='总费用')
    customer_id = db.Column(db.String(32), db.ForeignKey('customer.customer_id'), comment='入住客户ID')
    status = db.Column(db.String(20), default='AVAILABLE', comment='房间状态')

    # 关系定义
    detail_records = db.relationship('DetailRecord', backref='room_ref', lazy=True)
    invoices = db.relationship('Invoice', backref='room_ref', lazy=True)

    def to_dict(self):
        """转换为字典格式"""
        return {
            'room_id': self.room_id,
            'current_temp': float(self.current_temp) if self.current_temp else None,
            'target_temp': float(self.target_temp) if self.target_temp else None,
            'fan_speed': self.fan_speed,
            'power_status': self.power_status,
            'fee_rate': float(self.fee_rate) if self.fee_rate else None,
            'current_fee': float(self.current_fee) if self.current_fee else None,
            'total_fee': float(self.total_fee) if self.total_fee else None,
            'customer_id': self.customer_id,
            'status': self.status
        }

    def check_in(self, customer_id):
        """
        入住方法
        :param customer_id: 客户ID
        """
        self.customer_id = customer_id
        self.status = 'OCCUPIED'
        db.session.commit()
        return self

    def check_out(self):
        """退房方法"""
        self.customer_id = None
        self.status = 'AVAILABLE'
        # 可选：退房时重置空调状态
        self.power_status = 'OFF'
        self.current_fee = 0.00
        db.session.commit()
        return self

    def __repr__(self):
        return f'<Room {self.room_id}: {self.status}>'


class DetailRecord(db.Model):
    """
    详单表模型
    对应SQL表: detail_record
    """
    __tablename__ = 'detail_record'

    record_id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='流水号')
    room_id = db.Column(db.String(10), db.ForeignKey('room.room_id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False, comment='开始时间')
    end_time = db.Column(db.DateTime, comment='结束时间')
    duration = db.Column(db.Integer, default=0, comment='时长(秒)')
    fan_speed = db.Column(db.String(10), nullable=False, comment='风速')
    fee_rate = db.Column(db.Numeric(5, 2), nullable=False, comment='费率')
    fee = db.Column(db.Numeric(10, 2), default=0.00, comment='费用')

    def to_dict(self):
        """转换为字典格式"""
        return {
            'record_id': self.record_id,
            'room_id': self.room_id,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration': self.duration,
            'fan_speed': self.fan_speed,
            'fee_rate': float(self.fee_rate) if self.fee_rate else None,
            'fee': float(self.fee) if self.fee else None
        }

    def __repr__(self):
        return f'<DetailRecord {self.record_id} for Room {self.room_id}>'


class Invoice(db.Model):
    """
    账单表模型
    对应SQL表: invoice
    """
    __tablename__ = 'invoice'

    invoice_id = db.Column(db.String(32), primary_key=True)
    room_id = db.Column(db.String(10), db.ForeignKey('room.room_id'), nullable=False)
    customer_id = db.Column(db.String(32), db.ForeignKey('customer.customer_id'), nullable=False)
    check_in_date = db.Column(db.DateTime, nullable=False)
    check_out_date = db.Column(db.DateTime, nullable=False)
    accommodation_fee = db.Column(db.Numeric(10, 2), default=0.00)
    ac_fee = db.Column(db.Numeric(10, 2), default=0.00)
    total_amount = db.Column(db.Numeric(10, 2), default=0.00)
    create_time = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        """转换为字典格式"""
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

    def __repr__(self):
        return f'<Invoice {self.invoice_id} for Room {self.room_id}>'