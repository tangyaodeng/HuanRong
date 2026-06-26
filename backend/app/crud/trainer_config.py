# backend/app/crud/trainer_config.py
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from .. import models, schemas


class TrainerConfigCRUD:
    """训练器配置CRUD操作"""

    def get_config_by_id(self, db: Session, config_id: int) -> Optional[models.TrainerConfig]:
        """通过ID获取配置"""
        return db.query(models.TrainerConfig).filter(
            models.TrainerConfig.id == config_id
        ).first()

    def get_device_configs(self, db: Session, device_id: int) -> List[models.TrainerConfig]:
        """获取设备的所有配置"""
        return db.query(models.TrainerConfig).filter(
            models.TrainerConfig.device_id == device_id
        ).order_by(
            models.TrainerConfig.is_primary.desc(),
            models.TrainerConfig.created_at.desc()
        ).all()

    def get_config_by_device_and_path(
            self,
            db: Session,
            device_id: int,
            trainer_path: str
    ) -> Optional[models.TrainerConfig]:
        """通过设备和路径获取配置"""
        return db.query(models.TrainerConfig).filter(
            models.TrainerConfig.device_id == device_id,
            models.TrainerConfig.trainer_path == trainer_path
        ).first()

    def get_primary_configs(self, db: Session, device_id: int) -> List[models.TrainerConfig]:
        """获取设备的主配置"""
        return db.query(models.TrainerConfig).filter(
            models.TrainerConfig.device_id == device_id,
            models.TrainerConfig.is_primary == True,
            models.TrainerConfig.is_active == True
        ).all()

    def get_active_configs(self, db: Session, device_id: int) -> List[models.TrainerConfig]:
        """获取设备的活跃配置"""
        return db.query(models.TrainerConfig).filter(
            models.TrainerConfig.device_id == device_id,
            models.TrainerConfig.is_active == True
        ).order_by(models.TrainerConfig.is_primary.desc()).all()



    def update_config(
            self,
            db: Session,
            config_id: int,
            config_update: schemas.TrainerConfigUpdate
    ) -> Optional[models.TrainerConfig]:
        """更新训练器配置"""
        config = self.get_config_by_id(db, config_id)
        if not config:
            return None

        update_data = config_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(config, key, value)

        config.updated_at = datetime.now()
        db.commit()
        db.refresh(config)
        return config


    def get_device_primary_trainer(self, db: Session, device_id: int) -> Optional[models.TrainerConfig]:
        """获取设备的主训练器配置"""
        return db.query(models.TrainerConfig).filter(
            models.TrainerConfig.device_id == device_id,
            models.TrainerConfig.is_primary == True,
            models.TrainerConfig.is_active == True
        ).first()

    def create_config(self, db: Session, config_data:schemas.TrainerConfigCreate) -> models.TrainerConfig:
        db_config = models.TrainerConfig(**config_data.dict())
        db.add(db_config)
        db.commit()
        db.refresh(db_config)
        return db_config

