from flask import Blueprint, request, jsonify, Response
from app import db
from app.models import Room, Customer, Invoice, DetailRecord
from app.services.bill_service import BillService
import csv
import io

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
    """导出账单(含住宿费、空调费)"""
    invoice = Invoice.query.filter_by(room_id=room_id).order_by(Invoice.create_time.desc()).first()
    if not invoice: return "No Invoice"

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['InvoiceID', 'Room', 'Customer', 'CheckIn', 'CheckOut', 'AccomFee', 'ACFee', 'Total'])
    writer.writerow([
        invoice.invoice_id, invoice.room_id, invoice.customer_id,
        invoice.check_in_date, invoice.check_out_date,
        invoice.accommodation_fee, invoice.ac_fee, invoice.total_amount
    ])

    output.seek(0)
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=bill_{room_id}.csv"}
    )


@front_bp.route('/exportDetail/<room_id>', methods=['GET'])
def export_detail(room_id):
    """导出详单(所有开关机、调风记录)"""
    records = DetailRecord.query.filter_by(room_id=room_id).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['RecordID', 'Room', 'StartTime', 'EndTime', 'Duration', 'FanSpeed', 'FeeRate', 'Fee'])

    for r in records:
        writer.writerow([
            r.record_id, r.room_id, r.start_time, r.end_time,
            r.duration, r.fan_speed, r.fee_rate, r.fee
        ])

    output.seek(0)
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=detail_{room_id}.csv"}
    )