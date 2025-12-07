from app import create_app, db
from app import models  # 确保模型被加载

app = create_app()
# 绑定 app 到 db，供 Scheduler 线程使用
db.app = app

if __name__ == '__main__':
    with app.app_context():
        # 这将触发 init.sql 中定义的表结构创建（包含 DROP TABLE）
        db.create_all()

        # 启动调度器
        from app.core.scheduler import Scheduler

        scheduler = Scheduler()

        print(">>> System Initialized.")
        print(">>> 1. Call POST /api/ac/setMode to reset.")
        print(">>> 2. 10s Real Time = 1min System Time.")

    # use_reloader=False 防止线程启动两次
    app.run(debug=True, port=5000, use_reloader=False)