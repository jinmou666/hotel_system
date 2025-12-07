import os

class Config:
    # 数据库连接 - ⚠️ 关键修改：在末尾添加 ?charset=utf8mb4
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:147258369@localhost/hotel_ac_system?charset=utf8mb4'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'bupt_se_project_secret'

class SystemConstants:
    """
    系统核心参数配置 - 严格对应验收 Excel
    """
    # 1. 时间比例 (10秒现实 = 1分钟系统 -> 6倍速)
    TIME_KX = 6

    # 2. 调度限制
    MAX_SERVICE = 3
    MAX_WAIT = 2
    TIME_SLICE = 120

    # 3. 费率 (元/分钟)
    FEE_RATE_HIGH = 1.0
    FEE_RATE_MID = 0.5
    FEE_RATE_LOW = 1.0 / 3.0

    # 4. 温度变化率 (度/分钟)
    TEMP_XH_HIGH = 1.0
    TEMP_XH_MID = 0.5
    TEMP_XH_LOW = 1.0 / 3.0

    # 回温速率
    RECOVER_RATE = 0.5

    # 5. 模式默认参数
    COOL_MODE_DEFAULTS = {
        'default_target': 25.0,
        'temp_limit_min': 18.0,
        'temp_limit_max': 28.0,
        'initial_temps': {
            '101': 32.0, '102': 28.0, '103': 30.0, '104': 29.0, '105': 35.0
        }
    }

    HEAT_MODE_DEFAULTS = {
        'default_target': 23.0,
        'temp_limit_min': 18.0,
        'temp_limit_max': 25.0,
        'initial_temps': {
            '101': 10.0, '102': 15.0, '103': 18.0, '104': 12.0, '105': 14.0
        }
    }