# backend/app/crud/data_config.py
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from .. import models, schemas
from datetime import datetime


class DataConfigCRUD:
    """数据配置CRUD操作"""

    def get_config_by_device(self, db: Session, device_id: int) -> Optional[models.DeviceDataConfig]:
        """通过设备ID获取配置"""
        return db.query(models.DeviceDataConfig).filter(
            models.DeviceDataConfig.device_id == device_id
        ).first()

    def create_or_update_config(self, db: Session, device_id: int,
                                config_update: schemas.DeviceDataConfigUpdate) -> models.DeviceDataConfig:
        """创建或更新设备配置"""
        config = self.get_config_by_device(db, device_id)

        if config:
            # 更新现有配置
            update_data = config_update.dict(exclude_unset=True)
            for key, value in update_data.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            config.updated_at = datetime.now()
        else:
            # 创建新配置
            config_data = config_update.dict()
            config_data['device_id'] = device_id
            config = models.DeviceDataConfig(**config_data)
            db.add(config)

        db.commit()
        db.refresh(config)
        return config

    def delete_config_by_device(self, db: Session, device_id: int) -> bool:
        """删除设备配置"""
        config = self.get_config_by_device(db, device_id)
        if not config:
            return False

        db.delete(config)
        db.commit()
        return True