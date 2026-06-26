from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from ..dependencies.database import get_db
from .. import schemas
from ..crud.model_evaluation import ModelEvaluationCRUD
import logging
from ..models import TrainingSchedule
from sqlalchemy import func

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/model_evaluation", tags=["model_evaluation"])


@router.post("/", response_model=schemas.ModelEvaluationResponse, status_code=201)
async def create_model_evaluation(
        evaluation: schemas.ModelEvaluationCreate,
        db: Session = Depends(get_db)
):
    """创建设备模型评估记录"""
    try:
        crud = ModelEvaluationCRUD(db)

        # 检查设备是否存在
        from .. import models
        device = db.query(models.Device).filter(
            models.Device.id == evaluation.device_id
        ).first()

        if not device:
            raise HTTPException(status_code=404, detail="设备未找到")

        # 创建评估记录
        db_evaluation = crud.create_model_evaluation(
            device_id=evaluation.device_id,
            r_squared=evaluation.r_squared,
            rmse=evaluation.rmse,
            mae=evaluation.mae,
            training_time=evaluation.training_time,  # 直接传递秒数
            training_data_size=evaluation.training_data_size,
            test_data_size=evaluation.test_data_size,
            feature_count=evaluation.feature_count
        )

        # 转换为响应格式
        response_data = {
            "id": db_evaluation.id,
            "device_id": db_evaluation.model_id,
            "r_squared": float(db_evaluation.r_squared),
            "rmse": float(db_evaluation.rmse),
            "mae": float(db_evaluation.mae),
            "training_time": int(db_evaluation.training_time.total_seconds()) if db_evaluation.training_time else 0,
            "training_data_size": db_evaluation.training_data_size,
            "test_data_size": db_evaluation.test_data_size,
            "feature_count": db_evaluation.feature_count,
            "created_at": db_evaluation.created_at,
            "updated_at": db_evaluation.updated_at
        }

        return schemas.ModelEvaluationResponse(**response_data)

    except Exception as e:
        logger.error(f"创建模型评估失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建模型评估失败: {str(e)}")


@router.get("/device/{device_id}/latest", response_model=schemas.ModelEvaluationResponse)
async def get_latest_device_evaluation(
        device_id: int = Path(..., title="设备ID", ge=1),
        db: Session = Depends(get_db)
):
    try:
        crud = ModelEvaluationCRUD(db)
        evaluation = crud.get_latest_evaluation_by_device(device_id)

        if not evaluation:
            raise HTTPException(status_code=404, detail="该设备暂无评估记录")

        # 转换数据库对象为响应格式
        response_data = {
            "id": evaluation.id,
            "device_id": evaluation.model_id,  # 映射model_id到device_id
            "r_squared": float(evaluation.r_squared),
            "rmse": float(evaluation.rmse),
            "mae": float(evaluation.mae),
            "training_time": int(evaluation.training_time.total_seconds()) if evaluation.training_time else 0,
            "training_data_size": evaluation.training_data_size,
            "test_data_size": evaluation.test_data_size,
            "feature_count": evaluation.feature_count,
            "created_at": evaluation.created_at,
            "updated_at": evaluation.updated_at
        }

        return schemas.ModelEvaluationResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取设备评估记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取设备评估记录失败: {str(e)}")


@router.get("/device/{device_id}/all", response_model=List[schemas.ModelEvaluationResponse])
async def get_device_evaluations(
        device_id: int = Path(..., title="设备ID", ge=1),
        limit: int = Query(10, ge=1, le=100, description="返回记录数量限制"),
        db: Session = Depends(get_db)
):
    """获取设备的所有评估记录"""
    try:
        crud = ModelEvaluationCRUD(db)
        evaluations = crud.get_device_evaluations(device_id, limit)

        # 转换每条记录
        response_list = []
        for evaluation in evaluations:
            response_data = {
                "id": evaluation.id,
                "device_id": evaluation.model_id,
                "r_squared": float(evaluation.r_squared),
                "rmse": float(evaluation.rmse),
                "mae": float(evaluation.mae),
                "training_time": int(evaluation.training_time.total_seconds()) if evaluation.training_time else 0,
                "training_data_size": evaluation.training_data_size,
                "test_data_size": evaluation.test_data_size,
                "feature_count": evaluation.feature_count,
                "created_at": evaluation.created_at,
                "updated_at": evaluation.updated_at
            }
            response_list.append(schemas.ModelEvaluationResponse(**response_data))

        return response_list

    except Exception as e:
        logger.error(f"获取设备评估列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取设备评估列表失败: {str(e)}")


@router.get("/metrics/{device_id}", response_model=schemas.DeviceMetricsResponse)
async def get_device_metrics(
        device_id: int = Path(..., title="设备ID", ge=1),
        db: Session = Depends(get_db)
):
    try:
        from .. import models

        device = db.query(models.Device).filter(models.Device.id == device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="设备未找到")

        project = db.query(models.Project).filter(models.Project.id == device.project_id).first()

        model_version = None
        model_name = "未配置"
        if device.model_version_id:
            model_version = db.query(models.DeviceModelVersion).filter(
                models.DeviceModelVersion.id == device.model_version_id
            ).first()
            if model_version:
                model = db.query(models.DeviceModel).filter(
                    models.DeviceModel.id == model_version.model_id
                ).first()
                if model:
                    model_name = model.name

        crud = ModelEvaluationCRUD(db)
        latest_evaluation = crud.get_latest_evaluation_by_device(device_id)

        latest_evaluation_response = None
        if latest_evaluation:
            latest_evaluation_response = schemas.ModelEvaluationResponse(
                id=latest_evaluation.id,
                device_id=latest_evaluation.model_id,
                r_squared=float(latest_evaluation.r_squared),
                rmse=float(latest_evaluation.rmse),
                mae=float(latest_evaluation.mae),
                training_time=int(latest_evaluation.training_time.total_seconds()) if latest_evaluation.training_time else 0,
                training_data_size=latest_evaluation.training_data_size,
                test_data_size=latest_evaluation.test_data_size,
                feature_count=latest_evaluation.feature_count,
                created_at=latest_evaluation.created_at,
                updated_at=latest_evaluation.updated_at
            )

        performance_summary = None
        if latest_evaluation:
            performance_summary = {
                "r_squared": latest_evaluation.r_squared,
                "rmse": latest_evaluation.rmse,
                "mae": latest_evaluation.mae,
                "training_time_minutes": latest_evaluation.training_time.seconds // 60 if latest_evaluation.training_time else 0,
                "training_data_size": latest_evaluation.training_data_size,
                "test_data_size": latest_evaluation.test_data_size,
                "feature_count": latest_evaluation.feature_count,
                "evaluated_at": latest_evaluation.created_at
            }

        # ---------- 关键修复：获取最后训练时间 ----------
        # 1. 从训练计划表获取
        last_train_run = db.query(
            func.max(TrainingSchedule.last_run_at)
        ).filter(
            TrainingSchedule.device_id == device_id,
            TrainingSchedule.schedule_type == 'train'
        ).scalar()
        logger.info(f"设备 {device_id} TrainingSchedule.last_run_at: {last_train_run}")

        # 2. 如果为空，从设备训练记录获取
        if not last_train_run:
            training_record = db.query(models.DeviceModelTraining).filter(
                models.DeviceModelTraining.device_id == device_id
            ).first()
            if training_record:
                last_train_run = training_record.last_trained_at
                logger.info(f"设备 {device_id} DeviceModelTraining.last_trained_at: {last_train_run}")

        # 3. 最终备选：使用最新评估记录的创建时间
        if not last_train_run and latest_evaluation:
            last_train_run = latest_evaluation.created_at
            logger.info(f"设备 {device_id} 使用评估记录创建时间: {last_train_run}")

        return {
            "device_id": device_id,
            "device_name": device.name,
            "project_name": project.name if project else "未知项目",
            "model_name": model_name,
            "model_version": model_version.version if model_version else "v1.0",
            "latest_evaluation": latest_evaluation_response,
            "performance_summary": performance_summary,
            "last_train_run_at": last_train_run
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取设备指标失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取设备指标失败: {str(e)}")


@router.delete("/{evaluation_id}", status_code=204)
async def delete_model_evaluation(
        evaluation_id: int = Path(..., title="评估记录ID", ge=1),
        db: Session = Depends(get_db)
):
    """删除评估记录"""
    try:
        crud = ModelEvaluationCRUD(db)
        success = crud.delete_evaluation(evaluation_id)

        if not success:
            raise HTTPException(status_code=404, detail="评估记录未找到")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除评估记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除评估记录失败: {str(e)}")


@router.get("/stats/", response_model=Dict[str, Any])
async def get_evaluation_stats(
        device_id: Optional[int] = Query(None, description="设备ID，可选"),
        db: Session = Depends(get_db)
):
    """获取评估统计信息"""
    try:
        crud = ModelEvaluationCRUD(db)
        stats = crud.get_evaluation_stats(device_id)

        return stats

    except Exception as e:
        logger.error(f"获取评估统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取评估统计失败: {str(e)}")