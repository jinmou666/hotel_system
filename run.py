from app import create_app, db
# 【关键】必须导入 models，否则 SQLAlchemy 扫描不到表结构，create_all() 会失效
from app import models

# 从 app 包中创建应用实例
app = create_app()

if __name__ == '__main__':
    with app.app_context():
        # 尝试创建所有表 (如果表已存在则忽略)
        db.create_all()
        print(">>> Database tables checked/created successfully.")
        print(">>> System running on http://127.0.0.1:5000")

    app.run(debug=True, port=5000)