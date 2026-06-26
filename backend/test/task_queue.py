# backend/test/task_queue.py
import sys
import os
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.task_queue_manager import get_task_queue_manager
from app.services.scheduler import get_scheduler

# 初始化调度器（会自动启动队列管理器）
scheduler = get_scheduler()
scheduler.start()   # 启动调度器和任务队列

# 等待几秒让线程完全启动
time.sleep(2)

# 获取队列管理器实例
queue = get_task_queue_manager()
status = queue.get_queue_status()

print("任务队列状态:")
print(f"  运行中: {status['is_running']}")
print(f"  队列大小: {status['queue_size']}")
print(f"  活动训练任务数: {status['active_train_count']}")
print(f"  活动预测任务数: {status['active_predict_count']}")
print(f"  活动任务详情: {status['active_tasks']}")

# 停止调度器（可选）
# scheduler.stop()