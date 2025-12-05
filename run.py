from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config

# 初始化数据库对象 (全局单例)
db = SQLAlchemy()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    # --- 注册蓝图 (Controller) ---
    # 注意：组员写好代码后，需要在这里取消注释来启用功能

    # from controllers.ac_controller import ac_bp
    # app.register_blueprint(ac_bp, url_prefix='/api/ac')

    # from controllers.front_controller import front_bp
    # app.register_blueprint(front_bp, url_prefix='/api/front')

    return app


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        # 确保数据库表已根据 models 创建 (郑员杰的工作成果将在此生效)
        db.create_all()
        print(">>> System initialized successfully.")

    app.run(debug=True, port=5000)