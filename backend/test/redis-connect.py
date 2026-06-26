import redis

r = redis.Redis(
    host='192.168.5.240',
    port=6379,
    password='123456',      # 必须提供密码
    decode_responses=True
)

try:
    r.ping()
    print("✅ 连接成功")
    cooling_opt = r.get('cooling_opt')
    chilled_opt = r.get('chilled_opt')
    print(f'cooling_opt: {cooling_opt}')
    print(f'chilled_opt: {chilled_opt}')
except redis.ConnectionError as e:
    print(f"❌ 连接失败: {e}")