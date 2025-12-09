from flask import Blueprint, request, jsonify, Response
from app import db
from app.models import Room, Customer, Invoice, DetailRecord
from app.services.bill_service import BillService
from app.core.scheduler import Scheduler
from config import SystemConstants
import csv
import io
from datetime import datetime

front_bp = Blueprint('front_bp', __name__)


@front_bp.route('/checkIn', methods=['POST'])
def check_in():
    data = request.get_json()
    room_id = data.get('room_id')
    customer_id = data.get('customer_id')
    id_number = data.get('id_number')
    room = Room.query.get(room_id)
    if not room: return jsonify({'code': 404, 'msg': 'No Room'})
    customer = Customer.query.get(customer_id)
    if not customer:
        customer = Customer(customer_id=customer_id, name="Guest", id_number=id_number)
        db.session.add(customer)
    room.check_in(customer_id)
    return jsonify({'code': 200, 'msg': 'Check-in Success'})


@front_bp.route('/checkOut', methods=['POST'])
def check_out():
    data = request.get_json()
    room_id = data.get('room_id')
    invoice = BillService.create_invoice(room_id)
    if not invoice: return jsonify({'code': 500, 'msg': 'Failed'})
    Room.query.get(room_id).check_out()
    return jsonify({'code': 200, 'msg': 'Success', 'data': invoice.to_dict()})


@front_bp.route('/exportBill/<room_id>', methods=['GET'])
def export_bill(room_id):
    invoice = Invoice.query.filter_by(room_id=room_id).order_by(Invoice.create_time.desc()).first()
    if not invoice: return "No Invoice"

    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(['房间号', '入住时间', '离开时间', '入住天数', '空调费', '住宿费', '总费用'])
    writer.writerow([
        invoice.room_id,
        invoice.check_in_date.strftime('%Y-%m-%d %H:%M:%S'),
        invoice.check_out_date.strftime('%Y-%m-%d %H:%M:%S'),
        invoice.stay_days,
        f"{invoice.ac_fee:.2f}", f"{invoice.accommodation_fee:.2f}", f"{invoice.total_amount:.2f}"
    ])
    return Response(output.getvalue().encode('gbk', 'ignore'), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment;filename=bill_{room_id}.csv"})


@front_bp.route('/exportDetail/<room_id>', methods=['GET'])
def export_detail(room_id):
    records = DetailRecord.query.filter_by(room_id=room_id).order_by(DetailRecord.start_time).all()
    scheduler = Scheduler()
    sim_start = scheduler.simulation_start_time

    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(['房间', '请求时刻(分)', '开始(分)', '结束(分)', '时长(s)', '风速', '费率', '费用', '累积'])

    cumulative = 0.0
    for r in records:
        d_start = (r.start_time - sim_start).total_seconds()
        sys_start = (d_start * SystemConstants.TIME_KX) / 60.0
        if sys_start < 0: sys_start = 0.0  # Clamp negative

        duration_sec = float(r.duration)
        sys_end = sys_start + (duration_sec / 60.0)  # 强制自洽

        fee = float(r.fee) if r.fee else 0.0
        cumulative += fee

        writer.writerow([
            r.room_id, f"{sys_start:.2f}", f"{sys_start:.2f}", f"{sys_end:.2f}",
            f"{duration_sec:.0f}", r.fan_speed, f"{float(r.fee_rate):.2f}", f"{fee:.2f}", f"{cumulative:.2f}"
        ])

    return Response(output.getvalue().encode('gbk', 'ignore'), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment;filename=detail_{room_id}.csv"})