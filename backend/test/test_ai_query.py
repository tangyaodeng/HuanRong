import json
import pymysql
import ollama
from typing import List, Dict, Optional
from datetime import datetime, timedelta

# ===================== 配置区 =====================
MYSQL_HOST = "192.168.5.43"
MYSQL_PORT = 3306
MYSQL_USER = "admin1"
MYSQL_PASSWORD = "123456"
MYSQL_DATABASE = "xm_hisdata"
MYSQL_CHARSET = "utf8mb4"

# ===================== 点位映射（请补全你需要的）=====================
POINT_MAP = {
    "室外温度": ["hrdz_zlz_ai38"],
    "主机实时功率": [
        "hrdz_zlz_ai354", "hrdz_zlz_ai362", "hrdz_zlz_ai370",
        "hrdz_zlz_ai378", "hrdz_zlz_ai386"
    ],
    "冷冻泵频率反馈": [
        "hrdz_zlz_ai169", "hrdz_zlz_ai170", "hrdz_zlz_ai171",
        "hrdz_zlz_ai172", "hrdz_zlz_ai173", "hrdz_zlz_ai174",
        "hrdz_zlz_ai175"
    ],
    # 按需补充其它点位...
}

def build_point_map_description() -> str:
    lines = ["【点位映射知识】"]
    for business_name, tags in POINT_MAP.items():
        lines.append(f"- {business_name}：点位 {', '.join(tags)}")
    return "\n".join(lines)

# ===================== 数据库查询函数 =====================
def get_point_data(business_name: str,
                   start_time: Optional[str] = None,
                   end_time: Optional[str] = None,
                   aggregation: str = "latest") -> dict:
    """查询点位数据（每点位单独一张表，表名=点位名）"""
    if business_name not in POINT_MAP:
        return {"success": False, "message": f"未知的业务名称: {business_name}"}

    tag_ids = POINT_MAP[business_name]
    if not tag_ids:
        return {"success": False, "message": "该业务名下无点位"}

    conn = pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE, charset=MYSQL_CHARSET,
        connect_timeout=3, read_timeout=5
    )
    try:
        values = []
        with conn.cursor() as cursor:
            for tag in tag_ids:
                table = tag   # 表名就是点位名
                time_condition = ""
                if start_time and end_time:
                    time_condition = f"WHERE UpdateDateTime BETWEEN '{start_time}' AND '{end_time}'"
                elif start_time:
                    time_condition = f"WHERE UpdateDateTime >= '{start_time}'"
                elif end_time:
                    time_condition = f"WHERE UpdateDateTime <= '{end_time}'"

                if aggregation == "latest":
                    sql = f"SELECT PointValue FROM `{table}` {time_condition} ORDER BY UpdateDateTime DESC LIMIT 1"
                else:
                    agg_func = aggregation.upper()
                    sql = f"SELECT {agg_func}(PointValue) AS val FROM `{table}` {time_condition}"

                try:
                    cursor.execute(sql)
                    row = cursor.fetchone()
                    if row and row[0] is not None:
                        values.append(float(row[0]))
                except Exception as e:
                    return {"success": False, "message": f"查询表 {table} 失败: {str(e)}"}

        if not values:
            return {"success": True, "data": 0.0, "message": "无数据"}

        if aggregation == "latest":
            result = sum(values) / len(values)
        elif aggregation == "avg":
            result = sum(values) / len(values)
        elif aggregation == "sum":
            result = sum(values)
        elif aggregation == "max":
            result = max(values)
        elif aggregation == "min":
            result = min(values)
        else:
            result = sum(values) / len(values)

        return {"success": True, "data": result, "message": "查询成功"}
    finally:
        conn.close()

# ===================== 工具定义（function calling）=====================
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_point_data",
            "description": (
                "查询工业点位数据。参数 business_name 必须是【点位映射知识】中的中文名称。\n"
                "start_time/end_time 格式 YYYY-MM-DD HH:MM:SS，可选。\n"
                "aggregation 可选 latest, avg, sum, max, min。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "business_name": {"type": "string", "description": "点位业务名"},
                    "start_time": {"type": "string", "description": "开始时间，格式 YYYY-MM-DD HH:MM:SS", "nullable": True},
                    "end_time": {"type": "string", "description": "结束时间，格式 YYYY-MM-DD HH:MM:SS", "nullable": True},
                    "aggregation": {"type": "string", "description": "聚合方式: latest, avg, sum, max, min", "default": "latest"}
                },
                "required": ["business_name"]
            }
        }
    }
]

# ===================== 核心对话 =====================
def chat_with_tools(user_message: str, history: List[Dict] = None) -> str:
    if history is None:
        history = []

    system_prompt = f"""你是一个工业上位机监控助手，可以查询数据库中的实时/历史数据。

{build_point_map_description()}

【数据库说明】
- 每个点位单独一张表，表名等于点位标识。
- 表字段：UpdateDateTime (时间), PointValue (数值)。

【行为准测】
- 当用户询问数据时，调用 get_point_data 工具。
- 根据【点位映射知识】确定 business_name。
- 时间范围：如“最近3天”计算 start_time 为3天前，end_time 为当前。
- 聚合方式：平均→avg，总和→sum，最大/最小→max/min，未指定则用 latest。
- 将返回的数值结合用户问题生成自然语言回答。
"""
    messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": user_message}
    ]

    print("[调试] 第一次调用 Ollama ...")
    response = ollama.chat(model='qwen3:4b', messages=messages, tools=TOOLS)
    print("[调试] 模型返回角色:", response['message'].get('role'))
    print("[调试] 是否有 tool_calls:", 'tool_calls' in response['message'])

    if response['message'].get('tool_calls'):
        tool_calls = response['message']['tool_calls']
        for tool_call in tool_calls:
            if tool_call['function']['name'] == 'get_point_data':
                args = tool_call['function']['arguments']
                print(f"[调试] 调用工具，参数: {args}")
                try:
                    result = get_point_data(
                        business_name=args.get('business_name'),
                        start_time=args.get('start_time'),
                        end_time=args.get('end_time'),
                        aggregation=args.get('aggregation', 'latest')
                    )
                    result_str = json.dumps(result, ensure_ascii=False)
                    print(f"[调试] 工具返回: {result_str}")
                except Exception as e:
                    result_str = json.dumps({"success": False, "message": str(e)})
                messages.append({"role": "tool", "content": result_str})
            else:
                messages.append({"role": "tool", "content": "未知工具调用"})

        final_response = ollama.chat(model='qwen3:4b', messages=messages)
        return final_response['message']['content']
    else:
        print("[调试] 模型未调用工具，直接返回文本：", response['message']['content'])
        return response['message']['content']

# ===================== 主程序（交互循环）=====================
if __name__ == "__main__":
    print("=" * 50)
    print("🚀 工业监控助手启动成功！")
    print(f"数据库: {MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}")
    print("已加载点位映射数:", len(POINT_MAP))
    print("输入问题（如：室外温度是多少？ 或 主机实时功率最近3天平均值），输入 exit 退出")
    print("=" * 50)

    history = []  # 多轮对话历史
    while True:
        try:
            user_input = input("\n❓ 请输入问题：")
            if user_input.strip().lower() in ('exit', 'quit'):
                print("再见！")
                break
            if not user_input.strip():
                continue

            answer = chat_with_tools(user_input, history)
            print("🤖 助手回答：", answer)

            # 保存对话上下文
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": answer})
            if len(history) > 10:
                history = history[-10:]
        except KeyboardInterrupt:
            print("\n退出程序。")
            break
        except Exception as e:
            print("❌ 运行错误：", e)
            import traceback
            traceback.print_exc()