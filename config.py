import os


class Config:
    # 数据库连接 (组员需在各自电脑修改密码)
    # 格式 : mysql+pymysql://用户名:密码@地址:端口/数据库名
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:147258369@localhost/hotel_ac_system'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'bupt_se_project_secret'


class SystemConstants:
    """
    验收专用参数配置 - 严禁硬编码，必须引用此处常量
    """
    # 时间倍速：10秒(现实) = 1分钟(系统) -> 6倍速
    # 用于 Scheduler 计算 duration
    TIME_SCALE = 60

    # 时间片长度：2分钟 (对应 Excel 调度策略)
    # 单位：系统时间秒数 (2 * 60 = 120秒)
    TIME_SLICE = 120

    # 费率配置 (元/分钟? 需根据Excel确认，此处假设元/度，结合温控算法换算)
    # Excel 写的是 1元/1度。
    # 高风: 1度/1分钟 -> 1元/分钟
    # 中风: 1度/2分钟 -> 0.5元/分钟
    # 低风: 1度/3分钟 -> 0.33元/分钟
    FEE_RATE_HIGH = 1.0
    FEE_RATE_MID = 0.5
    FEE_RATE_LOW = 0.33

    # 回温参数
    RECOVER_RATE = 0.5  # 每分钟回温0.5度

    # 制冷模式 (Cooling) - 对应 Excel 冷
    COOL_MODE_DEFAULTS = {
        'default_target': 25.0,
        'temp_limit_min': 18.0,
        'temp_limit_max': 28.0,
        'rooms': {
            '101': 32.0, '102': 28.0, '103': 30.0, '104': 29.0, '105': 35.0
        }
    }

    # 制热模式 (Heating) - 对应 Excel 热
    HEAT_MODE_DEFAULTS = {
        'default_target': 23.0,
        'temp_limit_min': 18.0,
        'temp_limit_max': 25.0,
        'rooms': {
            '101': 10.0, '102': 15.0, '103': 18.0, '104': 12.0, '105': 14.0
        }
    }