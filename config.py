import os

class Config:
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:147258369@localhost/hotel_ac_system?charset=utf8mb4'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'bupt_se_project_secret'
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,
        'max_overflow': 40,
        'pool_recycle': 1800,
        'pool_pre_ping': True
    }

class SystemConstants:
    """
    系统核心参数配置
    """
    TIME_KX = 6.0
    MAX_SERVICE = 3
    MAX_WAIT = 2
    TIME_SLICE = 120

    FEE_RATE_HIGH = 1.0
    FEE_RATE_MID = 0.5
    FEE_RATE_LOW = 1.0 / 3.0

    TEMP_XH_HIGH = 1.0
    TEMP_XH_MID = 0.5
    TEMP_XH_LOW = 1.0 / 3.0

    RECOVER_RATE = 0.5

    # === 新增：房间日租金配置 ===
    ROOM_DAILY_RATES = {
        '101': 100.0,
        '102': 125.0,
        '103': 150.0,
        '104': 200.0,
        '105': 100.0
    }

    COOL_MODE_DEFAULTS = {
        'default_target': 25.0,
        'temp_limit_min': 18.0,
        'temp_limit_max': 28.0,
        'initial_temps': {
            101: 32.0, '101': 32.0,
            102: 28.0, '102': 28.0,
            103: 30.0, '103': 30.0,
            104: 29.0, '104': 29.0,
            105: 35.0, '105': 35.0
        }
    }

    HEAT_MODE_DEFAULTS = {
        'default_target': 23.0,
        'temp_limit_min': 18.0,
        'temp_limit_max': 25.0,
        'initial_temps': {
            101: 10.0, '101': 10.0,
            102: 15.0, '102': 15.0,
            103: 18.0, '103': 18.0,
            104: 12.0, '104': 12.0,
            105: 14.0, '105': 14.0
        }
    }