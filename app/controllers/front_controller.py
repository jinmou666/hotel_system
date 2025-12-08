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
    if not invoice:
        return jsonify({'code': 500, 'msg': 'Failed to create invoice'})

    Room.query.get(room_id).check_out()
    return jsonify({'code': 200, 'msg': 'Check-out Success', 'data': invoice.to_dict()})


@front_bp.route('/exportBill/<room_id>', methods=['GET'])
def export_bill(room_id):
    """导出账单(标准格式)"""
    invoice = Invoice.query.filter_by(room_id=room_id).order_by(Invoice.create_time.desc()).first()
    if not invoice: return "No Invoice"

    # 模拟住宿费：假设不同房间价格不同，从配置读取或硬编码演示
    # 简单逻辑：总金额 = 空调费 + 住宿费(这里简单设为100元演示)
    # 若 BillService 已经计算了，直接用

    output = io.StringIO()
    # 写入BOM头防止Excel中文乱码
    output.write('\ufeff')
    writer = csv.writer(output)

    writer.writerow(['房间号', '入住时间', '离开时间', '空调总费用(元)', '房间费用(元)', '总费用(元)'])
    writer.writerow([
        invoice.room_id,
        invoice.check_in_date,
        invoice.check_out_date,
        f"{invoice.ac_fee:.2f}",
        f"{invoice.accommodation_fee:.2f}",
        f"{invoice.total_amount:.2f}"
    ])

    output.seek(0)
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=bill_{room_id}.csv"}
    )


@front_bp.route('/exportDetail/<room_id>', methods=['GET'])
def export_detail(room_id):
    """导出详单(含系统时间转换)"""
    records = DetailRecord.query.filter_by(room_id=room_id).order_by(DetailRecord.start_time).all()

    scheduler = Scheduler()
    sim_start = scheduler.simulation_start_time

    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(
        ['房间号', '请求时间(系统分)', '服务开始(系统分)', '服务结束(系统分)', '服务时长(秒)', '风速', '当前费用',
         '累积费用'])

    cumulative_fee = 0.0

    for r in records:
        # 计算系统时间 (分钟) = (现实时间差秒数 * 倍速) / 60
        # 请求时间 ≈ 服务开始时间 (简化)

        # 1. 计算相对现实秒数
        delta_start = (r.start_time - sim_start).total_seconds()
        sys_start_min = (delta_start * SystemConstants.TIME_KX) / 60.0

        sys_end_min = 0
        if r.end_time:
            delta_end = (r.end_time - sim_start).total_seconds()
            sys_end_min = (delta_end * SystemConstants.TIME_KX) / 60.0
        else:
            # 如果未结束（异常情况），暂按当前时间算
            delta_end = (datetime.now() - sim_start).total_seconds()
            sys_end_min = (delta_end * SystemConstants.TIME_KX) / 60.0

        # 累积费用
        fee = float(r.fee) if r.fee else 0.0
        cumulative_fee += fee

        writer.writerow([
            r.room_id,
            f"{sys_start_min:.2f}",  # 请求时间
            f"{sys_start_min:.2f}",  # 开始时间
            f"{sys_end_min:.2f}",  # 结束时间
            r.duration,
            r.fan_speed,
            f"{fee:.2f}",
            f"{cumulative_fee:.2f}"
        ])

    output.seek(0)
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=detail_{room_id}.csv"}
    )