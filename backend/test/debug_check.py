import time

print("=" * 50)
print("1. 检查 ollama 连接...")
import ollama
import sys

print("正在测试 Ollama 聊天接口...")
try:
    # 直接发一条简单消息，不涉及工具，验证连通性
    test_response = ollama.chat(
        model='qwen3:4b',
        messages=[{'role': 'user', 'content': '回复OK即可，不要多余文字'}]
    )
    content = test_response['message']['content']
    print(f"✅ Ollama 可用，回复：{content}")
except Exception as e:
    print(f"❌ Ollama 测试失败：{e}")
    sys.exit(1)

print("测试结束，Ollama 正常。")

print("\n2. 检查数据库连接...")
import pymysql
try:
    conn = pymysql.connect(
        host="192.168.5.43",
        port=3306,
        user="admin1",
        password="123456",
        database="xm_hisdata",
        charset="utf8mb4",
        connect_timeout=5
    )
    print("✅ 数据库连接成功")
    # 查看一下数据库里有哪些表，确认表名规则
    with conn.cursor() as cur:
        cur.execute("SHOW TABLES")
        tables = cur.fetchall()
        print(f"   数据库中有 {len(tables)} 张表，前5张表名：{tables[:5]}")
    conn.close()
except Exception as e:
    print("❌ 数据库连接失败：", e)

print("=" * 50)
input("按回车键退出...")