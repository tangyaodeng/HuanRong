# backend/app/crud/model_training.py
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import datetime
from .. import models, schemas


class TrainingCRUD:
    def __init__(self, db: Session):
        self.db = db

    # 创建设备模型训练记录
    def create_device_model_training(
            self,
            device_id: int,
            model_version_id: Optional[int] = None,
            model_type: str = 'xgboost',
            training_status: str = 'training'
    ) -> models.DeviceModelTraining:
        """创建设备模型训练记录"""
        try:
            # 检查是否已存在
            existing = self.get_training_by_device(device_id)
            if existing:
                return existing

            # 创建新记录
            db_training = models.DeviceModelTraining(
                device_id=device_id,
                model_version_id=model_version_id,
                model_type=model_type,
                training_status=training_status,
                training_interval_minutes=720,  # 默认12小时
                prediction_interval_minutes=5,  # 默认5分钟
                performance_metrics={},
                training_details={}
            )

            self.db.add(db_training)
            self.db.commit()
            self.db.refresh(db_training)
            return db_training
        except Exception as e:
            self.db.rollback()
            raise e

    # 更新训练状态
    def update_training_status(
            self,
            training_id: int,
            status: str,
            performance_metrics: Optional[Dict] = None,
            training_details: Optional[Dict] = None
    ) -> models.DeviceModelTraining:
        """更新训练状态"""
        training = self.db.query(models.DeviceModelTraining).filter(
            models.DeviceModelTraining.id == training_id
        ).first()

        if not training:
            raise ValueError(f"训练记录 {training_id} 不存在")

        training.training_status = status
        training.updated_at = datetime.now()

        if status == 'trained' or status == 'failed':
            training.last_trained_at = datetime.now()

        if performance_metrics:
            training.performance_metrics = performance_metrics

        if training_details:
            training.training_details = training_details

        self.db.commit()
        self.db.refresh(training)
        return training

    # 通过设备ID获取训练记录
    def get_training_by_device(self, device_id: int) -> Optional[models.DeviceModelTraining]:
        """通过设备ID获取训练记录"""
        return self.db.query(models.DeviceModelTraining).filter(
            models.DeviceModelTraining.device_id == device_id
        ).first()

    # 获取所有训练记录
    def get_all_trainings(
            self,
            skip: int = 0,
            limit: int = 100,
            status: Optional[str] = None,
            project_id: Optional[int] = None
    ) -> List[models.DeviceModelTraining]:
        """获取所有训练记录"""
        query = self.db.query(models.DeviceModelTraining)

        if status:
            query = query.filter(models.DeviceModelTraining.training_status == status)

        if project_id:
            # 需要通过设备关联项目
            query = query.join(models.Device).filter(models.Device.project_id == project_id)

        return query.order_by(
            models.DeviceModelTraining.updated_at.desc()
        ).offset(skip).limit(limit).all()

    # 创建设备训练计划
    def create_training_schedule(
            self,
            device_id: int,
            schedule_type: str,
            start_time: datetime,
            end_time: Optional[datetime] = None,
            interval_value: int = 12,
            interval_unit: str = 'hours',
            is_active: bool = True
    ) -> models.TrainingSchedule:
        """创建设备训练计划"""
        # 计算下次运行时间
        next_run_at = start_time

        schedule = models.TrainingSchedule(
            device_id=device_id,
            schedule_type=schedule_type,
            start_time=start_time,
            end_time=end_time,
            interval_value=interval_value,
            interval_unit=interval_unit,
            next_run_at=next_run_at,
            is_active=is_active
        )

        self.db.add(schedule)
        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    # 获取设备训练计划
    def get_device_schedules(
            self,
            device_id: int,
            schedule_type: Optional[str] = None
    ) -> List[models.TrainingSchedule]:
        """获取设备训练计划"""
        query = self.db.query(models.TrainingSchedule).filter(
            models.TrainingSchedule.device_id == device_id
        )

        if schedule_type:
            query = query.filter(models.TrainingSchedule.schedule_type == schedule_type)

        return query.order_by(models.TrainingSchedule.next_run_at).all()

    # 更新训练统计信息
    def update_training_stats(self, training_id: int, stats: Dict[str, Any]) -> None:
        """更新训练统计信息"""
        training = self.db.query(models.DeviceModelTraining).filter(
            models.DeviceModelTraining.id == training_id
        ).first()

        if training:
            training.performance_metrics = stats
            self.db.commit()

    # 删除训练记录
    def delete_training(self, training_id: int) -> bool:
        """删除训练记录"""
        training = self.db.query(models.DeviceModelTraining).filter(
            models.DeviceModelTraining.id == training_id
        ).first()

        if training:
            self.db.delete(training)
            self.db.commit()
            return True
        return False

    # 获取训练统计
    def get_training_stats(self) -> Dict[str, Any]:
        """获取训练统计"""
        total = self.db.query(models.DeviceModelTraining).count()
        trained = self.db.query(models.DeviceModelTraining).filter(
            models.DeviceModelTraining.training_status == 'trained'
        ).count()
        training = self.db.query(models.DeviceModelTraining).filter(
            models.DeviceModelTraining.training_status == 'training'
        ).count()
        failed = self.db.query(models.DeviceModelTraining).filter(
            models.DeviceModelTraining.training_status == 'failed'
        ).count()

        return {
            "total": total,
            "trained": trained,
            "training": training,
            "failed": failed
        }

