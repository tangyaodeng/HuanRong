"""
独立调度器启动脚本
单独启动 TrainingScheduler（不启动 FastAPI），方便在独立终端运行
用法: python backend/run_scheduler.py [--log-level INFO|WARNING|DEBUG]
"""
import sys
import os
import time
import signal
import argparse
import logging
from datetime import datetime

# 确保项目根目录在 sys.path 中
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 解决 Windows 中文路径编码问题
os.environ['JOBLIB_TEMP_FOLDER'] = 'C:\\temp_joblib'
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'
os.environ["PYTHONUNBUFFERED"] = "1"
sys.setrecursionlimit(10000)

temp_dir = 'C:\\temp_joblib'
if not os.path.exists(temp_dir):
    try:
        os.makedirs(temp_dir, exist_ok=True)
    except Exception:
        pass


def setup_logging(level: str = "INFO") -> logging.Logger:
    """配置日志：同时输出到控制台和当日文件"""
    log_dir = os.path.join(current_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"scheduler_{datetime.now().strftime('%Y-%m-%d')}.log")

    # 根 logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 清除已有 handlers
    root_logger.handlers.clear()

    # 格式化器
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台 handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(getattr(logging, level.upper(), logging.INFO))
    console.setFormatter(formatter)
    root_logger.addHandler(console)

    # 文件 handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)  # 文件始终记录 DEBUG
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    root_logger.info(f"日志级别: {level}, 日志文件: {log_file}")
    return root_logger


def main():
    parser = argparse.ArgumentParser(description="独立调度器启动脚本")
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别 (默认: INFO)"
    )
    args = parser.parse_args()

    logger = setup_logging(args.log_level)
    logger.info("=" * 60)
    logger.info("🚀 独立调度器启动中...")
    logger.info("=" * 60)

    # 延迟导入避免死锁
    from app.services.scheduler import get_scheduler

    scheduler = get_scheduler()

    # 注册信号处理
    shutdown_flag = {"stop": False}

    def signal_handler(sig, frame):
        logger.info(f"收到信号 {sig}，准备优雅关闭...")
        shutdown_flag["stop"] = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        scheduler.start()
        logger.info("✅ 调度器已启动，按 Ctrl+C 停止")
        logger.info(f"   - 训练线程: 每小时检查一次")
        logger.info(f"   - 预测线程: 每分钟检查一次")
        logger.info(f"   - 预测日志: backend/logs/predictions_{{date}}.jsonl")
        logger.info(f"   - 训练日志: backend/logs/training_{{date}}.jsonl")

        # 保持主线程运行
        while not shutdown_flag["stop"]:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("收到 KeyboardInterrupt")
    except Exception as e:
        logger.error(f"调度器运行异常: {e}", exc_info=True)
    finally:
        logger.info("正在停止调度器...")
        scheduler.stop()
        logger.info("🛑 调度器已完全停止")


if __name__ == "__main__":
    main()
