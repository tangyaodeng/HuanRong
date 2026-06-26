# backend/app/api/trainer_config.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging
from ..utils.trainer_utils import generate_trainer_file, trainer_file_exists
from ..schemas import TrainerConfigCreate

from ..dependencies.database import get_db
from .. import models, schemas
from ..crud.trainer_config import TrainerConfigCRUD

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trainer_config", tags=["trainer_config"])
crud = TrainerConfigCRUD()

@router.post("/create", response_model=schemas.TrainerConfigResponse)
async def create_trainer_config(
    config_data: schemas.TrainerConfigCreate,
    db: Session = Depends(get_db)
):
    """创建新的训练器配置，自动生成对应的训练器文件（如果不存在）"""
    try:
        # 检查设备是否存在
        device = db.query(models.Device).filter(models.Device.id == config_data.device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="设备不存在")

        # 尝试生成/检查训练器文件
        if not trainer_file_exists(config_data.device_id):
            trainer_path = generate_trainer_file(config_data.device_id)
        else:
            trainer_path = f"ml/models/trainers/device{config_data.device_id}_xgboost_v1.py"

        # 构造数据库记录所需的路径（存储为模块路径形式）
        module_path = f"ml.models.trainers.device{config_data.device_id}_xgboost_v1.XGBoostTrainer"

        # 检查是否已存在相同路径的配置
        existing = crud.get_config_by_device_and_path(db, config_data.device_id, module_path)
        if existing:
            raise HTTPException(status_code=400, detail="该训练器配置已存在")

        # 创建配置（使用模块路径作为 trainer_path）
        new_config_data = config_data.copy(update={"trainer_path": module_path})
        new_config = crud.create_config(db, new_config_data)

        # 丰富响应
        response = schemas.TrainerConfigResponse.from_orm(new_config)
        response.device_name = device.name
        if device.project:
            response.project_name = device.project.name

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建训练器配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建配置失败: {str(e)}")

@router.get("/device/{device_id}", response_model=List[schemas.TrainerConfigResponse])
async def get_device_trainer_configs(
        device_id: int,
        db: Session = Depends(get_db)
):
    """获取设备的所有训练器配置"""
    try:
        configs = crud.get_device_configs(db, device_id=device_id)

        if not configs:
            return []

        # 获取设备信息以丰富响应
        device = db.query(models.Device).filter(models.Device.id == device_id).first()
        device_name = device.name if device else None

        # 获取项目信息
        project_name = None
        if device and device.project:
            project_name = device.project.name

        # 丰富配置信息
        enriched_configs = []
        for config in configs:
            config_dict = schemas.TrainerConfigResponse.from_orm(config)
            config_dict.device_name = device_name
            config_dict.project_name = project_name
            enriched_configs.append(config_dict)

        return enriched_configs

    except Exception as e:
        logger.error(f"获取设备训练器配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")



@router.put("/{config_id}", response_model=schemas.TrainerConfigResponse)
async def update_trainer_config(
        config_id: int,
        config_update: schemas.TrainerConfigUpdate,
        db: Session = Depends(get_db)
):
    """更新训练器配置"""
    try:
        # 检查配置是否存在
        config = crud.get_config_by_id(db, config_id)
        if not config:
            raise HTTPException(status_code=404, detail="配置未找到")

        # 如果设置为主配置，需要先取消其他主配置
        if config_update.is_primary:
            primary_configs = crud.get_primary_configs(db, device_id=config.device_id)
            for primary_config in primary_configs:
                if primary_config.id != config_id and primary_config.id:
                    crud.update_config(
                        db,
                        config_id=primary_config.id,
                        config_update=schemas.TrainerConfigUpdate(is_primary=False)
                    )

        # 更新配置
        updated_config = crud.update_config(db, config_id, config_update)

        # 丰富响应信息
        response = schemas.TrainerConfigResponse.from_orm(updated_config)
        if config.device:
            response.device_name = config.device.name
            if config.device.project:
                response.project_name = config.device.project.name

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新训练器配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")



@router.post("/set_primary/{config_id}", response_model=schemas.TrainerConfigResponse)
async def set_primary_trainer_config(
        config_id: int,
        db: Session = Depends(get_db)
):
    """设置主训练器配置"""
    try:
        # 检查配置是否存在
        config = crud.get_config_by_id(db, config_id)
        if not config:
            raise HTTPException(status_code=404, detail="配置未找到")

        # 如果已经激活，直接返回
        if config.is_primary:
            return schemas.TrainerConfigResponse.from_orm(config)

        # 取消其他主配置
        primary_configs = crud.get_primary_configs(db, device_id=config.device_id)
        for primary_config in primary_configs:
            if primary_config.id != config_id and primary_config.id:
                crud.update_config(
                    db,
                    config_id=primary_config.id,
                    config_update=schemas.TrainerConfigUpdate(is_primary=False)
                )

        # 设置当前配置为主配置
        updated_config = crud.update_config(
            db,
            config_id,
            schemas.TrainerConfigUpdate(is_primary=True)
        )

        # 丰富响应信息
        response = schemas.TrainerConfigResponse.from_orm(updated_config)
        if config.device:
            response.device_name = config.device.name
            if config.device.project:
                response.project_name = config.device.project.name

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"设置主训练器配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"设置主配置失败: {str(e)}")



@router.get("/stats/{device_id}", response_model=schemas.TrainerConfigStats)
async def get_trainer_config_stats(
        device_id: int,
        db: Session = Depends(get_db)
):
    """获取训练器配置统计"""
    try:
        # 获取所有配置
        configs = crud.get_device_configs(db, device_id=device_id)

        # 统计信息
        total_configs = len(configs)
        active_configs = len([c for c in configs if c.is_active])
        primary_configs = len([c for c in configs if c.is_primary])

        # 按训练器类型统计
        by_trainer_type = {}
        for config in configs:
            trainer_type = config.trainer_type or "unknown"
            by_trainer_type[trainer_type] = by_trainer_type.get(trainer_type, 0) + 1

        # 设备信息
        device = db.query(models.Device).filter(models.Device.id == device_id).first()
        by_device = [{
            "device_id": device_id,
            "device_name": device.name if device else "未知设备",
            "total_configs": total_configs,
            "active_configs": active_configs,
            "primary_configs": primary_configs,
            "last_updated": max([c.updated_at for c in configs]) if configs else None
        }] if device else []

        return schemas.TrainerConfigStats(
            total_configs=total_configs,
            active_configs=active_configs,
            primary_configs=primary_configs,
            by_trainer_type=by_trainer_type,
            by_device=by_device
        )

    except Exception as e:
        logger.error(f"获取训练器配置统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")