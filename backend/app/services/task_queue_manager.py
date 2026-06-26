# backend/app/services/task_queue_manager.py
import threading
import queue
import time
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class TaskQueueManager:
    """任务队列管理器 - 支持训练和预测任务并发执行"""

    def __init__(self, max_train_tasks: int = 1, max_predict_tasks: int = 1):
        """
        初始化任务队列

        Args:
            max_train_tasks: 最大并发训练任务数（默认1个）
            max_predict_tasks: 最大并发预测任务数（默认1个）
        """
        # 使用Queue实现先进先出队列
        self.task_queue = queue.Queue()

        # 活动任务跟踪 - 按任务类型分开
        self.active_tasks: Dict[str, Dict] = {
            'train': {},  # 训练任务
            'predict': {}  # 预测任务
        }
        self.task_results: Dict[str, Dict] = {}
        self.task_status: Dict[str, str] = {}  # pending, running, completed, failed

        self.max_train_tasks = max_train_tasks
        self.max_predict_tasks = max_predict_tasks
        self.lock = threading.RLock()
        self.is_running = False
        self.worker_thread = None

        # 【关键修复】按设备ID和任务类型创建锁
        # 结构: device_locks[device_id][task_type] = threading.Lock()
        self.device_locks: Dict[int, Dict[str, threading.Lock]] = defaultdict(dict)
        self.device_lock_timeout = 300  # 设备锁超时时间（秒）

        # 任务统计
        self.stats = {
            'total_added': 0,
            'total_completed': 0,
            'total_failed': 0,
            'max_queue_size': 0,
            'avg_execution_time': 0,
            'by_type': {
                'train': {'added': 0, 'completed': 0, 'failed': 0},
                'predict': {'added': 0, 'completed': 0, 'failed': 0}
            }
        }

        logger.info(f"任务队列管理器初始化完成，最大训练任务: {max_train_tasks}, 最大预测任务: {max_predict_tasks}")

    def add_task(self, task_id, task_func, args=(), kwargs=None, device_id=None, task_type="generic"):
        if kwargs is None:
            kwargs = {}

        with self.lock:
            # 检查是否已有相同任务ID
            if task_id in self.task_status:
                logger.warning(f"任务 {task_id} 已存在，状态: {self.task_status[task_id]}")
                return False

            # 检查任务类型是否有效
            if task_type not in ['train', 'predict']:
                logger.warning(f"任务 {task_id} 类型无效: {task_type}")
                return False

            # 不再检查设备是否已有任务，允许排队
            # 创建任务项
            task_item = {
                'task_id': task_id,
                'task_func': task_func,
                'args': args,
                'kwargs': kwargs,
                'device_id': device_id,
                'task_type': task_type,
                'added_at': datetime.now(),
                'status': 'pending',
                'retry_count': 0
            }

            # 添加到队列
            self.task_queue.put(task_item)

            # 更新状态和统计
            self.task_status[task_id] = 'pending'
            self.stats['total_added'] += 1
            self.stats['by_type'][task_type]['added'] += 1

            current_size = self.task_queue.qsize()
            if current_size > self.stats['max_queue_size']:
                self.stats['max_queue_size'] = current_size

            logger.info(f"✅ 任务 {task_id} 已添加到队列 (设备: {device_id}, 类型: {task_type})")
            logger.info(f"📊 队列状态: {current_size} 个等待任务")
            return True

    def _get_device_lock(self, device_id: int, task_type: str) -> threading.Lock:
        with self.lock:
            if device_id not in self.device_locks:
                self.device_locks[device_id] = {}
            if task_type not in self.device_locks[device_id]:
                self.device_locks[device_id][task_type] = threading.Lock()
                logger.debug(f"为设备 {device_id} 创建 {task_type} 锁")
            return self.device_locks[device_id][task_type]

    def _can_start_task(self, task_type: str, device_id: int = None) -> bool:
        """检查是否可以启动指定类型的任务，并确保同一设备同一类型任务不重复"""
        with self.lock:
            # 检查同一设备是否已有同类型任务在运行
            if device_id is not None:
                for task in self.active_tasks[task_type].values():
                    if task.get('device_id') == device_id:
                        return False

            # 检查全局并发数
            active_count = len(self.active_tasks[task_type])
            if task_type == 'train':
                return active_count < self.max_train_tasks
            elif task_type == 'predict':
                return active_count < self.max_predict_tasks
            return False

    def _execute_task(self, task_item: Dict):
        """执行单个任务"""
        task_id = task_item['task_id']
        device_id = task_item['device_id']
        task_type = task_item['task_type']

        # 在执行前检查任务是否应该继续
        with self.lock:
            if task_id not in self.task_status or self.task_status[task_id] != 'pending':
                logger.warning(f"任务 {task_id} 在执行前已被取消或处理，跳过")
                return

        start_time = time.time()
        device_lock = None

        try:
            # 更新任务状态
            with self.lock:
                self.task_status[task_id] = 'running'
                task_item['status'] = 'running'
                task_item['started_at'] = datetime.now()
                self.active_tasks[task_type][task_id] = task_item

            logger.info(f"🚀 开始执行任务 {task_id} (设备: {device_id}, 类型: {task_type})")

            # 如果任务关联设备，获取设备锁（按任务类型区分）
            if device_id:
                device_lock = self._get_device_lock(device_id, task_type)
                if device_lock is None:
                    error_msg = f"获取设备 {device_id} 的 {task_type} 锁失败，返回 None"
                    logger.error(f"❌ {error_msg}")
                    with self.lock:
                        self.task_status[task_id] = 'failed'
                        self.task_results[task_id] = {
                            'success': False,
                            'error': error_msg,
                            'started_at': task_item.get('started_at'),
                            'completed_at': datetime.now(),
                            'execution_time': time.time() - start_time,
                            'device_id': device_id,
                            'task_type': task_type
                        }
                        self.stats['total_failed'] += 1
                        self.stats['by_type'][task_type]['failed'] += 1
                        if task_id in self.active_tasks[task_type]:
                            del self.active_tasks[task_type][task_id]
                    return

                logger.info(f"任务 {task_id} 等待设备 {device_id} 的 {task_type} 锁")
                # 使用 timeout=-1 表示无限等待（整数参数，避免 None 类型问题）
                lock_acquired = device_lock.acquire(timeout=-1)
                logger.info(f"任务 {task_id} 获得设备 {device_id} 的 {task_type} 锁")
                # 由于 timeout=-1，lock_acquired 总是 True，但保留条件判断
                if not lock_acquired:
                    # 实际不会执行到这里
                    error_msg = f"获取设备 {device_id} 的 {task_type} 锁超时"
                    logger.warning(f"⚠️ {error_msg}")
                    with self.lock:
                        self.task_status[task_id] = 'failed'
                        self.task_results[task_id] = {
                            'success': False,
                            'error': error_msg,
                            'started_at': task_item.get('started_at'),
                            'completed_at': datetime.now(),
                            'execution_time': time.time() - start_time,
                            'device_id': device_id,
                            'task_type': task_type
                        }
                        self.stats['total_failed'] += 1
                        self.stats['by_type'][task_type]['failed'] += 1
                        if task_id in self.active_tasks[task_type]:
                            del self.active_tasks[task_type][task_id]
                    return

            # 执行任务函数
            result = task_item['task_func'](*task_item['args'], **task_item['kwargs'])

            execution_time = time.time() - start_time

            # 记录成功结果
            with self.lock:
                self.task_results[task_id] = {
                    'success': True,
                    'result': result,
                    'started_at': task_item['started_at'],
                    'completed_at': datetime.now(),
                    'execution_time': execution_time,
                    'device_id': device_id,
                    'task_type': task_type
                }

                self.task_status[task_id] = 'completed'
                self.stats['total_completed'] += 1
                self.stats['by_type'][task_type]['completed'] += 1

                # 从活动任务中移除
                if task_id in self.active_tasks[task_type]:
                    del self.active_tasks[task_type][task_id]

                # 更新平均执行时间
                total_completed = self.stats['total_completed']
                if total_completed > 0:
                    self.stats['avg_execution_time'] = (
                            (self.stats['avg_execution_time'] * (
                                        total_completed - 1) + execution_time) / total_completed
                    )

            logger.info(f"✅ 任务 {task_id} 执行成功，耗时: {execution_time:.2f}秒")

        except Exception as e:
            execution_time = time.time() - start_time

            # 获取当前重试次数
            retry_count = task_item.get('retry_count', 0)

            if retry_count < 3:
                logger.warning(f"任务 {task_id} 执行失败（第{retry_count + 1}次），重新加入队列: {e}")
                # 增加重试次数
                task_item['retry_count'] = retry_count + 1
                task_item['status'] = 'pending'
                # 重新加入队列
                self.task_queue.put(task_item)
                # 更新全局状态和活动任务
                with self.lock:
                    # 更新状态为 pending
                    self.task_status[task_id] = 'pending'
                    # 从活动任务中移除（如果已添加）
                    if task_id in self.active_tasks[task_type]:
                        del self.active_tasks[task_type][task_id]
                return  # 直接返回，不记录失败统计
            else:
                # 记录失败结果
                with self.lock:
                    self.task_results[task_id] = {
                        'success': False,
                        'error': str(e),
                        'started_at': task_item.get('started_at'),
                        'completed_at': datetime.now(),
                        'execution_time': execution_time,
                        'device_id': device_id,
                        'task_type': task_type,
                        'traceback': None  # 可添加 traceback
                    }
                    self.task_status[task_id] = 'failed'
                    self.stats['total_failed'] += 1
                    self.stats['by_type'][task_type]['failed'] += 1
                    if task_id in self.active_tasks[task_type]:
                        del self.active_tasks[task_type][task_id]
                logger.error(f"❌ 任务 {task_id} 最终失败: {e}，耗时: {execution_time:.2f}秒", exc_info=True)

        finally:
            # 释放设备锁
            if device_id and device_lock and device_lock.locked():
                device_lock.release()
                logger.info(f"🔓 已释放设备 {device_id} 的 {task_type} 锁")

            logger.info(
                f"📊 活动任务数 - 训练: {len(self.active_tasks['train'])}, 预测: {len(self.active_tasks['predict'])}")

    def _queue_worker(self):
        """队列工作线程主循环"""
        logger.info("🚀 任务队列工作线程启动")

        while self.is_running:
            try:
                # 获取下一个任务（非阻塞方式）
                try:
                    task_item = self.task_queue.get(timeout=1)

                    # 检查任务是否已被取消或处理
                    task_id = task_item['task_id']
                    task_type = task_item['task_type']

                    if self.task_status.get(task_id) != 'pending':
                        logger.warning(f"任务 {task_id} 状态异常，跳过")
                        self.task_queue.task_done()
                        continue

                    # 检查是否可以启动该类型任务
                    if not self._can_start_task(task_type, task_item.get('device_id')):
                        logger.debug(f"达到最大{task_type}任务数，等待...")
                        # 将任务放回队列前面
                        self.task_queue.put(task_item)
                        time.sleep(0.5)
                        continue

                    # 启动任务线程
                    thread = threading.Thread(
                        target=self._execute_task,
                        args=(task_item,),
                        daemon=True,
                        name=f"Task-{task_id}"
                    )

                    thread.start()

                    active_train = len(self.active_tasks['train'])
                    active_predict = len(self.active_tasks['predict'])
                    logger.info(f"📈 启动任务 {task_id}，活动任务 - 训练: {active_train}, 预测: {active_predict}")

                    # 标记任务已取出
                    self.task_queue.task_done()

                except queue.Empty:
                    # 队列为空，等待
                    continue

            except Exception as e:
                logger.error(f"队列工作线程异常: {e}", exc_info=True)
                time.sleep(1)

        logger.info("🛑 任务队列工作线程停止")

    def start(self):
        """启动队列管理器"""
        if self.is_running:
            logger.warning("任务队列管理器已经在运行中")
            return

        self.is_running = True
        self.worker_thread = threading.Thread(
            target=self._queue_worker,
            daemon=True,
            name="TaskQueueWorker"
        )
        self.worker_thread.start()

        logger.info("✅ 任务队列管理器已启动")

    def stop(self):
        """停止队列管理器"""
        if not self.is_running:
            return

        self.is_running = False

        # 等待工作线程停止
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5)

        logger.info("🛑 任务队列管理器已停止")

    def get_queue_status(self) -> Dict:
        """获取队列状态信息"""
        with self.lock:
            all_active_tasks = []
            for task_type in ['train', 'predict']:
                for task_id, task_item in self.active_tasks[task_type].items():
                    all_active_tasks.append({
                        'task_id': task_id,
                        'task_type': task_type,
                        'device_id': task_item.get('device_id'),
                        'started_at': task_item.get('started_at')
                    })

            return {
                'is_running': self.is_running,
                'queue_size': self.task_queue.qsize(),
                'active_tasks': all_active_tasks,
                'active_train_count': len(self.active_tasks['train']),
                'active_predict_count': len(self.active_tasks['predict']),
                'max_train_tasks': self.max_train_tasks,
                'max_predict_tasks': self.max_predict_tasks,
                'waiting_tasks': self.task_queue.qsize(),
                'device_locks': len(self.device_locks),
                'stats': self.stats.copy()
            }

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取特定任务状态"""
        with self.lock:
            if task_id not in self.task_status:
                return None

            status_info = {
                'task_id': task_id,
                'status': self.task_status[task_id]
            }

            if task_id in self.task_results:
                status_info.update(self.task_results[task_id])

            return status_info

    def wait_for_task(self, task_id: str, timeout: int = 3600) -> Optional[Dict]:
        """等待特定任务完成"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            with self.lock:
                if task_id in self.task_results:
                    return self.task_results[task_id]

            time.sleep(1)

        logger.warning(f"等待任务 {task_id} 超时 ({timeout}秒)")
        return None

    def clear_completed_tasks(self, older_than_hours: int = 24):
        """清理旧的任务记录"""
        with self.lock:
            cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
            tasks_to_remove = []

            for task_id, result in self.task_results.items():
                completed_at = result.get('completed_at')
                if completed_at and completed_at < cutoff_time:
                    tasks_to_remove.append(task_id)

            for task_id in tasks_to_remove:
                if task_id in self.task_results:
                    del self.task_results[task_id]
                if task_id in self.task_status:
                    del self.task_status[task_id]

            logger.info(f"已清理 {len(tasks_to_remove)} 个旧任务记录")


# 在文件末尾添加单例获取函数
_task_queue_manager = None

def get_task_queue_manager() -> TaskQueueManager:
    """获取任务队列管理器单例"""
    global _task_queue_manager
    if _task_queue_manager is None:
        _task_queue_manager = TaskQueueManager(max_train_tasks=1, max_predict_tasks=1)
    return _task_queue_manager