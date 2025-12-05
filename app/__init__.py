# App Factory
from flask import Flask
from config import Config
from app.models import db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # 初始化插件
    db.init_app(app)

    # 注册蓝图 (Blueprints)
    # from app.api.auth_routes import auth_bp
    # app.register_blueprint(auth_bp, url_prefix='/api/auth')

    # 确保数据库表存在 (开发阶段偷懒做法，生产环境请用 Flask-Migrate)
    with app.app_context():
        db.create_all()
        print("✅ 数据库连接成功，表结构已检查/创建")

    return app
