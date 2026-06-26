import pickle
import glob
import os
from datetime import datetime

# 查找匹配前缀的模型文件
pattern = 'xgboost_device_7_hourly_cooling_energy_*.pkl'
files = glob.glob(pattern)
if not files:
    print("未找到匹配的模型文件")
    exit()

# 按文件修改时间排序，取最新的
latest_file = max(files, key=os.path.getmtime)
print(f"加载最新模型: {latest_file}")

with open(latest_file, 'rb') as f:
    data = pickle.load(f)

print("Keys:", data.keys())
print("target_mean:", data.get('target_mean'))
print("target_std:", data.get('target_std'))
print("training_stats keys:", data.get('training_stats', {}).keys())
print("standardization_stats:", data.get('training_stats', {}).get('standardization_stats'))