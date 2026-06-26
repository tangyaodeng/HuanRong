# backend/app/services/scheduler.py
# 在原有代码基础上修改

import schedule
import time
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from ..database import SessionLocal
from .. import models
import requests
import threading
import traceback
from sqlalchemy import or_
import os
import sys
import uuid
from typing import Dict
from sqlalchemy import and_

# 【重要修复】在导入任何ml模块之前设置环境变量，防止死锁
os.environ["PYTHONUNBUFFERED"] = "1"
sys.setrecursionlimit(10000)  # 增加递归深度

# 延迟导入ml模块 - 防止死锁
_ml_modules_imported = False


def ensure_ml_modules_imported():
    """确保ML模块安全导入（避免死锁）"""
    global _ml_modules_imported
    if not _ml_modules_imported:
        try:
            # 使用线程锁避免并发导入
            import threading
            import_lock = threading.RLock()
            with import_lock:
                # 先导入基础模块
                import pandas as pd
                import numpy as np

                # 然后按顺序导入自定义模块
                from ml.data.loader import MySQLDataLoader
                from ml.data.preprocessor import TimeSeriesPreprocessor
                from ml.models.trainer import XGBoostTrainer, ModelTrainingManager

                logger.info("✅ ML模块安全导入完成")
                _ml_modules_imported = True
        except Exception as e:
            logger.error(f"导入ML模块失败: {e}")
    return _ml_modules_imported


logger = logging.getLogger(__name__)


class TrainingScheduler:
    """训练计划调度器 - 使用双线程分别处理训练和预测任务"""

    def __init__(self):
        self.is_running = False
        self.train_thread = None  # 训练任务线程
        self.predict_thread = None  # 预测任务线程

        # 线程控制标志
        self.train_thread_running = False
        self.predict_thread_running = False

        # 线程锁
        self.train_lock = threading.RLock()
        self.predict_lock = threading.RLock()

        self.api_base_url = "http://localhost:8000/api/v1/model_training"
        self.predictor = None  # 预测器实例
        self._import_lock = threading.RLock()  # 导入锁

        # 初始化任务队列 - 使用单例模式
        from .task_queue_manager import get_task_queue_manager
        self.task_queue = get_task_queue_manager()

        # 任务执行统计
        self.task_statistics = {
            'train': {'total': 0, 'success': 0, 'failed': 0},
            'predict': {'total': 0, 'success': 0, 'failed': 0},
            'last_train_check': None,
            'last_predict_check': None
        }

    def recover_expired_schedules(self):
        """恢复过期的任务计划 - 在服务启动时调用"""
        try:
            logger.info("🔄 开始恢复过期的任务计划...")

            db = SessionLocal()
            try:
                # 统一使用 UTC 时间，避免时区混淆
                now = datetime.now(timezone.utc)

                # 1. 查询所有活跃但已经过期的任务
                expired_schedules = db.query(models.TrainingSchedule).filter(
                    models.TrainingSchedule.is_active == True,
                    models.TrainingSchedule.next_run_at < now
                ).all()

                logger.info(f"找到 {len(expired_schedules)} 个已过期的活跃任务计划")

                recovered_count = 0
                for schedule in expired_schedules:
                    try:
                        # 检查计划是否完全过期（结束时间也过去了）
                        if schedule.end_time and schedule.end_time < now:
                            logger.info(f"计划 {schedule.id} 已完全过期（结束时间: {schedule.end_time}），停用")
                            schedule.is_active = False
                            db.commit()
                            continue

                        # 计算应该执行的下次时间
                        new_next_run = self._calculate_proper_next_run(schedule, now)

                        if new_next_run:
                            schedule.next_run_at = new_next_run
                            recovered_count += 1

                            # 如果新时间在当前时间之后不久（10分钟内），立即添加到队列
                            time_diff = (new_next_run - now).total_seconds()
                            if 0 <= time_diff <= 600:  # 10分钟内
                                logger.info(f"计划 {schedule.id} 将在 {time_diff:.0f} 秒后执行，立即添加到队列")
                                self._add_schedule_to_queue(schedule, immediate=True)
                            else:
                                logger.info(f"计划 {schedule.id} 已恢复，下次执行时间: {new_next_run}")
                        else:
                            logger.warning(f"计划 {schedule.id} 无法计算有效下次执行时间，停用")
                            schedule.is_active = False

                        db.commit()

                    except Exception as e:
                        logger.error(f"恢复计划 {schedule.id} 失败: {e}")
                        db.rollback()
                        continue

                # 2. 二次校验：确保所有活跃计划的 next_run_at 都 >= 当前时间
                active_schedules = db.query(models.TrainingSchedule).filter(
                    models.TrainingSchedule.is_active == True
                ).all()
                fixed_count = 0
                for schedule in active_schedules:
                    if schedule.next_run_at < now:
                        # 计算新的 next_run_at
                        new_next = self._calculate_proper_next_run(schedule, now)
                        if new_next:
                            schedule.next_run_at = new_next
                            fixed_count += 1

                            # 如果修正后的时间在10分钟内，也立即加入队列
                            time_diff = (new_next - now).total_seconds()
                            if 0 <= time_diff <= 600:
                                logger.info(f"计划 {schedule.id} 修正后将在 {time_diff:.0f} 秒后执行，立即添加到队列")
                                self._add_schedule_to_queue(schedule, immediate=True)
                            else:
                                logger.info(f"计划 {schedule.id} 已修正，下次执行时间: {new_next}")
                        else:
                            # 无法计算有效时间，停用计划
                            schedule.is_active = False
                            logger.warning(f"计划 {schedule.id} 无法修正，已停用")

                if fixed_count > 0:
                    db.commit()
                    logger.info(f"额外修正了 {fixed_count} 个活跃计划的 next_run_at")

                logger.info(f"✅ 共恢复/修正 {recovered_count + fixed_count} 个任务计划")
                return recovered_count

            finally:
                db.close()

        except Exception as e:
            logger.error(f"恢复过期任务计划失败: {e}")
            return 0

    def _calculate_proper_next_run(self, schedule, current_time):
        """计算合适的下次执行时间，根据计划类型采用不同策略"""
        try:
            # 如果是训练任务，对齐到整点（从起始时间之后的下一个整点）
            if schedule.schedule_type == 'train':
                # 从当前时间开始，找到下一个整点
                next_run = (current_time + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
                # 如果结束时间存在且超过了，则无效
                if schedule.end_time and next_run > schedule.end_time:
                    return None
                return next_run

            # 预测任务：保持原有的间隔累加逻辑
            # 确定基准时间
            if schedule.start_time:
                base_time = schedule.start_time
            else:
                base_time = schedule.last_run_at if schedule.last_run_at else schedule.next_run_at

            # 计算间隔
            if schedule.interval_unit == 'minutes':
                delta = timedelta(minutes=schedule.interval_value)
            elif schedule.interval_unit == 'hours':
                delta = timedelta(hours=schedule.interval_value)
            elif schedule.interval_unit == 'days':
                delta = timedelta(days=schedule.interval_value)
            else:
                logger.error(f"未知的间隔单位: {schedule.interval_unit}")
                return None

            # 累加直到大于当前时间
            next_run = base_time
            while next_run < current_time:
                next_run += delta
                if schedule.end_time and next_run > schedule.end_time:
                    return None
            return next_run

        except Exception as e:
            logger.error(f"计算下次执行时间失败: {e}")
            return None

    def _add_schedule_to_queue(self, schedule, immediate=False):
        """将计划添加到任务队列"""
        try:
            # 生成任务ID
            task_id = f"{schedule.schedule_type.capitalize()}-{schedule.id}-{int(time.time())}"

            # 添加到任务队列
            added = self.task_queue.add_task(
                task_id=task_id,
                task_func=self._execute_schedule_with_update,
                args=(schedule.id,),
                device_id=schedule.device_id,
                task_type=schedule.schedule_type
            )

            if added:
                logger.info(f"计划 {schedule.id} 已添加到任务队列")
                return True
            else:
                logger.warning(f"计划 {schedule.id} 添加到队列失败")
                return False

        except Exception as e:
            logger.error(f"添加计划到队列失败: {e}")
            return False

    def get_pending_schedules_by_type(self, schedule_type: str, time_window_minutes: int = 5):
        try:
            db = SessionLocal()
            try:
                now = datetime.now(timezone.utc)  # aware UTC
                window_end = now + timedelta(minutes=time_window_minutes)
                logger.debug(f"检查{schedule_type}任务，当前时间（UTC）: {now}，窗口结束: {window_end}")

                # 查询待执行计划
                pending_schedules = db.query(models.TrainingSchedule).filter(
                    and_(
                        models.TrainingSchedule.is_active == True,
                        models.TrainingSchedule.schedule_type == schedule_type,
                        models.TrainingSchedule.next_run_at >= now,
                        models.TrainingSchedule.next_run_at <= window_end,
                        or_(
                            models.TrainingSchedule.end_time.is_(None),
                            models.TrainingSchedule.next_run_at <= models.TrainingSchedule.end_time
                        )
                    )
                ).order_by(
                    models.TrainingSchedule.next_run_at.asc()
                ).all()

                logger.info(f"找到 {len(pending_schedules)} 个待执行的{schedule_type}计划")
                return pending_schedules

            finally:
                db.close()

        except Exception as e:
            logger.error(f"获取待执行的{schedule_type}计划失败: {str(e)}")
            return []

    def execute_real_training(self, schedule_id: int, device_id: int):
        """执行真实训练任务"""
        try:
            logger.info(f"执行真实训练任务，计划ID: {schedule_id}, 设备ID: {device_id}")

            # 【修复1】首先从数据库获取设备的目标特征
            db = SessionLocal()
            try:
                # 获取设备关联的模型版本和特征
                device = db.query(models.Device).filter(
                    models.Device.id == device_id
                ).first()

                if not device or not device.model_version_id:
                    logger.error(f"设备 {device_id} 未找到或未关联模型版本")
                    return False

                # 获取模型版本的输出特征
                output_features = []
                model_version_features = db.query(
                    models.ModelVersionFeature,
                    models.Feature
                ).join(
                    models.Feature, models.ModelVersionFeature.feature_id == models.Feature.id
                ).filter(
                    models.ModelVersionFeature.version_id == device.model_version_id,
                    models.ModelVersionFeature.is_output == True
                ).all()

                if not model_version_features:
                    logger.error(f"设备 {device_id} 没有设置输出特征")
                    return False

                # 使用第一个输出特征
                _, output_feature = model_version_features[0]
                target_feature = output_feature.code

                logger.info(f"获取到目标特征: {target_feature}")

            finally:
                db.close()

            # 【修复2】在配置中添加目标特征
            config = {
                'lookback_days': 30,
                'train_ratio': 0.8,
                'look_back': 24,
                'forecast_horizon': 1,
                'target_feature': target_feature,  # 添加目标特征
                'xgboost_params': {},
                'preprocessing_config': {
                    'missing_value_method': 'interpolate',
                    'outlier_method': 'iqr',
                    'create_time_features': True,
                    'scaling_method': 'standard'
                }
            }

            # 通过API调用真实训练
            response = requests.post(
                f"{self.api_base_url}/{device_id}/real_train",
                json={"config": config},  # 传递完整的配置
                timeout=3600
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"真实训练完成: {result.get('training_success', False)}")
                return result.get('training_success', False)
            else:
                logger.error(f"真实训练API调用失败: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"执行真实训练任务失败: {str(e)}", exc_info=True)
            return False

    def find_latest_model(self, device_id: int) -> str:
        """查找设备的最新模型文件"""
        try:
            # 模型保存目录
            base_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'ml',
                'models',
                'saved_models'
            )

            # 如果目录不存在，尝试其他路径
            if not os.path.exists(base_dir):
                # 尝试相对路径
                base_dir = os.path.join('backend', 'ml', 'models', 'saved_models')
                if not os.path.exists(base_dir):
                    logger.error(f"❌ 模型目录不存在: {base_dir}")
                    return None

            logger.info(f"🔍 搜索模型目录: {base_dir}")

            # 搜索设备相关的模型文件
            model_files = []
            for filename in os.listdir(base_dir):
                if filename.startswith(f"xgboost_device_{device_id}_") and filename.endswith('.pkl'):
                    model_path = os.path.join(base_dir, filename)
                    # 获取文件修改时间
                    mtime = os.path.getmtime(model_path)
                    model_files.append((mtime, model_path, filename))

            if not model_files:
                logger.error(f"❌ 设备 {device_id} 没有找到模型文件")
                return None

            # 按时间倒序排序，选择最新的模型
            model_files.sort(reverse=True)
            latest_model = model_files[0][1]  # 获取最新文件的路径

            logger.info(f"✅ 找到最新模型: {latest_model}")
            return latest_model

        except Exception as e:
            logger.error(f"❌ 查找模型文件失败: {e}")
            return None

    def _get_predictor_safely(self):
        """安全获取预测器实例"""
        with self._import_lock:
            if self.predictor is None:
                try:
                    logger.info("安全导入预测器模块...")

                    # 【关键修复】先确保ML基础模块已导入
                    ensure_ml_modules_imported()

                    # 然后导入预测器
                    from ml.models.predictor import get_predictor
                    self.predictor = get_predictor()
                    logger.info("✅ 预测器单例已安全获取")
                except ImportError as e:
                    logger.error(f"❌ 导入预测器失败: {e}")
                    # 尝试直接导入
                    try:
                        from backend.ml.models.predictor import get_predictor
                        self.predictor = get_predictor()
                        logger.info("✅ 通过完整路径导入预测器成功")
                    except ImportError:
                        logger.error("❌ 无法导入预测器，预测功能将不可用")
                        self.predictor = None
            return self.predictor

    def get_predictor(self):
        """获取预测器单例 - 使用安全方法"""
        return self._get_predictor_safely()

    def execute_schedule_task_directly(self, schedule_id: int):
        """直接执行计划任务，不通过HTTP API"""
        try:
            logger.info(f"直接执行计划任务 {schedule_id}")

            db = SessionLocal()
            try:
                # 获取计划
                schedule_record = db.query(models.TrainingSchedule).filter(
                    models.TrainingSchedule.id == schedule_id
                ).first()

                if not schedule_record or not schedule_record.is_active:
                    logger.warning(f"计划 {schedule_id} 不存在或未激活")
                    return False

                # 执行不同类型的任务
                executed = False

                if schedule_record.schedule_type == 'train':
                    executed = self.execute_real_training(schedule_id, schedule_record.device_id)
                elif schedule_record.schedule_type == 'predict':
                    executed = self.execute_real_prediction(schedule_record.device_id)
                else:
                    logger.error(f"未知的计划类型: {schedule_record.schedule_type}")
                    return False

                # 更新计划执行统计
                schedule_record.total_runs += 1
                if executed:
                    schedule_record.success_runs += 1
                    logger.info(f"计划 {schedule_id} 执行成功")
                else:
                    schedule_record.failed_runs += 1
                    logger.warning(f"计划 {schedule_id} 执行失败")

                schedule_record.last_run_at = datetime.now(timezone.utc)


                db.commit()
                return executed

            finally:
                db.close()

        except Exception as e:
            logger.error(f"执行计划 {schedule_id} 时出错: {str(e)}", exc_info=True)
            return False

    def execute_real_prediction(self, device_id: int):
        try:
            logger.info(f"执行预测任务，设备ID: {device_id}")

            # 获取预测器
            predictor = self.get_predictor()
            if predictor is None:
                logger.error("❌ 无法获取预测器实例")
                return False

            # 查找设备的最新模型文件
            model_path = self.find_latest_model(device_id)
            if not model_path:
                logger.error(f"❌ 设备 {device_id} 没有找到训练好的模型")
                return False

            # 加载模型
            logger.info(f"📂 加载模型: {model_path}")
            load_success = predictor.load_model(model_path)
            if not load_success:
                logger.error(f"❌ 加载模型失败: {model_path}")
                return False

            # 获取设备的目标特征（与训练时一致）
            db = SessionLocal()
            try:
                device = db.query(models.Device).filter(models.Device.id == device_id).first()
                if not device or not device.model_version_id:
                    logger.error(f"设备 {device_id} 未找到或未关联模型版本")
                    return False

                # 获取模型版本的输出特征
                output_feature = db.query(models.Feature).join(
                    models.ModelVersionFeature
                ).filter(
                    models.ModelVersionFeature.version_id == device.model_version_id,
                    models.ModelVersionFeature.is_output == True
                ).first()
                target_feature = output_feature.code if output_feature else None

                if not target_feature:
                    logger.error(f"设备 {device_id} 没有设置输出特征")
                    return False

            finally:
                db.close()

            # 使用从数据库获取的目标特征和默认的 look_back（例如 24）
            logger.info(f"🔮 开始执行预测，设备: {device_id}, 目标特征: {target_feature}")
            prediction_result = predictor.make_prediction(
                device_id=device_id,
                target_feature=target_feature,  # 使用实际特征
                look_back=24  # 使用默认值或从配置获取
            )

            if prediction_result.get('success'):
                logger.info(f"✅ 预测成功: {prediction_result.get('prediction', 0):.4f}")
                return True
            else:
                logger.error(f"❌ 预测失败: {prediction_result.get('error', '未知错误')}")
                return False

        except Exception as e:
            logger.error(f"执行预测任务失败: {str(e)}", exc_info=True)
            return False

    def execute_train_schedules(self):
        """执行训练任务 - 从整点开始每小时检查一次"""
        with self.train_lock:
            try:
                logger.debug("检查待执行训练计划...")
                self.task_statistics['last_train_check'] = datetime.now()

                # 获取接下来60分钟内的训练任务
                pending_schedules = self.get_pending_schedules_by_type('train', time_window_minutes=60)

                if pending_schedules:
                    logger.info(f"发现 {len(pending_schedules)} 个待执行训练计划")

                    for schedule in pending_schedules:
                        try:
                            # 检查计划是否已过期
                            if schedule.end_time and datetime.now(timezone.utc) > schedule.end_time:
                                logger.info(f"训练计划 {schedule.id} 已过期，停用")
                                self._disable_schedule(schedule.id)
                                continue

                            # 检查设备是否有正在执行的训练任务（活动任务）
                            queue_status = self.task_queue.get_queue_status()
                            # 检查该设备是否有正在执行的同类型任务
                            if any(task.get('device_id') == schedule.device_id and task.get(
                                    'task_type') == schedule.schedule_type
                                   for task in queue_status.get('active_tasks', [])):
                                logger.info(f"设备 {schedule.device_id} 已有任务在执行，跳过")
                                continue

                            # 生成任务ID
                            task_id = f"Train-{schedule.id}-{int(time.time())}"

                            # 添加详细日志：为设备添加任务
                            logger.info(f"为设备 {schedule.device_id} 添加训练任务，计划ID: {schedule.id}")

                            # 添加到任务队列
                            added = self.task_queue.add_task(
                                task_id=task_id,
                                task_func=self._execute_schedule_with_update,
                                args=(schedule.id,),
                                device_id=schedule.device_id,
                                task_type='train'
                            )

                            if added:
                                self.task_statistics['train']['total'] += 1
                                logger.info(f"训练计划 {schedule.id} 已添加到任务队列")
                            else:
                                logger.warning(f"训练计划 {schedule.id} 添加到队列失败")

                        except Exception as e:
                            logger.error(f"添加训练计划 {schedule.id} 到队列失败: {str(e)}")

                else:
                    logger.debug("没有待执行的训练计划")

            except Exception as e:
                logger.error(f"执行训练计划失败: {str(e)}")

    def execute_predict_schedules(self):
        """执行预测任务 - 每1分钟检查一次"""
        with self.predict_lock:
            try:
                logger.debug("检查待执行预测计划...")
                self.task_statistics['last_predict_check'] = datetime.now()

                # 获取接下来3分钟内的预测任务（窗口扩大，避免漏掉）
                pending_schedules = self.get_pending_schedules_by_type('predict', time_window_minutes=1)

                if pending_schedules:
                    logger.info(f"发现 {len(pending_schedules)} 个待执行预测计划")

                    for schedule in pending_schedules:
                        try:
                            # 检查计划是否已过期
                            if schedule.end_time and datetime.now(timezone.utc) > schedule.end_time:
                                logger.info(f"预测计划 {schedule.id} 已过期，停用")
                                self._disable_schedule(schedule.id)
                                continue

                            # 检查设备是否有正在执行的预测任务（活动任务）
                            queue_status = self.task_queue.get_queue_status()
                            # 检查该设备是否有正在执行的同类型任务
                            if any(task.get('device_id') == schedule.device_id and task.get(
                                    'task_type') == schedule.schedule_type
                                   for task in queue_status.get('active_tasks', [])):
                                logger.info(f"设备 {schedule.device_id} 已有任务在执行，跳过")
                                continue

                            # 生成任务ID
                            task_id = f"Predict-{schedule.id}-{int(time.time())}"

                            # 添加详细日志：为设备添加任务
                            logger.info(f"为设备 {schedule.device_id} 添加预测任务，计划ID: {schedule.id}")

                            # 添加到任务队列
                            added = self.task_queue.add_task(
                                task_id=task_id,
                                task_func=self._execute_schedule_with_update,
                                args=(schedule.id,),
                                device_id=schedule.device_id,
                                task_type='predict'
                            )

                            if added:
                                self.task_statistics['predict']['total'] += 1
                                logger.info(f"预测计划 {schedule.id} 已添加到任务队列")
                            else:
                                logger.warning(f"预测计划 {schedule.id} 添加到队列失败")

                        except Exception as e:
                            logger.error(f"添加预测计划 {schedule.id} 到队列失败: {str(e)}")

                else:
                    logger.debug("没有待执行的预测计划")

            except Exception as e:
                logger.error(f"执行预测计划失败: {str(e)}")

    def _execute_schedule_with_update(self, schedule_id: int):
        """执行计划任务并更新下次执行时间"""
        try:
            logger.info(f"开始执行计划任务 {schedule_id}")

            # 执行任务
            result = self.execute_schedule_task_directly(schedule_id)

            # 更新统计
            db = SessionLocal()
            try:
                schedule = db.query(models.TrainingSchedule).filter(
                    models.TrainingSchedule.id == schedule_id
                ).first()

                if schedule:
                    if result:
                        logger.info(f"计划 {schedule_id} 执行成功")
                        # 更新计划执行统计
                        schedule.total_runs += 1
                        schedule.success_runs += 1
                        schedule.last_run_at = datetime.now(timezone.utc)

                        # 计算下次运行时间
                        self._calculate_next_run(schedule)

                        if schedule.schedule_type == 'train':
                            self.task_statistics['train']['success'] += 1
                        else:
                            self.task_statistics['predict']['success'] += 1
                    else:
                        logger.warning(f"计划 {schedule_id} 执行失败")
                        # 更新计划执行统计
                        schedule.total_runs += 1
                        schedule.failed_runs += 1
                        schedule.last_run_at = datetime.now(timezone.utc)

                        # 计算下次运行时间（失败时也更新）
                        self._calculate_next_run(schedule)

                        if schedule.schedule_type == 'train':
                            self.task_statistics['train']['failed'] += 1
                        else:
                            self.task_statistics['predict']['failed'] += 1

                    db.commit()

            finally:
                db.close()

            logger.info(f"计划任务 {schedule_id} 执行完成")
            return result

        except Exception as e:
            logger.error(f"执行计划任务 {schedule_id} 时发生异常: {e}")

            # 确保即使异常也更新下次执行时间
            try:
                db = SessionLocal()
                schedule = db.query(models.TrainingSchedule).filter(
                    models.TrainingSchedule.id == schedule_id
                ).first()

                if schedule:
                    schedule.total_runs += 1
                    schedule.failed_runs += 1
                    schedule.last_run_at = datetime.now(timezone.utc)
                    self._calculate_next_run(schedule)
                    db.commit()

                    if schedule.schedule_type == 'train':
                        self.task_statistics['train']['failed'] += 1
                    else:
                        self.task_statistics['predict']['failed'] += 1

            except Exception as db_error:
                logger.error(f"更新数据库失败: {db_error}")
            finally:
                if db:
                    db.close()

            return False

    def _calculate_next_run(self, schedule):
        """计算下次运行时间，根据计划类型采用不同策略"""
        now = datetime.now(timezone.utc)

        if schedule.schedule_type == 'train':
            # 训练任务：基于上次执行时间 + 间隔（保持固定间隔）
            if schedule.interval_unit == 'minutes':
                delta = timedelta(minutes=schedule.interval_value)
            elif schedule.interval_unit == 'hours':
                delta = timedelta(hours=schedule.interval_value)
            else:  # days
                delta = timedelta(days=schedule.interval_value)

            base = schedule.last_run_at or schedule.start_time or now
            next_run_at = base + delta
            # 确保下次时间大于当前时间（防止时钟倒退或已过期）
            while next_run_at <= now:
                next_run_at += delta

            logger.info(f"训练计划 {schedule.id} 下次执行时间（间隔累加）: {next_run_at}")
        else:
            # 预测任务：基于当前时间 + 间隔（保持固定间隔）
            if schedule.interval_unit == 'minutes':
                delta = timedelta(minutes=schedule.interval_value)
            elif schedule.interval_unit == 'hours':
                delta = timedelta(hours=schedule.interval_value)
            else:  # days
                delta = timedelta(days=schedule.interval_value)
            next_run_at = now + delta
            logger.info(f"预测计划 {schedule.id} 下次执行时间（间隔累加）: {next_run_at}")

        # 检查是否超过结束时间
        if schedule.end_time and next_run_at > schedule.end_time:
            schedule.is_active = False
            logger.info(f"计划 {schedule.id} 已到达结束时间，自动停止")
        else:
            schedule.next_run_at = next_run_at

    def _update_next_run_on_failure(self, schedule_id: int):
        """任务失败时更新下次执行时间"""
        try:
            db = SessionLocal()
            try:
                schedule = db.query(models.TrainingSchedule).filter(
                    models.TrainingSchedule.id == schedule_id
                ).first()

                if schedule:
                    # 使用当前时间加上间隔
                    from datetime import datetime, timezone, timedelta
                    now = datetime.now(timezone.utc)

                    if schedule.interval_unit == 'minutes':
                        delta = timedelta(minutes=schedule.interval_value)
                    elif schedule.interval_unit == 'hours':
                        delta = timedelta(hours=schedule.interval_value)
                    else:  # days
                        delta = timedelta(days=schedule.interval_value)

                    schedule.next_run_at = now + delta
                    db.commit()
                    logger.info(f"计划 {schedule_id} 任务失败，下次执行时间更新为: {schedule.next_run_at}")

            finally:
                db.close()
        except Exception as e:
            logger.error(f"更新失败计划下次执行时间失败: {str(e)}")

    def _disable_schedule(self, schedule_id: int):
        """停用过期或无效的计划"""
        try:
            db = SessionLocal()
            try:
                schedule = db.query(models.TrainingSchedule).filter(
                    models.TrainingSchedule.id == schedule_id
                ).first()

                if schedule:
                    schedule.is_active = False
                    db.commit()
                    logger.info(f"计划 {schedule_id} 已停用")

            finally:
                db.close()
        except Exception as e:
            logger.error(f"停用计划失败: {str(e)}")

    def _delay_schedule(self, schedule_id: int, delay_minutes: int = 2):
        """延迟计划的执行"""
        try:
            db = SessionLocal()
            try:
                schedule = db.query(models.TrainingSchedule).filter(
                    models.TrainingSchedule.id == schedule_id
                ).first()

                if schedule:
                    from datetime import datetime, timezone, timedelta
                    now = datetime.now(timezone.utc)
                    schedule.next_run_at = now + timedelta(minutes=delay_minutes)
                    db.commit()
                    logger.info(f"计划 {schedule_id} 延迟 {delay_minutes} 分钟执行")

            finally:
                db.close()
        except Exception as e:
            logger.error(f"延迟计划 {schedule_id} 失败: {str(e)}")

    def monitor_task_queue(self):
        """监控任务队列状态，自动恢复异常"""
        queue_status = self.task_queue.get_queue_status()

        # 检查是否有任务卡住
        for task in queue_status.get('active_tasks', []):
            task_id = task.get('task_id')
            task_info = self.task_queue.get_task_status(task_id)
            if task_info:
                started_at = task_info.get('started_at')
                if started_at:
                    # 检查任务是否运行超过30分钟
                    from datetime import datetime, timezone
                    now = datetime.now(timezone.utc)
                    duration = (now - started_at).total_seconds()

                    if duration > 1800:  # 30分钟
                        logger.warning(f"任务 {task_id} 已运行 {duration / 60:.1f} 分钟，可能已卡住")
                        # 可以在这里添加强制终止或重启的逻辑

    def get_trainer_for_device(self, device_id: int):
        """为设备获取训练器配置"""
        try:
            db = SessionLocal()
            try:
                # 查询设备的主训练器配置
                trainer_config = db.query(models.TrainerConfig).filter(
                    models.TrainerConfig.device_id == device_id,
                    models.TrainerConfig.is_primary == True,
                    models.TrainerConfig.is_active == True
                ).first()

                if not trainer_config:
                    # 如果没有主配置，查找第一个活跃配置
                    trainer_config = db.query(models.TrainerConfig).filter(
                        models.TrainerConfig.device_id == device_id,
                        models.TrainerConfig.is_active == True
                    ).first()

                if not trainer_config:
                    logger.warning(f"设备 {device_id} 没有配置训练器，使用默认训练器")
                    return "ml.models.trainer.XGBoostTrainer"

                return trainer_config.trainer_path

            finally:
                db.close()
        except Exception as e:
            logger.error(f"获取设备训练器失败: {e}")
            return "ml.models.trainer.XGBoostTrainer"

    def _train_thread_worker(self):
        """训练任务线程工作函数 - 每1分钟检查一次"""
        logger.info("🚀 训练任务线程启动")

        while self.train_thread_running:
            try:
                self.execute_train_schedules()
                # 每隔60秒检查一次，可根据实际需要调整（例如10秒、30秒）
                time.sleep(3600)
            except Exception as e:
                logger.error(f"训练线程异常: {e}")
                time.sleep(5)

        logger.info("🛑 训练任务线程停止")
    def _predict_thread_worker(self):
        """预测任务线程工作函数 - 每1分钟检查一次"""
        logger.info("🚀 预测任务线程启动")

        # 等待到下一个整分钟
        current_time = datetime.now()
        seconds_to_wait = (60 - current_time.second) % 60
        if seconds_to_wait > 0:
            logger.info(f"预测线程等待 {seconds_to_wait} 秒到下一个整分钟")
            time.sleep(seconds_to_wait)

        while self.predict_thread_running:
            try:
                self.execute_predict_schedules()
                # 等待到下一个整分钟，避免累积误差
                now = datetime.now()
                sleep_seconds = 60 - now.second
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)
            except Exception as e:
                logger.error(f"预测线程异常: {e}")
                time.sleep(5)

        logger.info("🛑 预测任务线程停止")

    def start(self):
        """启动调度器 - 使用双线程分别处理训练和预测任务"""
        if self.is_running:
            logger.warning("调度器已经在运行中")
            return

        self.is_running = True
        self.train_thread_running = True
        self.predict_thread_running = True

        # 启动任务队列管理器
        self.task_queue.start()

        # 【关键修复】在启动线程之前，先恢复过期任务
        logger.info("🔄 启动前恢复过期任务计划...")
        recovered = self.recover_expired_schedules()

        if recovered > 0:
            logger.info(f"✅ 成功恢复了 {recovered} 个过期任务计划")
        else:
            logger.info("✅ 没有需要恢复的过期任务计划")

        # 启动训练任务线程
        self.train_thread = threading.Thread(
            target=self._train_thread_worker,
            daemon=True,
            name="TrainSchedulerThread"
        )
        self.train_thread.start()

        # 启动预测任务线程
        self.predict_thread = threading.Thread(
            target=self._predict_thread_worker,
            daemon=True,
            name="PredictSchedulerThread"
        )
        self.predict_thread.start()

        logger.info("✅ 训练计划调度器已启动，使用双线程模式")
        logger.info("   - 训练线程: 每小时检查一次任务")
        logger.info("   - 预测线程: 每1分钟检查一次任务")
        logger.info("   - 已启用启动时任务恢复机制")

    def stop(self):
        """停止调度器"""
        self.is_running = False
        self.train_thread_running = False
        self.predict_thread_running = False

        # 停止任务队列管理器
        self.task_queue.stop()

        # 等待训练线程结束
        if self.train_thread and self.train_thread.is_alive():
            self.train_thread.join(timeout=5)
            logger.info("训练线程已停止")

        # 等待预测线程结束
        if self.predict_thread and self.predict_thread.is_alive():
            self.predict_thread.join(timeout=5)
            logger.info("预测线程已停止")

        logger.info("🛑 调度器已完全停止")

    def get_scheduler_status(self) -> Dict:
        """获取调度器状态"""
        queue_status = self.task_queue.get_queue_status()

        return {
            'is_running': self.is_running,
            'train_thread_alive': self.train_thread.is_alive() if self.train_thread else False,
            'predict_thread_alive': self.predict_thread.is_alive() if self.predict_thread else False,
            'task_queue': queue_status,
            'task_statistics': self.task_statistics
        }


# 单例模式
_scheduler = None


def get_scheduler() -> TrainingScheduler:
    """获取调度器单例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = TrainingScheduler()
    return _scheduler