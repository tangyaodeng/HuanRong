# backend/app/api/data_config.py
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from ..dependencies.database import get_db
from .. import models, schemas
import logging
from datetime import datetime
from ..crud.data_config import DataConfigCRUD

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data_config", tags=["data_config"])

# 初始化CRUD
data_config_crud = DataConfigCRUD()


@router.get("/device/{device_id}", response_model=schemas.DeviceDataConfigResponse)
async def get_device_data_config(
        device_id: int,
        db: Session = Depends(get_db)
):
    """获取设备的数据加载配置"""
    try:
        config = data_config_crud.get_config_by_device(db, device_id)

        if not config:
            # 如果不存在，返回默认配置（但不保存到数据库）
            from ml.data.loader import get_data_loader
            loader = get_data_loader(db)
            default_config = loader.get_device_data_config(device_id)

            # 生成一个虚拟的UUID用于响应
            import uuid

            return {
                "device_id": device_id,
                "data_start_time": default_config.get('data_start_time'),
                "data_end_time": default_config.get('data_end_time'),
                "max_rows_limit": default_config.get('max_rows_limit'),
                "enable_steady_state_filter": default_config.get('enable_steady_state_filter', True),
                "steady_window": default_config.get('steady_window', 4),
                "steady_threshold_pct": default_config.get('steady_threshold_pct', 0.01),
                "min_power_pct": default_config.get('min_power_pct', 0.2),
                "id": 0,
                "uuid": uuid.uuid4(),  # 使用生成的UUID
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }

        return config

    except Exception as e:
        logger.error(f"获取设备数据配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取设备数据配置失败: {str(e)}")


@router.post("/device/{device_id}", response_model=schemas.DeviceDataConfigResponse)
async def save_device_data_config(
        device_id: int,
        config_update: schemas.DeviceDataConfigUpdate,
        db: Session = Depends(get_db)
):
    """保存设备的数据加载配置"""
    try:
        # 验证设备存在
        device = db.query(models.Device).filter(models.Device.id == device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="设备未找到")

        # 保存配置
        config = data_config_crud.create_or_update_config(db, device_id, config_update)

        return config

    except Exception as e:
        logger.error(f"保存设备数据配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"保存设备数据配置失败: {str(e)}")


@router.delete("/device/{device_id}", status_code=204)
async def delete_device_data_config(
        device_id: int,
        db: Session = Depends(get_db)
):
    """删除设备的数据加载配置（恢复默认）"""
    try:
        deleted = data_config_crud.delete_config_by_device(db, device_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="设备配置未找到")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除设备数据配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除设备数据配置失败: {str(e)}")


@router.get("/defaults", response_model=Dict[str, Any])
async def get_default_data_config():
    """获取系统默认的数据加载配置"""
    try:
        from ml.data.loader import MySQLDataLoader

        # 创建临时加载器实例以获取默认值
        loader = MySQLDataLoader()

        return {
            "DEFAULT_START_TIME": loader.DEFAULT_START_TIME,
            "DEFAULT_END_TIME": loader.DEFAULT_END_TIME,
            "MAX_ROWS_DEFAULT": loader.MAX_ROWS_DEFAULT,
        }

    except Exception as e:
        logger.error(f"获取默认配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取默认配置失败: {str(e)}")