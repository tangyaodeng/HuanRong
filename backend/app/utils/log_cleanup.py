"""
日志文件清理工具
按前缀和保留天数清理旧的日志文件（如 predictions_*, training_*, scheduler_*）
"""
import os
import re
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# 匹配文件名中的日期：predictions_2026-06-26.jsonl 或 scheduler_2026-06-26.log
_DATE_PATTERN = re.compile(r'(\d{4}-\d{2}-\d{2})')


def cleanup_old_logs(log_dir: str, prefix: str, keep_days: int = 7) -> int:
    """
    清理目录中 prefix* 开头的旧日志文件，只保留最近 keep_days 天的文件。

    Args:
        log_dir: 日志目录路径
        prefix: 文件名前缀（如 "predictions_", "training_", "scheduler_"）
        keep_days: 保留天数，默认7天

    Returns:
        删除的文件数量
    """
    if not os.path.isdir(log_dir):
        return 0

    cutoff_date = datetime.now() - timedelta(days=keep_days)
    deleted = 0
    to_delete = []

    try:
        for filename in os.listdir(log_dir):
            if not filename.startswith(prefix):
                continue

            match = _DATE_PATTERN.search(filename)
            if not match:
                continue

            try:
                file_date = datetime.strptime(match.group(1), '%Y-%m-%d')
                if file_date < cutoff_date:
                    to_delete.append(filename)
            except ValueError:
                continue

        for filename in to_delete:
            filepath = os.path.join(log_dir, filename)
            try:
                os.remove(filepath)
                deleted += 1
            except OSError as e:
                logger.warning(f"删除旧日志文件失败 {filepath}: {e}")

        if deleted > 0:
            logger.warning(
                f"[日志清理] {prefix}*: 已删除 {deleted} 个超过 {keep_days} 天的旧文件 ({', '.join(to_delete)})"
            )

    except Exception as e:
        logger.warning(f"[日志清理] 清理 {prefix}* 时出错: {e}")

    return deleted
