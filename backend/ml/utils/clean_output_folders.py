#backend/utils/clean_output_folders.py
"""
批量清理 output 目录下所有项目-设备文件夹中的旧数据文件夹，
每个项目-设备文件夹只保留最新的 N 个（默认 5 个）。
"""
import os
import sys
import shutil
import argparse
from pathlib import Path

# 添加项目根目录到 sys.path（根据需要调整）
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(backend_dir)
sys.path.insert(0, project_root)

# 引入文件处理器（或者直接实现清理逻辑）
from ml.data.file_processing import FileProcessor


def clean_all_output_folders(base_data_dir: str = None, max_keep: int = 5):
    """
    遍历 output 目录下的所有项目-设备文件夹，清理旧的 data_* 子文件夹
    """
    if base_data_dir is None:
        # 使用与 FileProcessor 相同的默认路径逻辑
        processor = FileProcessor()
        base_data_dir = processor.base_data_dir

    output_dir = os.path.join(base_data_dir, 'output')
    if not os.path.isdir(output_dir):
        print(f"输出目录不存在: {output_dir}")
        return

    # 获取所有项目-设备文件夹（格式：{project}_{device}）
    project_device_dirs = [
        d for d in os.listdir(output_dir)
        if os.path.isdir(os.path.join(output_dir, d))
    ]

    if not project_device_dirs:
        print("没有找到任何项目-设备文件夹。")
        return

    print(f"开始清理 output 目录，保留每个项目-设备文件夹下最新的 {max_keep} 个 data_* 文件夹。")
    total_deleted = 0

    for folder_name in project_device_dirs:
        folder_path = os.path.join(output_dir, folder_name)
        print(f"\n处理: {folder_name}")

        # 获取所有 data_* 子文件夹
        subdirs = [
            d for d in os.listdir(folder_path)
            if os.path.isdir(os.path.join(folder_path, d)) and d.startswith("data_")
        ]

        if len(subdirs) <= max_keep:
            print(f"  现有 {len(subdirs)} 个，无需清理。")
            continue

        subdirs.sort(reverse=True)  # 最新的在前
        to_delete = subdirs[max_keep:]
        print(f"  将删除 {len(to_delete)} 个旧文件夹: {', '.join(to_delete)}")

        for sub in to_delete:
            full_path = os.path.join(folder_path, sub)
            try:
                shutil.rmtree(full_path)
                total_deleted += 1
                print(f"    ✅ 已删除: {sub}")
            except Exception as e:
                print(f"    ❌ 删除失败 {sub}: {e}")

    print(f"\n清理完成，共删除 {total_deleted} 个文件夹。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="清理 output 目录下的旧数据文件夹")
    parser.add_argument("--base_data_dir", type=str, default=None,
                        help="基础数据目录，默认为项目根目录下的 data")
    parser.add_argument("--max_keep", type=int, default=5,
                        help="每个项目-设备文件夹下保留的最新的文件夹数量，默认 5")
    args = parser.parse_args()

    clean_all_output_folders(args.base_data_dir, args.max_keep)