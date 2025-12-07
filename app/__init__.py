from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from config import Config

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # 1. 初始化插件
    db.init_app(app)
    # 允许跨域
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # 2. 注册蓝图
    # 放在函数内部避免循环导入
    from app.controllers.ac_controller import ac_bp
    from app.controllers.front_controller import front_bp

    app.register_blueprint(ac_bp, url_prefix='/api/ac')
    app.register_blueprint(front_bp, url_prefix='/api/front')

    return app