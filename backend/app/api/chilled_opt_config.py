#backend/app/api/chilled_opt_config.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from ..dependencies.database import get_db
from .. import models, schemas
import logging
from ..crud.chilled_opt_config import ChilledOptCRUD
import redis
import json
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chilled_opt_config", tags=["冷冻水优化"])

chilled_opt_crud = ChilledOptCRUD()

# Redis 配置
REDIS_CONFIG = {
    'host': settings.REDIS_HOST,
    'port': settings.REDIS_PORT,
    'db': settings.REDIS_DB,
    'password': settings.REDIS_PASSWORD,
    'decode_responses': True,
    'socket_connect_timeout': 2
}

redis_client = None
try:
    redis_client = redis.Redis(**REDIS_CONFIG)
    redis_client.ping()
    logger.info("Redis 连接成功")
except Exception as e:
    logger.warning(f"Redis 连接失败: {e}，迭代数据接口将不可用")

@router.get("/iteration/latest", response_model=schemas.ChilledOptIterationResponse)
async def get_latest_iteration():
    """获取最近一次优化迭代的全部温度组合计算结果"""
    if redis_client is None:
        raise HTTPException(status_code=503, detail="Redis 服务不可用")
    try:
        redis_key = f"{settings.PROGRAM_NAME}:chilled_opt:latest_iteration"
        data = redis_client.get(redis_key)
        if not data:
            raise HTTPException(status_code=404, detail="暂无迭代数据")
        return json.loads(data)
    except Exception as e:
        logger.error(f"获取迭代数据失败: {e}")
        raise HTTPException(status_code=500, detail="获取迭代数据失败")

@router.get("/iteration/page", response_model=schemas.ChilledOptIterationPageResponse)
async def get_iteration_page(
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(20, ge=1, le=200, description="每页记录数")
):
    """分页获取最近一次优化迭代的温度组合计算结果"""
    if redis_client is None:
        raise HTTPException(status_code=503, detail="Redis 服务不可用")
    try:
        redis_key = f"{settings.PROGRAM_NAME}:chilled_opt:latest_iteration"
        data = redis_client.get(redis_key)
        if not data:
            raise HTTPException(status_code=404, detail="暂无迭代数据")
        parsed = json.loads(data)
        combinations = parsed.get('combinations', [])
        total = len(combinations)
        start = skip
        end = skip + limit
        page_combinations = combinations[start:end]
        page = (skip // limit) + 1 if limit > 0 else 1
        return {
            "total": total,
            "page": page,
            "page_size": limit,
            "combinations": page_combinations
        }
    except Exception as e:
        logger.error(f"分页获取迭代数据失败: {e}")
        raise HTTPException(status_code=500, detail="获取迭代数据失败")

# ==================== 配置相关接口 ====================

@router.get("/config", response_model=schemas.ChilledOptConfigResponse)
async def get_config(db: Session = Depends(get_db)):
    try:
        config = chilled_opt_crud.get_config(db)
        if not config:
            config = models.ChilledOptConfig()
            db.add(config)
            db.commit()
            db.refresh(config)
            logger.info("创建了默认冷冻水优化配置")
        return config
    except Exception as e:
        logger.error(f"获取配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取配置失败")

@router.put("/config", response_model=schemas.ChilledOptConfigResponse)
async def update_config(
        config_update: schemas.ChilledOptConfigUpdate,
        db: Session = Depends(get_db)
):
    try:
        config = chilled_opt_crud.update_config(db, config_update)
        logger.info("冷冻水优化配置已更新")
        return config
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新配置失败: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")

# ==================== 参数相关接口 ====================

@router.get("/parameters", response_model=schemas.ChilledOptParametersTotalList)
async def get_parameters(
        skip: int = Query(0, ge=0, description="跳过记录数"),
        limit: int = Query(100, ge=1, le=200, description="每页记录数"),
        applied: Optional[bool] = Query(None, description="是否已应用"),
        start_date: Optional[datetime] = Query(None, description="开始时间"),
        end_date: Optional[datetime] = Query(None, description="结束时间"),
        db: Session = Depends(get_db)
):
    try:
        parameters = chilled_opt_crud.get_parameters(
            db, skip=skip, limit=limit, applied=applied,
            start_date=start_date, end_date=end_date
        )
        total = chilled_opt_crud.count_parameters(
            db, applied=applied, start_date=start_date, end_date=end_date
        )
        total_pages = (total + limit - 1) // limit if limit > 0 else 1
        current_page = (skip // limit) + 1 if limit > 0 else 1
        return schemas.ChilledOptParametersTotalList(
            parameters=parameters,
            total=total,
            page=current_page,
            page_size=limit,
            total_pages=total_pages
        )
    except Exception as e:
        logger.error(f"获取参数列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取参数列表失败")

@router.get("/parameters/latest", response_model=schemas.ChilledOptParametersTotalResponse)
async def get_latest_parameters(db: Session = Depends(get_db)):
    try:
        parameters = chilled_opt_crud.get_latest_parameters(db)
        if not parameters:
            raise HTTPException(status_code=404, detail="未找到优化参数")
        return parameters
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取最新参数失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取最新参数失败")

@router.get("/parameters/{parameter_id}", response_model=schemas.ChilledOptParametersTotalResponse)
async def get_parameter_by_id(
        parameter_id: int,
        db: Session = Depends(get_db)
):
    try:
        parameter = chilled_opt_crud.get_parameter_by_id(db, parameter_id)
        if not parameter:
            raise HTTPException(status_code=404, detail="未找到优化参数")
        return parameter
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取参数失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取参数失败")

@router.get("/parameters/stats", response_model=schemas.OptimizationStats)
async def get_optimization_stats(
        days: int = Query(30, ge=1, le=365, description="统计天数"),
        db: Session = Depends(get_db)
):
    try:
        stats = chilled_opt_crud.get_optimization_stats(db, days)
        return stats
    except Exception as e:
        logger.error(f"获取统计信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取统计信息失败")

@router.get("/parameters/history", response_model=List[schemas.ChilledOptParametersTotalResponse])
async def get_parameters_history(
        start_date: datetime = Query(..., description="开始时间"),
        end_date: datetime = Query(..., description="结束时间"),
        limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
        db: Session = Depends(get_db)
):
    try:
        parameters = chilled_opt_crud.get_parameters(
            db, skip=0, limit=limit, start_date=start_date, end_date=end_date
        )
        return parameters
    except Exception as e:
        logger.error(f"获取历史参数失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取历史参数失败")

@router.get("/parameters/history/field", response_model=List[schemas.DeviceHistoryFieldResponse])
async def get_device_field_history(
        field: str = Query(..., description="设备字段标识，如'total_power', 'host_total_power'等"),
        start_date: datetime = Query(..., description="开始时间"),
        end_date: datetime = Query(..., description="结束时间"),
        limit: int = Query(100, ge=1, le=1000, description="返回记录数上限"),
        db: Session = Depends(get_db)
):
    try:
        data = chilled_opt_crud.get_device_field_history(db, field, start_date, end_date, limit)
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取设备字段历史数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取历史数据失败")