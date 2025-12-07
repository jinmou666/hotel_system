from flask import Blueprint, request, jsonify
from app.core.scheduler import Scheduler
from app.models import Room

ac_bp = Blueprint('ac_bp', __name__)


@ac_bp.route('/roomState/<room_id>', methods=['GET'])
def get_room_state(room_id):
    room = Room.query.get(room_id)
    if not room: return jsonify({'code': 404})

    data = room.to_dict()
    # 注入实时调度状态
    scheduler = Scheduler()
    sched_status = scheduler.get_scheduling_status(room_id)

    # 组合显示逻辑：
    # 如果关机 -> OFF
    # 如果开机且在服务 -> RUNNING
    # 如果开机但在等待 -> WAITING
    if room.power_status == 'OFF':
        data['sched_status'] = 'OFF'
    else:
        data['sched_status'] = sched_status

    return jsonify(data)


@ac_bp.route('/setMode', methods=['POST'])
def set_mode():
    data = request.get_json()
    mode = data.get('mode', 'COOL')
    Scheduler().reset_mode(mode)
    return jsonify({'code': 200, 'msg': f'Reset to {mode}'})


@ac_bp.route('/togglePower/<room_id>', methods=['POST'])
def toggle_power(room_id):
    data = request.get_json()
    power_status = data.get('power_status')

    scheduler = Scheduler()
    room = Room.query.get(room_id)

    if power_status == 'ON':
        # 补全参数，防止前端传空
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