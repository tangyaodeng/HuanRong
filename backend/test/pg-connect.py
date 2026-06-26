# backend/test/pg-connect.py
import sys
import os
from sqlalchemy import create_engine, text
# 将父目录（backend）添加到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 现在可以导入app模块
from app.config import settings


def test_connection():
    print(f"正在尝试连接数据库...")
    print(f"连接字符串: {settings.DATABASE_URL.replace('123456', '******')}")  # 隐藏密码打印

    try:
        # 创建引擎，设置echo=True可以在控制台看到执行的SQL，便于调试
        engine = create_engine(settings.DATABASE_URL, echo=True)

        # 尝试建立连接并执行一个简单查询
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print("✅ 数据库连接成功！")
            print(f"测试查询结果: {result.fetchone()}")
            return True

    except Exception as e:
        print(f"❌ 数据库连接失败！")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误详情: {e}")
        return False


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)