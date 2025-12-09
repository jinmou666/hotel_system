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


# === CSV 导出 (Excel 友好) ===
@front_bp.route('/exportBill/<room_id>', methods=['GET'])
def export_bill(room_id):
    invoice = Invoice.query.filter_by(room_id=room_id).order_by(Invoice.create_time.desc()).first()
    if not invoice: return "No Invoice"

    output = io.StringIO()
    output.write('\ufeff')  # BOM
    writer = csv.writer(output)
    writer.writerow(['房间号', '入住时间', '离开时间', '空调费(元)', '住宿费(元)', '总费用(元)'])
    writer.writerow([
        invoice.room_id, invoice.check_in_date, invoice.check_out_date,
        f"{invoice.ac_fee:.2f}", f"{invoice.accommodation_fee:.2f}", f"{invoice.total_amount:.2f}"
    ])
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment;filename=bill_{room_id}.csv"})


@front_bp.route('/exportDetail/<room_id>', methods=['GET'])
def export_detail(room_id):
    records = DetailRecord.query.filter_by(room_id=room_id).order_by(DetailRecord.start_time).all()
    scheduler = Scheduler()
    sim_start = scheduler.simulation_start_time

    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(
        ['房间', '请求时刻(分)', '开始时刻(分)', '结束时刻(分)', '时长(s)', '风速', '费率', '费用', '累积费用'])

    cumulative = 0.0
    for r in records:
        d_start = (r.start_time - sim_start).total_seconds()
        sys_start = (d_start * SystemConstants.TIME_KX) / 60.0

        if r.end_time:
            d_end = (r.end_time - sim_start).total_seconds()
            sys_end = (d_end * SystemConstants.TIME_KX) / 60.0
        else:
            sys_end = sys_start  # 异常数据

        fee = float(r.fee) if r.fee else 0.0
        cumulative += fee

        writer.writerow([
            r.room_id, f"{sys_start:.2f}", f"{sys_start:.2f}", f"{sys_end:.2f}",
            r.duration, r.fan_speed, f"{float(r.fee_rate):.2f}", f"{fee:.2f}", f"{cumulative:.2f}"
        ])

    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment;filename=detail_{room_id}.csv"})


# === TXT 导出 (易读格式) ===
@front_bp.route('/exportBill/txt/<room_id>', methods=['GET'])
def export_bill_txt(room_id):
    invoice = Invoice.query.filter_by(room_id=room_id).order_by(Invoice.create_time.desc()).first()
    if not invoice: return "No Invoice"

    txt = f"""
========================================
          酒店入住账单 (Bill)
========================================
 房间号   : {invoice.room_id}
 客户ID   : {invoice.customer_id}
 入住时间 : {invoice.check_in_date}
 离开时间 : {invoice.check_out_date}
----------------------------------------
 空调费用 : {invoice.ac_fee:.2f} 元
 住宿费用 : {invoice.accommodation_fee:.2f} 元
----------------------------------------
 总计金额 : {invoice.total_amount:.2f} 元
========================================
"""
    return Response(txt, mimetype="text/plain",
                    headers={"Content-Disposition": f"attachment;filename=bill_{room_id}.txt"})


@front_bp.route('/exportDetail/txt/<room_id>', methods=['GET'])
def export_detail_txt(room_id):
    records = DetailRecord.query.filter_by(room_id=room_id).order_by(DetailRecord.start_time).all()
    scheduler = Scheduler()
    sim_start = scheduler.simulation_start_time

    txt = [f"=== 空调详单: Room {room_id} ==="]
    txt.append(f"{'开始(分)':<10} {'结束(分)':<10} {'时长(s)':<8} {'风速':<6} {'费用':<8} {'累积':<8}")
    txt.append("-" * 65)

    cumulative = 0.0
    for r in records:
        d_start = (r.start_time - sim_start).total_seconds()
        sys_start = (d_start * SystemConstants.TIME_KX) / 60.0

        if r.end_time:
            d_end = (r.end_time - sim_start).total_seconds()
            sys_end = (d_end * SystemConstants.TIME_KX) / 60.0
        else:
            sys_end = 0.0

        fee = float(r.fee) if r.fee else 0.0
        cumulative += fee

        line = f"{sys_start:<10.2f} {sys_end:<10.2f} {r.duration:<8} {r.fan_speed:<6} {fee:<8.2f} {cumulative:<8.2f}"
        txt.append(line)

    return Response("\n".join(txt), mimetype="text/plain",
                    headers={"Content-Disposition": f"attachment;filename=detail_{room_id}.txt"})