# backend/app/utils/trainer_utils.py
import os
import re
import shutil
from pathlib import Path

# 项目根目录（请根据实际项目结构调整）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # 例如 backend/../../
TRAINERS_DIR = PROJECT_ROOT / "ml" / "models" / "trainers"
TEMPLATE_FILE = "deviceid_xgboost_v1.py"  # 模板文件名

def trainer_file_exists(device_id: int) -> bool:
    """检查指定设备的训练器文件是否存在"""
    filename = f"device{device_id}_xgboost_v1.py"
    return (TRAINERS_DIR / filename).exists()

def generate_trainer_file(device_id: int) -> str:
    """
    从模板文件复制并替换占位符，生成目标训练器文件
    返回：目标文件的相对路径（如 ml/models/trainers/device9_xgboost_v1.py）
    """
    template_path = TRAINERS_DIR / TEMPLATE_FILE
    if not template_path.exists():
        raise FileNotFoundError(f"模板文件不存在: {template_path}")

    target_filename = f"device{device_id}_xgboost_v1.py"
    target_path = TRAINERS_DIR / target_filename

    if target_path.exists():
        # 如果已存在，直接返回（可根据需求决定是否覆盖）
        return str(target_path.relative_to(PROJECT_ROOT))

    # 读取模板内容
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 替换占位符（假设模板中使用 deviceid 作为占位）
    content = content.replace("deviceid", f"device{device_id}")
    # 根据需要替换其他可能的占位符，如类名等
    content = content.replace("Deviceid", f"Device{device_id}")

    # 写入目标文件
    with open(target_path, 'w', encoding='utf-8') as f:
        f.write(content)

    # 返回相对于项目根的路径，用于数据库存储
    relative_path = str(target_path.relative_to(PROJECT_ROOT))
    return relative_path