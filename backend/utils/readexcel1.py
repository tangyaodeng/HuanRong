#cd backend/utils
#python readexcel.py
#名称 huanrong apikey xMjK_d7o5ufijtg0r9pdufj80   appid 20260428002603459  密钥 jThB6Z_OV_Nf6ZE8GS6q

import pandas as pd
import requests
import random
import hashlib
import re
import os
import sys
import time

# ===== 百度通用翻译配置 =====
BAIDU_APPID = "20260428002603459"
BAIDU_SECRET_KEY = "jThB6Z_OV_Nf6ZE8GS6q"
# =============================

excel_path = r"D:\桌面\Ai预测\环荣项目\环荣511.xlsx"
txt_path = os.path.join(os.path.dirname(excel_path), "环荣511(1).txt")

# ---------- 需要读取的工作表列表（请根据实际名称修改）----------
SHEET_NAMES = [
    "DB10-432DI(读）",
    "DB12-680AI(读)",      # 注意原名称中的全角括号，保持与 Excel 中完全一致
]
# ----------------------------------------------------------------

# 本地备选映射表（可按需扩充，避免API调用失败导致输出空白）
FALLBACK_MAP = {
    "室外温度": "outdoor_temperature",
    "室外湿度": "outdoor_humidity",
    "湿球温度": "wet_bulb_temperature",
    "冷冻水总管供水温度": "total_chilled_inlet_temp",
    "冷冻水总管回水温度": "total_chilled_return_temp",
    "室内温度1": "indoor_temperature_1",
    "室内湿度1": "indoor_humidity_1",
    # 继续添加你Excel中反复出现的术语...
}

def baidu_translate(text: str, from_lang: str = "zh", to_lang: str = "en", retries=3) -> str:
    """调用百度通用翻译API，支持重试"""
    salt = str(random.randint(32768, 65536))
    sign_str = BAIDU_APPID + text + salt + BAIDU_SECRET_KEY
    sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest()

    url = "https://api.fanyi.baidu.com/api/trans/vip/translate"
    params = {
        "q": text,
        "from": from_lang,
        "to": to_lang,
        "appid": BAIDU_APPID,
        "salt": salt,
        "sign": sign,
    }

    for attempt in range(retries):
        resp = requests.get(url, params=params, timeout=10)
        result = resp.json()

        if "trans_result" in result:
            return result["trans_result"][0]["dst"]
        elif "error_code" in result:
            code = result["error_code"]
            if code == "54003":           # 频率限制，等待后重试
                wait = 3 + attempt * 2
                print(f"  频率限制，{wait}秒后重试...")
                time.sleep(wait)
                continue
            else:
                raise Exception(f"百度翻译失败：{result}")
    raise Exception("重试多次仍失败")

def to_snake_case(text: str) -> str:
    """英文文本转为 snake_case 变量名"""
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip().lower()
    return text.replace(' ', '_')

if not os.path.exists(excel_path):
    print(f"❌ 找不到文件：{excel_path}")
    sys.exit(1)

# 尝试读取所有指定的工作表，忽略不存在的工作表
all_lines = []
for sheet in SHEET_NAMES:
    try:
        df = pd.read_excel(excel_path, sheet_name=sheet, header=None)
    except ValueError as e:
        print(f"⚠️ 工作表 '{sheet}' 不存在或无法读取，跳过。错误：{e}")
        continue

    # 从第2行开始取 A(0) 和 F(5) 列
    df_data = df.iloc[1:, [0, 5]].copy()
    df_data.columns = ["A", "F"]
    df_data.dropna(subset=["F"], inplace=True)
    df_data["F"] = df_data["F"].astype(str).str.strip()

    sheet_lines = []
    for _, row in df_data.iterrows():
        a_val = row["A"]
        f_val = row["F"]
        if not a_val or pd.isna(a_val):
            continue

        # --- 获取英文变量名 ---
        if f_val in FALLBACK_MAP:
            var_name = FALLBACK_MAP[f_val]
        else:
            try:
                english = baidu_translate(f_val)
                var_name = to_snake_case(english)
            except Exception as e:
                print(f"⚠️ 翻译失败：{f_val}，错误：{e}，使用拼音占位符")
                safe_suffix = re.sub(r'[^\w]', '_', f_val)
                var_name = f"unknown_{safe_suffix}"

        # 行内容：变量赋值 + 注释（含工作表和原始中文）
        line = f'{var_name}: str = "{a_val}"  # {f_val}'
        sheet_lines.append(line)

        # 控制请求频率，每秒大约1~2次
        time.sleep(0.6)

    print(f"📋 工作表 '{sheet}' 处理完成，有效行数：{len(sheet_lines)}")
    all_lines.extend(sheet_lines)

# 写入文件（覆盖）
with open(txt_path, "w", encoding="utf-8") as f:
    f.write("\n".join(all_lines))

print(f"✅ 全部完成，共处理 {len(all_lines)} 行，输出：{txt_path}")