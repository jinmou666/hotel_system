from flask import Blueprint, request, jsonify
# 假设 Scheduler 在 app.core.scheduler 中定义，且为单例模式
# 注意：如果运行时报错找不到 app.core.scheduler，请确认该文件是否存在
from app.core.scheduler import Scheduler

# 定义 Blueprint
ac_bp = Blueprint('ac_bp', __name__)

@ac_bp.route('/powerOn', methods=['POST'])
def power_on():
    """
    开机接口
    接收 JSON: { "roomId": 1, "targetTemp": 25, "fanSpeed": 2 }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'code': 400, 'msg': 'No data provided', 'data': None})

        room_id = data.get('roomId')
        target_temp = data.get('targetTemp')
        fan_speed = data.get('fanSpeed')

        # 调用调度器请求供电 (不直接操作数据库)
        # 假设 request_power 返回的是调度结果或相关数据
        scheduler = Scheduler()
        result = scheduler.request_power(room_id, fan_speed, target_temp)

        return jsonify({
            'code': 200,
            'msg': 'success',
            'data': result
        })

    except Exception as e:
        print(f"Error in powerOn: {e}")
        return jsonify({'code': 500, 'msg': str(e), 'data': None})


@ac_bp.route('/changeState', methods=['POST'])
def change_state():
    """
    调节状态接口 (调温/调风速)
    接收 JSON: { "roomId": 1, "targetTemp": 26, "fanSpeed": 1 }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'code': 400, 'msg': 'No data provided', 'data': None})

        room_id = data.get('roomId')
        target_temp = data.get('targetTemp')
        fan_speed = data.get('fanSpeed')

        # 调用调度器修改状态
        scheduler = Scheduler()
        result = scheduler.change_state(room_id, fan_speed, target_temp)

        return jsonify({
            'code': 200,
            'msg': 'success',
            'data': result
        })

    except Exception as e:
        print(f"Error in changeState: {e}")
        return jsonify({'code': 500, 'msg': str(e), 'data': None})