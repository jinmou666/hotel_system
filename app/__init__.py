# App Factory
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config

# 核心修复：在此处创建全局的 db 实例
db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # 初始化插件
    db.init_app(app)

    # 注册蓝图 (Blueprints)
    # 为避免未来循环导入，蓝图导入应放在此处（函数内部）
    # 使用try-except确保部分蓝图未创建时应用仍能启动
    try:
        from app.controllers.front_controller import front_bp
        app.register_blueprint(front_bp, url_prefix='/api/front')
    except ImportError:
        print("ℹ️  前端控制器未就绪，跳过注册")

    try:
        from app.controllers.ac_controller import ac_bp
        app.register_blueprint(ac_bp, url_prefix='/api/ac')
    except ImportError:
        print("ℹ️  空调控制器未就绪，跳过注册")

    # 确保数据库表存在 (开发阶段)
    with app.app_context():
        db.create_all()
        print("✅ 数据库连接成功，表结构已检查/创建")

    return app
