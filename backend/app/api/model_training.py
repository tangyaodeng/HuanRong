# backend/app/api/model_training.py
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from ..dependencies.database import get_db
from .. import models, schemas
import logging
from datetime import datetime, timedelta, timezone
import sys
import os
from ..crud.model_training import TrainingCRUD
import traceback
from sqlalchemy import or_
try:
    from ..services.scheduler import get_scheduler
    from ..services.task_queue_manager import get_task_queue_manager
except ImportError as e:
    import logging
    _logger = logging.getLogger(__name__)
    _logger.warning('Scheduler module import failed (may run via run_scheduler.py): %s', e)
    get_scheduler = None
    get_task_queue_manager = None
logger = logging.getLogger(__name__)
import time
import uuid
router = APIRouter(prefix="/model_training", tags=["model_training"])

@router.post("/batch/train", response_model=Dict[str, Any])
async def batch_train_models(batch_request: schemas.BatchTrainingRequest, db: Session = Depends(get_db)):
    from ..services.scheduler import get_scheduler
    from ..services.task_queue_manager import get_task_queue_manager

    scheduler = get_scheduler()
    task_queue = get_task_queue_manager()

    results = []
    success_count = 0
    failed_count = 0

    for device_id in batch_request.device_ids:
        # 检查设备是否存在
        device = db.query(models.Device).filter(models.Device.id == device_id).first()
        if not device:
            results.append({"device_id": device_id, "status": "failed", "message": "设备不存在"})
            failed_count += 1
            continue

        # 移除 _can_start_task 检查，直接尝试提交
        task_id = f"ManualTrain-{device_id}-{int(time.time())}-{uuid.uuid4().hex[:6]}"

        added = task_queue.add_task(
            task_id=task_id,
            task_func=scheduler._execute_schedule_with_update,
            args=(None,),
            kwargs={"device_id": device_id, "config": batch_request.training_config},
            device_id=device_id,
            task_type='train'
        )

        if added:
            results.append({"device_id": device_id, "status": "success", "message": "训练任务已提交"})
            success_count += 1
        else:
            # 理论上现在添加总是成功，但保留错误处理
            results.append({"device_id": device_id, "status": "failed", "message": "任务提交失败"})
            failed_count += 1

    return {
        "total": len(batch_request.device_ids),
        "success": success_count,
        "failed": failed_count,
        "results": results
    }
@router.post("/{device_id}/train_with_config", response_model=Dict[str, Any])
async def train_device_model_with_config(
        device_id: int,
        config: schemas.TrainingConfig,
        db: Session = Depends(get_db)
):
    """使用配置训练设备模型"""
    try:
        # 验证设备
        device = db.query(models.Device).filter(models.Device.id == device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="设备未找到")

        # 准备配置
        training_config = {
            'lookback_days': config.lookback_days,
            'train_ratio': config.train_ratio,
            'look_back': config.look_back,
            'forecast_horizon': config.forecast_horizon,
            'xgboost_params': config.xgboost_params or {},
            'preprocessing_config': config.preprocessing_config
        }

        print(f"训练配置: {training_config}")

        # 确定目标特征
        target_feature = config.target_feature
        if not target_feature:
            # 获取模型版本的特征
            features = db.query(models.Feature).join(
                models.ModelVersionFeature,
                models.Feature.id == models.ModelVersionFeature.feature_id
            ).filter(
                models.ModelVersionFeature.version_id == device.model_version_id
            ).all()

            if features:
                # 使用第一个数值型特征作为目标
                numeric_features = [f for f in features if f.data_type == 'number']
                if numeric_features:
                    target_feature = numeric_features[0].code
                else:
                    # 如果没有数值型特征，使用第一个特征
                    target_feature = features[0].code
            else:
                raise HTTPException(status_code=400, detail="设备没有配置特征")

        # TODO: 这里先返回模拟结果，让服务能够启动
        result = {
            'device_id': device_id,
            'target_feature': target_feature,
            'training_success': True,
            'performance_metrics': {
                'r2_score': 0.85,
                'rmse': 0.12,
                'mae': 0.08,
                'mape': 5.3
            },
            'training_details': {
                'training_time_seconds': 45.2,
                'model_params': {},
                'data_shapes': {'X_train': (1000, 24, 10)},
                'feature_importance': []
            },
            'config': training_config
        }

        # 更新设备训练记录
        training_record = db.query(models.DeviceModelTraining).filter(
            models.DeviceModelTraining.device_id == device_id
        ).first()

        if not training_record:
            training_record = models.DeviceModelTraining(
                device_id=device_id,
                model_version_id=device.model_version_id,
                training_status='trained' if result.get('training_success') else 'failed'
            )
            db.add(training_record)
        else:
            training_record.training_status = 'trained' if result.get('training_success') else 'failed'

        if result.get('training_success'):
            training_record.last_trained_at = datetime.now()
            training_record.performance_metrics = result.get('performance_metrics', {})
            training_record.training_details = result.get('training_details', {})

        training_record.updated_at = datetime.now()
        db.commit()

        return result

    except Exception as e:
        logger.error(f"使用配置训练设备模型失败: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"训练失败: {str(e)}")


@router.post("/schedules", response_model=schemas.TrainingScheduleResponse, status_code=201)
async def create_training_schedule(
        schedule: schemas.TrainingSchedule,
        db: Session = Depends(get_db)
):
    """创建训练计划"""
    try:
        # 验证设备
        device = db.query(models.Device).filter(models.Device.id == schedule.device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="设备未找到")

        # 计算下次运行时间
        next_run_at = schedule.start_time

        # 创建计划
        db_schedule = models.TrainingSchedule(
            device_id=schedule.device_id,
            schedule_type=schedule.schedule_type,
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            interval_value=schedule.interval_value,
            interval_unit=schedule.interval_unit,
            next_run_at=next_run_at,
            is_active=schedule.is_active
        )

        db.add(db_schedule)
        db.commit()
        db.refresh(db_schedule)

        return db_schedule

    except Exception as e:
        logger.error(f"创建训练计划失败: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建训练计划失败: {str(e)}")


@router.get("/schedules/device/{device_id}", response_model=List[schemas.TrainingScheduleResponse])
async def get_device_schedules(
        device_id: int,
        schedule_type: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """获取设备的训练计划"""
    try:
        query = db.query(models.TrainingSchedule).filter(
            models.TrainingSchedule.device_id == device_id
        )

        if schedule_type:
            query = query.filter(models.TrainingSchedule.schedule_type == schedule_type)

        schedules = query.order_by(models.TrainingSchedule.next_run_at).all()
        return schedules

    except Exception as e:
        logger.error(f"获取训练计划失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取训练计划失败: {str(e)}")


@router.post("/save_settings", response_model=schemas.TrainingScheduleSettingsResponse)
async def save_training_settings(
        settings: schemas.TrainingScheduleSettings,
        db: Session = Depends(get_db)
):
    """保存训练设置"""
    try:
        logger.info(f"保存设备 {settings.device_id} 的训练设置")

        # 验证设备
        device = db.query(models.Device).filter(
            models.Device.id == settings.device_id
        ).first()

        if not device:
            raise HTTPException(status_code=404, detail="设备未找到")

        # 验证时间逻辑
        if settings.train_end_time and settings.train_end_time <= settings.train_start_time:
            raise HTTPException(status_code=400, detail="训练结束时间必须晚于开始时间")

        if settings.predict_end_time and settings.predict_end_time <= settings.predict_start_time:
            raise HTTPException(status_code=400, detail="预测结束时间必须晚于开始时间")

        # 获取或创建训练记录
        training = db.query(models.DeviceModelTraining).filter(
            models.DeviceModelTraining.device_id == settings.device_id
        ).first()

        if not training:
            training = models.DeviceModelTraining(
                device_id=settings.device_id,
                model_version_id=device.model_version_id,
                training_status='not_started'
            )
            db.add(training)
            db.commit()
            db.refresh(training)

        # 处理训练计划（更新或创建）
        train_schedule = db.query(models.TrainingSchedule).filter(
            models.TrainingSchedule.device_id == settings.device_id,
            models.TrainingSchedule.schedule_type == 'train'
        ).first()

        if train_schedule:
            # 更新现有训练计划
            train_schedule.start_time = settings.train_start_time
            train_schedule.end_time = settings.train_end_time
            train_schedule.interval_value = settings.train_interval_value
            train_schedule.interval_unit = settings.train_interval_unit
            train_schedule.is_active = settings.train_is_active

            if settings.train_is_active:
                # 重新计算 next_run_at，确保不早于当前时间
                scheduler = get_scheduler()
                new_next_run = scheduler.calculate_next_run_for_activation(
                    schedule_type='train',
                    interval_value=settings.train_interval_value,
                    interval_unit=settings.train_interval_unit,
                    start_time=settings.train_start_time,
                    end_time=settings.train_end_time
                )
                if new_next_run:
                    train_schedule.next_run_at = new_next_run
                else:
                    # 如果计算出的时间超出结束时间，则停用计划
                    train_schedule.is_active = False
                    # 可选：记录日志，或向前端返回警告信息
                    logger.warning(f"设备 {settings.device_id} 的训练计划激活失败，结束时间已过，已自动停用")
            # 如果停用，保留原有 next_run_at（不变）
        else:
            # 创建新的训练计划
            train_schedule = models.TrainingSchedule(
                device_id=settings.device_id,
                schedule_type='train',
                start_time=settings.train_start_time,
                end_time=settings.train_end_time,
                interval_value=settings.train_interval_value,
                interval_unit=settings.train_interval_unit,
                next_run_at=settings.train_start_time,
                is_active=settings.train_is_active
            )
            db.add(train_schedule)

        # 处理预测计划（更新或创建）
        predict_schedule = db.query(models.TrainingSchedule).filter(
            models.TrainingSchedule.device_id == settings.device_id,
            models.TrainingSchedule.schedule_type == 'predict'
        ).first()

        if predict_schedule:
            # 更新现有预测计划
            predict_schedule.start_time = settings.predict_start_time
            predict_schedule.end_time = settings.predict_end_time
            predict_schedule.interval_value = settings.predict_interval_value
            predict_schedule.interval_unit = settings.predict_interval_unit
            predict_schedule.is_active = settings.predict_is_active
            predict_schedule.output_mode = settings.output_mode
            predict_schedule.output_count = settings.output_count

            if settings.predict_is_active:
                scheduler = get_scheduler()
                new_next_run = scheduler.calculate_next_run_for_activation(
                    schedule_type='predict',
                    interval_value=settings.predict_interval_value,
                    interval_unit=settings.predict_interval_unit,
                    start_time=settings.predict_start_time,
                    end_time=settings.predict_end_time
                )
                if new_next_run:
                    predict_schedule.next_run_at = new_next_run
                else:
                    predict_schedule.is_active = False
                    logger.warning(f"设备 {settings.device_id} 的预测计划激活失败，结束时间已过，已自动停用")
        else:
            # 创建新的预测计划
            predict_schedule = models.TrainingSchedule(
                device_id=settings.device_id,
                schedule_type='predict',
                start_time=settings.predict_start_time,
                end_time=settings.predict_end_time,
                interval_value=settings.predict_interval_value,
                interval_unit=settings.predict_interval_unit,
                next_run_at=settings.predict_start_time,
                is_active=settings.predict_is_active,
                output_mode=settings.output_mode,
                output_count=settings.output_count
            )
            db.add(predict_schedule)

        db.commit()

        return {
            "device_id": settings.device_id,
            "message": "训练设置保存成功"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存训练设置失败: {str(e)}")
        db.rollback()
        error_detail = str(e)
        if "end_time > start_time" in error_detail or "CheckViolation" in error_detail:
            error_detail = "时间设置错误：结束时间必须晚于开始时间"
        raise HTTPException(status_code=500, detail=f"保存训练设置失败: {error_detail}")


@router.post("/schedule/{schedule_id}/toggle", response_model=Dict[str, Any])
async def toggle_schedule_status(
        schedule_id: int,
        db: Session = Depends(get_db)
):
    """切换计划状态（启用/禁用）"""
    try:
        schedule = db.query(models.TrainingSchedule).filter(
            models.TrainingSchedule.id == schedule_id
        ).first()

        if not schedule:
            raise HTTPException(status_code=404, detail="训练计划未找到")

        # 切换状态
        schedule.is_active = not schedule.is_active
        schedule.updated_at = datetime.now()

        db.commit()

        status_text = "已启用" if schedule.is_active else "已停止"

        return {
            "schedule_id": schedule_id,
            "device_id": schedule.device_id,
            "schedule_type": schedule.schedule_type,
            "is_active": schedule.is_active,
            "message": f"{schedule.schedule_type}计划已{status_text}"
        }

    except Exception as e:
        logger.error(f"切换计划状态失败: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"切换计划状态失败: {str(e)}")


# 添加执行计划任务的接口
@router.post("/schedule/execute/{schedule_id}", response_model=Dict[str, Any])
def execute_schedule_task(
        schedule_id: int,
        db: Session = Depends(get_db)
):
    """执行训练或预测计划任务 - 简化版本"""
    try:
        logger.info(f"执行计划任务 {schedule_id}")

        # 获取计划
        schedule = db.query(models.TrainingSchedule).filter(
            models.TrainingSchedule.id == schedule_id
        ).first()

        if not schedule:
            raise HTTPException(status_code=404, detail="计划未找到")

        if not schedule.is_active:
            return {
                "schedule_id": schedule_id,
                "message": "计划未激活，跳过执行",
                "executed": False
            }

        # 根据计划类型执行不同任务
        executed = False
        message = ""

        if schedule.schedule_type == 'train':
            # 执行训练任务
            try:
                # 直接调用训练管理器
                from ml.models.trainer import ModelTrainingManager
                training_manager = ModelTrainingManager(db)

                # 准备训练配置
                config = {
                    'lookback_days': 30,
                    'train_ratio': 0.8,
                    'look_back': 24,
                    'forecast_horizon': 1,
                    'preprocessing_config': {
                        'create_time_features': True,
                        'scaling_method': 'standard'
                    }
                }

                # 确定目标特征
                from app import models as app_models
                id13_mapping = db.query(app_models.FeatureTableMapping).filter(
                    app_models.FeatureTableMapping.id == 13
                ).first()

                target_feature = "point_value"  # 默认
                if id13_mapping:
                    feature = db.query(app_models.Feature).filter(
                        app_models.Feature.id == id13_mapping.feature_id
                    ).first()
                    if feature:
                        target_feature = feature.code

                # 执行训练
                result = training_manager.train_device_model(
                    device_id=schedule.device_id,
                    target_feature=target_feature,
                    config=config
                )

                executed = result.get('training_success', False)
                message = f"训练任务执行{'成功' if executed else '失败'}"

            except Exception as e:
                logger.error(f"训练任务执行失败: {str(e)}", exc_info=True)
                message = f"训练任务执行失败: {str(e)}"

        elif schedule.schedule_type == 'predict':
            # 执行预测任务
            try:
                from ml.models.predictor import get_predictor
                predictor = get_predictor()

                # 查找设备的最新模型
                import os
                base_dir = os.path.join(os.path.dirname(__file__), "../ml/models/saved_models")
                device_models = []

                if os.path.exists(base_dir):
                    for f in os.listdir(base_dir):
                        if f.startswith(f"xgboost_device_{schedule.device_id}_"):
                            device_models.append(f)

                if not device_models:
                    raise ValueError(f"设备 {schedule.device_id} 没有训练好的模型")

                # 使用最新的模型
                device_models.sort(reverse=True)
                latest_model = os.path.join(base_dir, device_models[0])

                # 加载模型
                predictor.load_model(latest_model)

                # 执行预测
                result = predictor.make_prediction(
                    device_id=schedule.device_id,
                    target_feature=None,
                    look_back=None
                )

                executed = result.get('success', False)
                message = f"预测任务执行{'成功' if executed else '失败'}"

            except Exception as e:
                logger.error(f"预测任务执行失败: {str(e)}")
                message = f"预测任务执行失败: {str(e)}"

        # 更新计划执行统计
        schedule.total_runs += 1
        if executed:
            schedule.success_runs += 1
        else:
            schedule.failed_runs += 1

        schedule.last_run_at = datetime.now(timezone.utc)

        # 计算下次运行时间
        if schedule.end_time is None or schedule.last_run_at < schedule.end_time:
            if schedule.interval_unit == 'minutes':
                delta = timedelta(minutes=schedule.interval_value)
            elif schedule.interval_unit == 'hours':
                delta = timedelta(hours=schedule.interval_value)
            else:  # days
                delta = timedelta(days=schedule.interval_value)

            schedule.next_run_at = schedule.last_run_at + delta
        else:
            schedule.is_active = False
            logger.info(f"计划 {schedule_id} 已到达结束时间，自动停止")

        db.commit()

        return {
            "schedule_id": schedule_id,
            "schedule_type": schedule.schedule_type,
            "executed": executed,
            "next_run_at": schedule.next_run_at,
            "message": message
        }

    except Exception as e:
        logger.error(f"执行计划任务失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"执行计划任务失败: {str(e)}")


# 添加获取待执行计划的接口
@router.get("/schedules/pending", response_model=List[schemas.TrainingScheduleResponse])
def get_pending_schedules(  # 移除 async
        db: Session = Depends(get_db)
):
    """获取待执行的计划"""
    try:
        from datetime import timezone

        now = datetime.now(timezone.utc)

        pending_schedules = db.query(models.TrainingSchedule).filter(
            models.TrainingSchedule.is_active == True,
            models.TrainingSchedule.next_run_at <= now,
            or_(
                models.TrainingSchedule.end_time.is_(None),
                models.TrainingSchedule.next_run_at <= models.TrainingSchedule.end_time
            )
        ).all()

        return pending_schedules

    except Exception as e:
        logger.error(f"获取待执行计划失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取待执行计划失败: {str(e)}")

# 在 model_training.py 中添加专门的开始/停止接口

@router.post("/schedule/start/{device_id}", response_model=Dict[str, Any])
async def start_schedule(
        device_id: int,
        schedule_type: str = Body('train', embed=True),
        db: Session = Depends(get_db)
):
    """开始训练或预测任务"""
    try:
        # 查找计划
        schedule = db.query(models.TrainingSchedule).filter(
            models.TrainingSchedule.device_id == device_id,
            models.TrainingSchedule.schedule_type == schedule_type
        ).first()

        if not schedule:
            # 如果计划不存在，需要先创建
            device = db.query(models.Device).filter(
                models.Device.id == device_id
            ).first()

            if not device:
                raise HTTPException(status_code=404, detail="设备未找到")

            # 获取当前时间作为开始时间
            start_time = datetime.now()

            # 根据计划类型设置默认参数
            if schedule_type == 'train':
                interval_value = 12
                interval_unit = 'hours'
            else:  # predict
                interval_value = 5
                interval_unit = 'minutes'

            # 创建计划
            schedule = models.TrainingSchedule(
                device_id=device_id,
                schedule_type=schedule_type,
                start_time=start_time,
                end_time=None,
                interval_value=interval_value,
                interval_unit=interval_unit,
                next_run_at=start_time,
                is_active=True
            )
            db.add(schedule)
        else:
            # 激活现有计划
            schedule.is_active = True
            schedule.next_run_at = datetime.now()

        schedule.updated_at = datetime.now()
        db.commit()

        return {
            "schedule_id": schedule.id,
            "device_id": device_id,
            "schedule_type": schedule_type,
            "is_active": True,
            "message": f"{'训练' if schedule_type == 'train' else '预测'}任务已开始"
        }

    except Exception as e:
        logger.error(f"开始任务失败: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"开始任务失败: {str(e)}")


@router.post("/schedule/stop/{device_id}", response_model=Dict[str, Any])
async def stop_schedule(
        device_id: int,
        schedule_type: str = Body('train', embed=True),
        db: Session = Depends(get_db)
):
    """停止训练或预测任务"""
    try:
        schedule = db.query(models.TrainingSchedule).filter(
            models.TrainingSchedule.device_id == device_id,
            models.TrainingSchedule.schedule_type == schedule_type
        ).first()

        if not schedule:
            raise HTTPException(status_code=404, detail=f"{'训练' if schedule_type == 'train' else '预测'}计划未找到")

        # 停止任务
        schedule.is_active = False
        schedule.last_run_at = datetime.now()
        schedule.updated_at = datetime.now()

        db.commit()

        return {
            "schedule_id": schedule.id,
            "device_id": device_id,
            "schedule_type": schedule_type,
            "is_active": False,
            "message": f"{'训练' if schedule_type == 'train' else '预测'}任务已停止"
        }

    except Exception as e:
        logger.error(f"停止任务失败: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"停止任务失败: {str(e)}")

@router.delete("/schedules/{schedule_id}", status_code=204)
async def delete_training_schedule(
        schedule_id: int,
        db: Session = Depends(get_db)
):
    """删除训练计划"""
    try:
        schedule = db.query(models.TrainingSchedule).filter(
            models.TrainingSchedule.id == schedule_id
        ).first()

        if not schedule:
            raise HTTPException(status_code=404, detail="训练计划未找到")

        db.delete(schedule)
        db.commit()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除训练计划失败: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除训练计划失败: {str(e)}")


@router.get("/{device_id}/config", response_model=Dict[str, Any])
async def get_device_default_config(
        device_id: int,
        db: Session = Depends(get_db)
):
    """获取设备默认训练配置"""
    try:
        device = db.query(models.Device).filter(models.Device.id == device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="设备未找到")

        # 获取设备特征
        features = []
        if device.model_version_id:
            features = db.query(models.Feature).join(
                models.ModelVersionFeature,
                models.Feature.id == models.ModelVersionFeature.feature_id
            ).filter(
                models.ModelVersionFeature.version_id == device.model_version_id
            ).all()

        # 默认配置
        now = datetime.now()
        default_config = {
            "device_id": device_id,
            "lookback_days": 30,
            "train_ratio": 0.8,
            "train_start_time": now.isoformat(),
            "train_end_time": (now + timedelta(days=1)).isoformat(),
            "predict_start_time": now.isoformat(),
            "predict_end_time": (now + timedelta(days=7)).isoformat(),
            "train_interval_hours": 12,
            "predict_interval_minutes": 5,
            "look_back": 24,
            "forecast_horizon": 1,
            "available_features": [
                {
                    "code": feature.code,
                    "name": feature.name,
                    "data_type": feature.data_type,
                    "unit": feature.unit
                }
                for feature in features
            ] if features else [],
            "default_target_feature": features[0].code if features else None
        }

        return default_config

    except Exception as e:
        logger.error(f"获取设备配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取设备配置失败: {str(e)}")


@router.get("/", response_model=schemas.DeviceModelTrainingList)
def get_device_model_trainings(
        db: Session = Depends(get_db),
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=100),
        project_id: Optional[int] = Query(None),
        device_id: Optional[int] = Query(None),
        training_status: Optional[str] = Query(None),
        search: Optional[str] = Query(None)
):
    """获取设备模型训练列表"""
    try:
        skip = (page - 1) * page_size

        # 构建查询
        query = db.query(models.DeviceModelTraining)

        # 应用筛选条件
        if device_id:
            query = query.filter(models.DeviceModelTraining.device_id == device_id)

        if training_status:
            query = query.filter(models.DeviceModelTraining.training_status == training_status)

        # 如果指定了项目ID，需要通过设备表关联
        if project_id:
            query = query.join(models.Device).filter(models.Device.project_id == project_id)

        # 如果搜索关键词不为空，搜索设备名称
        if search:
            query = query.join(models.Device).filter(
                models.Device.name.ilike(f"%{search}%") |
                models.Device.identifier.ilike(f"%{search}%")
            )

        # 计算总数
        total = query.count()

        # 分页查询
        trainings = query.order_by(
            models.DeviceModelTraining.updated_at.desc()
        ).offset(skip).limit(page_size).all()

        # 获取详细信息
        training_details = []
        for training in trainings:
            detail = get_training_detail(db, training)
            training_details.append(detail)

        # 计算总页数
        total_pages = (total + page_size - 1) // page_size

        return {
            "trainings": training_details,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }

    except Exception as e:
        logger.error(f"获取设备模型训练列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取设备模型训练列表失败: {str(e)}")


@router.get("/{training_id}", response_model=schemas.DeviceModelTrainingDetail)
def get_device_model_training(training_id: int, db: Session = Depends(get_db)):
    """获取单个设备模型训练详情"""
    try:
        training = db.query(models.DeviceModelTraining).filter(
            models.DeviceModelTraining.id == training_id
        ).first()

        if not training:
            raise HTTPException(status_code=404, detail="设备模型训练记录未找到")

        return get_training_detail(db, training)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取设备模型训练详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取设备模型训练详情失败: {str(e)}")


@router.get("/device/{device_id}", response_model=schemas.DeviceModelTrainingDetail)
def get_device_training_by_device(device_id: int, db: Session = Depends(get_db)):
    """通过设备ID获取训练信息"""
    try:
        training = db.query(models.DeviceModelTraining).filter(
            models.DeviceModelTraining.device_id == device_id
        ).first()

        if not training:
            # 如果没有训练记录，创建一个默认的
            training = create_default_training(db, device_id)

        return get_training_detail(db, training)

    except Exception as e:
        logger.error(f"获取设备训练信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取设备训练信息失败: {str(e)}")


@router.post("/", response_model=schemas.DeviceModelTraining, status_code=201)
def create_device_model_training(
        training_data: schemas.DeviceModelTrainingCreate,
        db: Session = Depends(get_db)
):
    """创建设备模型训练记录"""
    try:
        # 检查设备是否存在
        device = db.query(models.Device).filter(
            models.Device.id == training_data.device_id
        ).first()

        if not device:
            raise HTTPException(status_code=404, detail="设备未找到")

        # 检查是否已存在该设备的训练记录
        existing = db.query(models.DeviceModelTraining).filter(
            models.DeviceModelTraining.device_id == training_data.device_id
        ).first()

        if existing:
            raise HTTPException(status_code=400, detail="该设备已存在训练记录")

        # 如果指定了模型版本ID，检查是否存在
        if training_data.model_version_id:
            model_version = db.query(models.DeviceModelVersion).filter(
                models.DeviceModelVersion.id == training_data.model_version_id
            ).first()

            if not model_version:
                raise HTTPException(status_code=404, detail="模型版本未找到")

        # 创建设备模型训练记录
        db_training = models.DeviceModelTraining(
            device_id=training_data.device_id,
            model_version_id=training_data.model_version_id,
            model_type=training_data.model_type,
            training_interval_minutes=training_data.training_interval_minutes,
            prediction_interval_minutes=training_data.prediction_interval_minutes,
            performance_metrics=training_data.performance_metrics or {},
            training_details=training_data.training_details or {},
            training_status=training_data.training_status
        )

        db.add(db_training)
        db.commit()
        db.refresh(db_training)

        return db_training

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建设备模型训练记录失败: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建设备模型训练记录失败: {str(e)}")


@router.put("/{training_id}", response_model=schemas.DeviceModelTraining)
def update_device_model_training(
        training_id: int,
        training_update: schemas.DeviceModelTrainingUpdate,
        db: Session = Depends(get_db)
):
    """更新设备模型训练记录"""
    try:
        training = db.query(models.DeviceModelTraining).filter(
            models.DeviceModelTraining.id == training_id
        ).first()

        if not training:
            raise HTTPException(status_code=404, detail="设备模型训练记录未找到")

        # 更新字段
        update_data = training_update.dict(exclude_unset=True)

        for field, value in update_data.items():
            if hasattr(training, field):
                setattr(training, field, value)

        training.updated_at = datetime.now()
        db.commit()
        db.refresh(training)

        return training

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新设备模型训练记录失败: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新设备模型训练记录失败: {str(e)}")


@router.delete("/{training_id}", status_code=204)
def delete_device_model_training(training_id: int, db: Session = Depends(get_db)):
    """删除设备模型训练记录"""
    try:
        training = db.query(models.DeviceModelTraining).filter(
            models.DeviceModelTraining.id == training_id
        ).first()

        if not training:
            raise HTTPException(status_code=404, detail="设备模型训练记录未找到")

        db.delete(training)
        db.commit()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除设备模型训练记录失败: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除设备模型训练记录失败: {str(e)}")


@router.get("/stats/summary", response_model=schemas.TrainingStats)
def get_training_stats(db: Session = Depends(get_db)):
    """获取训练统计信息"""
    try:
        # 计算各种状态的设备数量
        total = db.query(models.DeviceModelTraining).count()
        trained = db.query(models.DeviceModelTraining).filter(
            models.DeviceModelTraining.training_status == 'trained'
        ).count()
        training = db.query(models.DeviceModelTraining).filter(
            models.DeviceModelTraining.training_status == 'training'
        ).count()
        failed = db.query(models.DeviceModelTraining).filter(
            models.DeviceModelTraining.training_status == 'failed'
        ).count()

        # 计算平均R²分数
        avg_r2_query = db.query(models.DeviceModelTraining).filter(
            models.DeviceModelTraining.training_status == 'trained',
            models.DeviceModelTraining.performance_metrics.has_key('r2_score')
        )

        total_r2 = 0
        count_r2 = 0

        for training in avg_r2_query.all():
            if training.performance_metrics and 'r2_score' in training.performance_metrics:
                total_r2 += training.performance_metrics['r2_score']
                count_r2 += 1

        avg_r2_score = total_r2 / count_r2 if count_r2 > 0 else 0

        # 计算平均训练时间
        avg_training_query = db.query(models.DeviceModelTraining).filter(
            models.DeviceModelTraining.training_status == 'trained',
            models.DeviceModelTraining.training_details.has_key('training_time_seconds')
        )

        total_seconds = 0
        count_time = 0

        for training in avg_training_query.all():
            if training.training_details and 'training_time_seconds' in training.training_details:
                total_seconds += training.training_details['training_time_seconds']
                count_time += 1

        avg_training_minutes = (total_seconds / count_time / 60) if count_time > 0 else 0

        return {
            "total_devices": total,
            "trained_devices": trained,
            "training_devices": training,
            "failed_devices": failed,
            "avg_r2_score": round(avg_r2_score, 2),
            "avg_training_time_minutes": round(avg_training_minutes, 1)
        }

    except Exception as e:
        logger.error(f"获取训练统计信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取训练统计信息失败: {str(e)}")


@router.post("/start/{device_id}", response_model=schemas.TrainingStatusResponse)
def start_training_for_device(device_id: int, db: Session = Depends(get_db)):
    """为设备开始训练"""
    try:
        # 获取或创建训练记录
        training = db.query(models.DeviceModelTraining).filter(
            models.DeviceModelTraining.device_id == device_id
        ).first()

        if not training:
            # 创建默认训练记录
            training = create_default_training(db, device_id)

        # 更新训练状态
        training.training_status = 'training'
        training.updated_at = datetime.now()
        db.commit()
        db.refresh(training)

        # TODO: 这里应该触发实际的训练任务
        logger.info(f"开始为设备 {device_id} 训练模型")

        return {
            "device_id": device_id,
            "training_status": training.training_status,
            "last_trained_at": training.last_trained_at,
            "performance_metrics": training.performance_metrics,
            "training_details": training.training_details
        }

    except Exception as e:
        logger.error(f"开始训练失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"开始训练失败: {str(e)}")


@router.post("/batch_start", response_model=schemas.BatchTrainingResponse)
def start_batch_training(
        batch_request: schemas.BatchTrainingRequest,
        db: Session = Depends(get_db)
):
    """批量开始训练"""
    try:
        results = []
        success = 0
        failed = 0

        for device_id in batch_request.device_ids:
            try:
                # 获取或创建训练记录
                training = db.query(models.DeviceModelTraining).filter(
                    models.DeviceModelTraining.device_id == device_id
                ).first()

                if not training:
                    training = create_default_training(db, device_id)

                # 更新训练状态
                training.training_status = 'training'
                training.updated_at = datetime.now()
                db.commit()

                results.append({
                    "device_id": device_id,
                    "status": "success",
                    "message": "训练任务已开始"
                })
                success += 1

                logger.info(f"开始为设备 {device_id} 批量训练模型")

            except Exception as e:
                results.append({
                    "device_id": device_id,
                    "status": "failed",
                    "message": str(e)
                })
                failed += 1

        db.commit()

        return {
            "total": len(batch_request.device_ids),
            "success": success,
            "failed": failed,
            "results": results
        }

    except Exception as e:
        logger.error(f"批量开始训练失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"批量开始训练失败: {str(e)}")


@router.post("/{device_id}/train", response_model=Dict[str, Any])
async def train_device_model(
        device_id: int,
        training_config: Optional[Dict[str, Any]] = Body(None),
        db: Session = Depends(get_db)
):
    """训练设备模型"""
    try:
        logger.info(f"开始训练设备 {device_id} 的模型")

        # 获取设备信息
        device = db.query(models.Device).filter(
            models.Device.id == device_id
        ).first()

        if not device:
            raise HTTPException(status_code=404, detail="设备未找到")

        # 获取训练管理器
        try:
            # 使用训练管理器
            from ml.models.trainer import ModelTrainingManager
            training_manager = ModelTrainingManager(db)

            # 确定目标特征
            target_feature = "point_value"  # 默认特征，可以根据实际情况调整

            # 调用真实训练
            result = training_manager.train_device_model(
                device_id=device_id,
                target_feature=target_feature,
                config=training_config
            )

            logger.info(f"训练完成: {result.get('training_success', False)}")

        except Exception as e:
            logger.error(f"训练过程出错: {str(e)}", exc_info=True)

            # 如果训练管理器失败，返回错误信息
            result = {
                'device_id': device_id,
                'training_success': False,
                'error': str(e),
                'error_type': e.__class__.__name__,
                'performance_metrics': {},
                'training_details': {'error': str(e), 'traceback': traceback.format_exc()},
                'config': training_config or {}
            }

        # 创建或更新训练记录
        training_record = db.query(models.DeviceModelTraining).filter(
            models.DeviceModelTraining.device_id == device_id
        ).first()

        if not training_record:
            training_record = models.DeviceModelTraining(
                device_id=device_id,
                model_version_id=device.model_version_id,
                model_type='xgboost',
                training_status='trained' if result.get('training_success') else 'failed'
            )
            db.add(training_record)
        else:
            training_record.training_status = 'trained' if result.get('training_success') else 'failed'

        if result.get('training_success'):
            training_record.last_trained_at = datetime.now()
            training_record.performance_metrics = result.get('performance_metrics', {})
            training_record.training_details = result.get('training_details', {})

        training_record.updated_at = datetime.now()
        db.commit()

        return result

    except Exception as e:
        logger.error(f"训练设备模型失败: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"训练失败: {str(e)}")


@router.post("/{device_id}/real_train", response_model=Dict[str, Any])
async def real_train_device_model(
        device_id: int,
        config: Optional[Dict] = Body(None),
        db: Session = Depends(get_db)
):
    """真实训练设备模型（使用预测计划中的输出数量及输出模式）"""
    try:
        logger.info(f"开始真实训练设备 {device_id} 的模型")

        # 1. 验证设备是否存在
        device = db.query(models.Device).filter(
            models.Device.id == device_id
        ).first()
        if not device:
            raise HTTPException(status_code=404, detail="设备未找到")

        # 2. 获取设备当前激活的预测计划（取第一个激活的计划）
        predict_schedule = db.query(models.TrainingSchedule).filter(
            models.TrainingSchedule.device_id == device_id,
            models.TrainingSchedule.schedule_type == 'predict',
            models.TrainingSchedule.is_active == True
        ).first()

        # 3. 根据预测计划确定输出模式和输出数量
        if predict_schedule:
            output_mode = predict_schedule.output_mode or 'single'
            output_count = predict_schedule.output_count or 1
        else:
            output_mode = 'single'
            output_count = 1

        logger.info(f"输出模式: {output_mode}, 输出数量: {output_count}")

        # 4. 准备训练配置
        if not config:
            config = {}

        # ========== 根据 output_mode 决定训练参数 ==========
        if output_mode == 'multi':
            # 直接多步训练：模型一次输出 output_count 个值
            config['forecast_horizon'] = output_count
            config['recursive_forecast'] = {'enabled': False, 'steps': 1}
            logger.info(f"直接多步训练: forecast_horizon={output_count}")
        else:
            # 单输出模式：模型每次输出 1 个值
            config['forecast_horizon'] = 1
            config['recursive_forecast'] = {
                'enabled': output_count > 1,
                'steps': output_count
            }
            if output_count > 1:
                logger.info(f"单步递归训练: 递归步数={output_count}")
            else:
                logger.info(f"普通单步训练: forecast_horizon=1")

        # 固定 look_back 及其他默认配置
        config['look_back'] = 24

        config.setdefault('lookback_days', 30)
        config.setdefault('train_ratio', 0.8)
        config.setdefault('xgboost_params', {})
        config.setdefault('preprocessing_config', {
            'missing_value_method': 'interpolate',
            'outlier_method': 'iqr',
            'create_time_features': True,
            'scaling_method': 'standard'
        })

        # 5. 确定目标特征
        target_feature = None
        if config and 'target_feature' in config:
            target_feature = config['target_feature']
        else:
            target_feature = "point_value"
            logger.info(f"使用默认目标特征: {target_feature}")

        # 6. 调用训练管理器执行真实训练
        from ml.ml_start import MLStart
        training_manager = MLStart(db)
        result = training_manager.real_train_device_model(
            device_id=device_id,
            target_feature=target_feature,
            config=config
        )

        # 7. 处理训练结果
        if result is None:
            result = {
                'device_id': device_id,
                'target_feature': target_feature,
                'training_success': False,
                'error_message': '训练管理器返回了None，可能是内部错误',
                'training_details': {},
                'trained_at': datetime.now().isoformat()
            }

        # 8. 更新设备训练记录
        training_record = db.query(models.DeviceModelTraining).filter(
            models.DeviceModelTraining.device_id == device_id
        ).first()

        if not training_record:
            training_record = models.DeviceModelTraining(
                device_id=device_id,
                model_version_id=device.model_version_id,
                training_status=result.get('training_status', 'failed')
            )
            db.add(training_record)

        if result.get('training_success'):
            training_record.training_status = 'trained'
            training_record.last_trained_at = datetime.now()
            training_record.performance_metrics = result.get('performance_metrics', {})
            training_record.training_details = result.get('training_details', {})
        else:
            training_record.training_status = 'failed'

        training_record.updated_at = datetime.now()
        db.commit()

        return result

    except Exception as e:
        logger.error(f"真实训练失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"真实训练失败: {str(e)}")


# 辅助函数
def get_training_detail(db: Session, training: models.DeviceModelTraining):
    """获取训练记录的详细信息"""
    # 获取设备信息
    device = db.query(models.Device).filter(
        models.Device.id == training.device_id
    ).first()

    if not device:
        raise HTTPException(status_code=404, detail="关联的设备未找到")

    # 获取项目信息
    project = db.query(models.Project).filter(
        models.Project.id == device.project_id
    ).first()

    # 获取模型版本信息
    model_version = None
    if training.model_version_id:
        model_version = db.query(models.DeviceModelVersion).filter(
            models.DeviceModelVersion.id == training.model_version_id
        ).first()

    # 获取设备模型信息
    device_model = None
    if model_version:
        device_model = db.query(models.DeviceModel).filter(
            models.DeviceModel.id == model_version.model_id
        ).first()

    return {
        **training.__dict__,
        "device": device,
        "model_version": model_version,
        "project": project,
        "device_model": device_model
    }


def create_default_training(db: Session, device_id: int):
    """创建默认的训练记录"""
    # 检查设备是否存在
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备未找到")

    # 创建设备模型训练记录
    training = models.DeviceModelTraining(
        device_id=device_id,
        model_version_id=device.model_version_id,
        model_type='xgboost',
        training_interval_minutes=720,
        prediction_interval_minutes=5,
        performance_metrics={},
        training_details={},
        training_status='not_started'
    )

    db.add(training)
    db.commit()
    db.refresh(training)

    return training