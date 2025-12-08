from flask import Blueprint, request, jsonify
from app.core.scheduler import Scheduler
from app.models import Room

ac_bp = Blueprint('ac_bp', __name__)


@ac_bp.route('/roomState/<room_id>', methods=['GET'])
def get_room_state(room_id):
    room = Room.query.get(room_id)
    if not room: return jsonify({'code': 404})

    data = room.to_dict()
    scheduler = Scheduler()
    data['sched_status'] = scheduler.get_scheduling_status(room_id)
    return jsonify(data)


@ac_bp.route('/setMode', methods=['POST'])
def set_mode():
    data = request.get_json()
    mode = data.get('mode', 'COOL')
    Scheduler().reset_mode(mode)
    return jsonify({'code': 200, 'msg': f'Reset to {mode} (Paused)'})


# === 新增：启动物理引擎 ===
@ac_bp.route('/startSimulation', methods=['POST'])
def start_simulation():
    Scheduler().resume_simulation()
    return jsonify({'code': 200, 'msg': 'Simulation Started'})


@ac_bp.route('/stopSimulation', methods=['POST'])
def stop_simulation():
    Scheduler().pause_simulation()
    return jsonify({'code': 200, 'msg': 'Simulation Paused'})


@ac_bp.route('/togglePower/<room_id>', methods=['POST'])
def toggle_power(room_id):
    data = request.get_json()
    power_status = data.get('power_status')

    scheduler = Scheduler()
    room = Room.query.get(room_id)

    if power_status == 'ON':
        target = data.get('target_temp', room.target_temp)
        fan = data.get('fan_speed', room.fan_speed)
        scheduler.request_power(room_id, fan, target)
    else:
        scheduler.stop_power(room_id)
    return jsonify({'code': 200, 'msg': 'success'})


@ac_bp.route('/setTemp/<room_id>', methods=['POST'])
def set_temp(room_id):
    data = request.get_json()
    target_temp = data.get('target_temp')
    room = Room.query.get(room_id)
    Scheduler().request_power(room_id, room.fan_speed, target_temp)
    return jsonify({'code': 200, 'msg': 'success'})


@ac_bp.route('/setFanSpeed/<room_id>', methods=['POST'])
def set_fan_speed(room_id):
    data = request.get_json()
    fan_speed = data.get('fan_speed')
    room = Room.query.get(room_id)
    Scheduler().request_power(room_id, fan_speed, room.target_temp)
    return jsonify({'code': 200, 'msg': 'success'})