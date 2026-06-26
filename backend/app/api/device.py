from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from ..dependencies.database import get_db
from .. import models
from sqlalchemy import func, or_
import logging
from ..models import TrainingSchedule
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/devices", tags=["devices"])


# ==================== 基础设备端点 ====================

@router.get("/", response_model=Dict[str, Any])
def read_devices(
        db: Session = Depends(get_db),
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(10, ge=1, le=100, description="每页数量"),
        project_id: Optional[int] = Query(None, description="项目ID筛选"),
        status: Optional[str] = Query(None, description="状态筛选"),
        plan_status: Optional[str] = Query(None, description="训练计划状态筛选"),  # 新增
        search: Optional[str] = Query(None, description="搜索关键词")
):
    """获取设备列表（分页、搜索、筛选），包含最近一次预测计划执行时间"""
    logger.info(
        f"请求设备列表: page={page}, page_size={page_size}, project_id={project_id}, status={status}, search={search}"
    )

    try:
        skip = (page - 1) * page_size

        # 构建基础查询（只查询设备，不关联其他表，保证计数准确）
        base_query = db.query(models.Device)

        # 项目筛选
        if project_id:
            base_query = base_query.filter(models.Device.project_id == project_id)

        # 状态筛选
        if status:
            base_query = base_query.filter(models.Device.status == status)

        # 搜索
        if search:
            search_filter = or_(
                models.Device.name.ilike(f"%{search}%"),
                models.Device.identifier.ilike(f"%{search}%"),
                models.Device.description.ilike(f"%{search}%"),
                models.Device.location.ilike(f"%{search}%"),
            )
            base_query = base_query.filter(search_filter)

        # ========== 新增：训练计划状态筛选 ==========
        if plan_status:
            # 子查询：每个设备最新的训练计划（按id降序取最新）
            # 1. 获取所有训练计划的设备ID、is_active，并标序号
            subq = db.query(
                TrainingSchedule.device_id,
                TrainingSchedule.is_active,
                func.row_number().over(
                    partition_by=TrainingSchedule.device_id,
                    order_by=TrainingSchedule.id.desc()
                ).label('rn')
            ).filter(TrainingSchedule.schedule_type == 'train').subquery()

            # 2. 取每个设备最新的一条记录
            latest_plan = db.query(
                subq.c.device_id,
                subq.c.is_active
            ).filter(subq.c.rn == 1).subquery()

            if plan_status == 'active_plan':
                # 设备必须有训练计划且 is_active = True
                base_query = base_query.join(latest_plan, models.Device.id == latest_plan.c.device_id).filter(
                    latest_plan.c.is_active == True)
            elif plan_status == 'inactive_plan':
                # 设备必须有训练计划且 is_active = False
                base_query = base_query.join(latest_plan, models.Device.id == latest_plan.c.device_id).filter(
                    latest_plan.c.is_active == False)
            elif plan_status == 'no_plan':
                # 设备没有任何训练计划（即不在 latest_plan 中）
                # 使用左连接并检查设备ID为空
                base_query = base_query.outerjoin(latest_plan, models.Device.id == latest_plan.c.device_id).filter(
                    latest_plan.c.device_id.is_(None))

        # 计算总数
        total = base_query.count()

        # 获取分页的设备数据
        devices = base_query.order_by(models.Device.updated_at.desc()).offset(skip).limit(page_size).all()

        # 批量获取这些设备的最后训练时间（schedule_type='train' 的最近一次 last_run_at）
        device_ids = [device.id for device in devices]
        last_train_map = {}
        if device_ids:
            # 子查询：每个设备最大的 last_run_at
            results = db.query(
                TrainingSchedule.device_id,
                func.max(TrainingSchedule.last_run_at).label('last_train_run_at')
            ).filter(
                TrainingSchedule.device_id.in_(device_ids),
                TrainingSchedule.schedule_type == 'train'
            ).group_by(TrainingSchedule.device_id).all()
            last_train_map = {r[0]: r[1] for r in results}
        # 批量获取这些设备的最新 R² 分数
        device_ids = [device.id for device in devices]
        r2_map = {}
        if device_ids:
            from ..models import ModelEvaluation
            # 子查询：每个设备最大 created_at 对应的评估记录
            max_created_subq = db.query(
                ModelEvaluation.model_id,
                func.max(ModelEvaluation.created_at).label('max_created')
            ).filter(ModelEvaluation.model_id.in_(device_ids)).group_by(ModelEvaluation.model_id).subquery()
            # 联查得到完整的评估记录
            latest_evals = db.query(ModelEvaluation).join(
                max_created_subq,
                (ModelEvaluation.model_id == max_created_subq.c.model_id) &
                (ModelEvaluation.created_at == max_created_subq.c.max_created)
            ).all()
            for eval in latest_evals:
                r2_map[eval.model_id] = float(eval.r_squared) if eval.r_squared is not None else None
            # ========== 新增：获取训练计划状态 ==========
        train_plan_map = {}  # device_id -> is_active (True/False/None)
        if device_ids:
            # 子查询：每个设备最新的训练计划 id
            subq = db.query(
                TrainingSchedule.device_id,
                func.max(TrainingSchedule.id).label('max_id')
            ).filter(
                TrainingSchedule.device_id.in_(device_ids),
                TrainingSchedule.schedule_type == 'train'
            ).group_by(TrainingSchedule.device_id).subquery()
            latest_plans = db.query(TrainingSchedule).join(
                subq,
                (TrainingSchedule.device_id == subq.c.device_id) &
                (TrainingSchedule.id == subq.c.max_id)
            ).all()
            for plan in latest_plans:
                train_plan_map[plan.device_id] = plan.is_active

        # 辅助函数
        def _get_training_plan_status(is_active):
            if is_active is None:
                return "no_plan"
            elif is_active:
                return "active_plan"
            else:
                return "inactive_plan"
        # 格式化设备数据
        device_list = []
        for device in devices:
            device_data = {
                "id": device.id,
                "uuid": str(device.uuid),
                "name": device.name,
                "identifier": device.identifier,
                "description": device.description,
                "status": device.status,
                "location": device.location,
                "project_id": device.project_id,
                "device_metadata": device.device_metadata or {},
                "created_at": device.created_at.isoformat() if device.created_at else None,
                "updated_at": device.updated_at.isoformat() if device.updated_at else None,
                # 新增字段：最近一次预测计划执行时间
                "last_train_run_at": last_train_map.get(device.id).isoformat() if last_train_map.get(device.id) else None,
                "latest_r2_score": r2_map.get(device.id),
                "training_plan_status": _get_training_plan_status(train_plan_map.get(device.id)),
            }

            # 添加项目信息（如果有关联）
            if device.project:
                device_data["project"] = {
                    "id": device.project.id,
                    "name": device.project.name,
                    "code": device.project.code
                }

            # 添加设备模型和版本信息（从设备模型训练表获取准确信息）
            training_info = db.query(models.DeviceModelTraining).filter(
                models.DeviceModelTraining.device_id == device.id
            ).first()

            if training_info and training_info.model_version:
                device_data["model_version_info"] = {
                    "id": training_info.model_version.id,
                    "version": training_info.model_version.version,
                    "description": training_info.model_version.description,
                    "model_type": training_info.model_type,
                    "last_trained_at": training_info.last_trained_at.isoformat() if training_info.last_trained_at else None,
                    "training_status": training_info.training_status
                }
            elif device.model_version:  # 回退到设备表中的model_version字段
                device_data["model_version_info"] = {
                    "id": device.model_version.id,
                    "version": device.model_version.version,
                    "description": device.model_version.description
                }

            device_list.append(device_data)

        return {
            "devices": device_list,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0
        }

    except Exception as e:
        logger.error(f"获取设备列表失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"获取设备列表失败: {str(e)}"
        )


@router.get("/{device_id}", response_model=Dict[str, Any])
def read_device(device_id: int, db: Session = Depends(get_db)):
    """获取单个设备详情"""
    logger.info(f"请求设备详情: device_id={device_id}")

    db_device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if db_device is None:
        raise HTTPException(status_code=404, detail="设备未找到")

    # 格式化响应
    device_data = {
        "id": db_device.id,
        "uuid": str(db_device.uuid),
        "name": db_device.name,
        "identifier": db_device.identifier,
        "description": db_device.description,
        "status": db_device.status,
        "location": db_device.location,
        "project_id": db_device.project_id,
        "device_metadata": db_device.device_metadata or {},
        "created_at": db_device.created_at.isoformat() if db_device.created_at else None,
        "updated_at": db_device.updated_at.isoformat() if db_device.updated_at else None,
    }

    # 添加项目信息（如果有关联）
    if db_device.project:
        device_data["project"] = {
            "id": db_device.project.id,
            "name": db_device.project.name,
            "code": db_device.project.code
        }

    # 添加设备模型和版本信息（从设备模型训练表获取准确信息）
    training_info = db.query(models.DeviceModelTraining).filter(
        models.DeviceModelTraining.device_id == device_id
    ).first()

    if training_info and training_info.model_version:
        device_data["model_version_info"] = {
            "id": training_info.model_version.id,
            "version": training_info.model_version.version,
            "description": training_info.model_version.description,
            "model_type": training_info.model_type,
            "last_trained_at": training_info.last_trained_at.isoformat() if training_info.last_trained_at else None,
            "training_status": training_info.training_status
        }
    elif db_device.model_version:  # 回退到设备表中的model_version字段
        device_data["model_version_info"] = {
            "id": db_device.model_version.id,
            "version": db_device.model_version.version,
            "description": db_device.model_version.description
        }

    return device_data


@router.get("/uuid/{device_uuid}", response_model=Dict[str, Any])
def read_device_by_uuid(device_uuid: str, db: Session = Depends(get_db)):
    """通过UUID获取设备"""
    logger.info(f"通过UUID请求设备: device_uuid={device_uuid}")

    try:
        import uuid
        device_uuid_obj = uuid.UUID(device_uuid)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的UUID格式")

    db_device = db.query(models.Device).filter(models.Device.uuid == str(device_uuid_obj)).first()
    if db_device is None:
        raise HTTPException(status_code=404, detail="设备未找到")

    # 格式化响应
    device_data = {
        "id": db_device.id,
        "uuid": str(db_device.uuid),
        "name": db_device.name,
        "identifier": db_device.identifier,
        "description": db_device.description,
        "status": db_device.status,
        "location": db_device.location,
        "project_id": db_device.project_id,
        "device_metadata": db_device.device_metadata or {},
        "created_at": db_device.created_at.isoformat() if db_device.created_at else None,
        "updated_at": db_device.updated_at.isoformat() if db_device.updated_at else None,
    }

    # 添加设备模型和版本信息（从设备模型训练表获取准确信息）
    training_info = db.query(models.DeviceModelTraining).filter(
        models.DeviceModelTraining.device_id == db_device.id
    ).first()

    if training_info and training_info.model_version:
        device_data["model_version_info"] = {
            "id": training_info.model_version.id,
            "version": training_info.model_version.version,
            "description": training_info.model_version.description,
            "model_type": training_info.model_type,
            "last_trained_at": training_info.last_trained_at.isoformat() if training_info.last_trained_at else None,
            "training_status": training_info.training_status
        }
    elif db_device.model_version:  # 回退到设备表中的model_version字段
        device_data["model_version_info"] = {
            "id": db_device.model_version.id,
            "version": db_device.model_version.version,
            "description": db_device.model_version.description
        }

    return device_data


@router.post("/", response_model=Dict[str, Any], status_code=201)
def create_device(device_data: Dict[str, Any], db: Session = Depends(get_db)):
    """创建设备"""
    logger.info(f"创建设备: {device_data}")

    try:
        # 获取项目ID
        project_id = device_data.get("project_id")
        if not project_id:
            # 如果没有指定项目，使用第一个项目或返回错误
            first_project = db.query(models.Project).first()
            if not first_project:
                raise HTTPException(status_code=400, detail="没有可用的项目，请先创建项目")
            project_id = first_project.id

        # 检查项目是否存在
        project = db.query(models.Project).filter(models.Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=400, detail=f"项目ID {project_id} 不存在")

        # 检查设备标识符在项目内是否唯一
        existing = db.query(models.Device).filter(
            models.Device.project_id == project_id,
            models.Device.identifier == device_data.get("identifier")
        ).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"设备标识符 '{device_data.get('identifier')}' 在项目内已存在"
            )

        # 获取模型版本ID
        model_version_id = device_data.get("model_version_id")
        model_type = device_data.get("model_type", "xgboost")

        # 创建设备 - 关键修改：直接设置 model_version_id
        db_device = models.Device(
            project_id=project_id,
            name=device_data.get("name"),
            identifier=device_data.get("identifier"),
            description=device_data.get("description"),
            status=device_data.get("status", "active"),
            location=device_data.get("location"),
            device_metadata=device_data.get("device_metadata", {}),
            model_version_id=model_version_id  # 新增：直接设置模型版本ID
        )

        db.add(db_device)

        # 提交以获得设备ID
        db.commit()
        db.refresh(db_device)

        # 如果提供了模型版本信息，创建设备模型训练记录
        if model_version_id:
            # 检查模型版本是否存在
            model_version = db.query(models.DeviceModelVersion).filter(
                models.DeviceModelVersion.id == model_version_id
            ).first()

            if model_version:
                # 创建设备模型训练记录
                training_record = models.DeviceModelTraining(
                    device_id=db_device.id,
                    model_version_id=model_version_id,
                    model_type=model_type
                )
                db.add(training_record)
                db.commit()  # 提交训练记录

        # 更新项目的设备计数
        project.device_count = db.query(func.count(models.Device.id)).filter(
            models.Device.project_id == project_id
        ).scalar()

        db.commit()
        db.refresh(db_device)

        # 格式化响应
        response_data = {
            "id": db_device.id,
            "uuid": str(db_device.uuid),
            "name": db_device.name,
            "identifier": db_device.identifier,
            "description": db_device.description,
            "status": db_device.status,
            "location": db_device.location,
            "project_id": db_device.project_id,
            "device_metadata": db_device.device_metadata or {},
            "created_at": db_device.created_at.isoformat() if db_device.created_at else None,
            "updated_at": db_device.updated_at.isoformat() if db_device.updated_at else None,
        }

        # 添加项目信息（如果有关联）
        if db_device.project:
            response_data["project"] = {
                "id": db_device.project.id,
                "name": db_device.project.name,
                "code": db_device.project.code
            }

        # 添加模型版本信息
        if model_version_id and db_device.model_version:
            response_data["model_version_info"] = {
                "id": db_device.model_version.id,
                "version": db_device.model_version.version,
                "description": db_device.model_version.description
            }
        else:
            # 从设备模型训练表获取
            training_info = db.query(models.DeviceModelTraining).filter(
                models.DeviceModelTraining.device_id == db_device.id
            ).first()

            if training_info and training_info.model_version:
                response_data["model_version_info"] = {
                    "id": training_info.model_version.id,
                    "version": training_info.model_version.version,
                    "description": training_info.model_version.description,
                    "model_type": training_info.model_type,
                    "last_trained_at": training_info.last_trained_at.isoformat() if training_info.last_trained_at else None,
                    "training_status": training_info.training_status
                }

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建设备失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建设备失败: {str(e)}")


@router.put("/{device_id}", response_model=Dict[str, Any])
def update_device(
        device_id: int,
        device_update: Dict[str, Any],
        db: Session = Depends(get_db)
):
    """更新设备"""
    logger.info(f"更新设备 {device_id}: {device_update}")

    try:
        db_device = db.query(models.Device).filter(models.Device.id == device_id).first()
        if not db_device:
            raise HTTPException(status_code=404, detail="设备未找到")

        update_data = {k: v for k, v in device_update.items() if v is not None}

        # 添加调试日志
        logger.info(f"更新设备 {device_id} 的字段: {list(update_data.keys())}")

        # 特别处理 model_version_id
        if "model_version_id" in update_data:
            model_version_id = update_data.get("model_version_id")
            logger.info(f"更新设备 {device_id} 的 model_version_id 为: {model_version_id}")

            # 验证模型版本是否存在
            if model_version_id is not None:
                model_version = db.query(models.DeviceModelVersion).filter(
                    models.DeviceModelVersion.id == model_version_id
                ).first()
                if not model_version:
                    raise HTTPException(
                        status_code=400,
                        detail=f"模型版本ID {model_version_id} 不存在"
                    )

        # 如果更新了设备标识符，检查是否重复
        if "identifier" in update_data and update_data["identifier"] != db_device.identifier:
            existing = db.query(models.Device).filter(
                models.Device.project_id == db_device.project_id,
                models.Device.identifier == update_data["identifier"]
            ).first()

            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"设备标识符 '{update_data['identifier']}' 在项目内已存在"
                )

        # 更新字段
        for field, value in update_data.items():
            if hasattr(db_device, field):
                setattr(db_device, field, value)

        # 如果提供了模型版本信息，更新设备模型训练记录
        model_version_id = update_data.get("model_version_id")
        if model_version_id is not None:  # 包括None的情况也要处理
            # 查找现有的训练记录
            training_record = db.query(models.DeviceModelTraining).filter(
                models.DeviceModelTraining.device_id == device_id
            ).first()

            if training_record:
                # 更新现有记录
                training_record.model_version_id = model_version_id
                if "model_type" in update_data:
                    training_record.model_type = update_data["model_type"]
            else:
                # 创建新的训练记录
                new_training_record = models.DeviceModelTraining(
                    device_id=device_id,
                    model_version_id=model_version_id,
                    model_type=update_data.get("model_type", "xgboost")
                )
                db.add(new_training_record)

        db.commit()
        db.refresh(db_device)

        # 格式化响应
        response_data = {
            "id": db_device.id,
            "uuid": str(db_device.uuid),
            "name": db_device.name,
            "identifier": db_device.identifier,
            "description": db_device.description,
            "status": db_device.status,
            "location": db_device.location,
            "project_id": db_device.project_id,
            "device_metadata": db_device.device_metadata or {},
            "created_at": db_device.created_at.isoformat() if db_device.created_at else None,
            "updated_at": db_device.updated_at.isoformat() if db_device.updated_at else None,
        }

        # 添加项目信息（如果有关联）
        if db_device.project:
            response_data["project"] = {
                "id": db_device.project.id,
                "name": db_device.project.name,
                "code": db_device.project.code
            }

        # 添加模型版本信息
        training_info = db.query(models.DeviceModelTraining).filter(
            models.DeviceModelTraining.device_id == device_id
        ).first()

        if training_info and training_info.model_version:
            response_data["model_version_info"] = {
                "id": training_info.model_version.id,
                "version": training_info.model_version.version,
                "description": training_info.model_version.description,
                "model_type": training_info.model_type,
                "last_trained_at": training_info.last_trained_at.isoformat() if training_info.last_trained_at else None,
                "training_status": training_info.training_status
            }

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新设备失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新设备失败: {str(e)}")


@router.delete("/{device_id}", status_code=204)
def delete_device(device_id: int, db: Session = Depends(get_db)):
    """删除设备"""
    logger.info(f"删除设备: device_id={device_id}")

    try:
        db_device = db.query(models.Device).filter(models.Device.id == device_id).first()
        if not db_device:
            raise HTTPException(status_code=404, detail="设备未找到")

        project_id = db_device.project_id

        # 删除相关的设备模型训练记录
        training_record = db.query(models.DeviceModelTraining).filter(
            models.DeviceModelTraining.device_id == device_id
        ).first()

        if training_record:
            db.delete(training_record)

        db.delete(db_device)

        # 更新项目的设备计数
        project = db.query(models.Project).filter(models.Project.id == project_id).first()
        if project:
            project.device_count = db.query(func.count(models.Device.id)).filter(
                models.Device.project_id == project_id
            ).scalar()

        db.commit()
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除设备失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除设备失败: {str(e)}")


# ==================== 项目相关设备端点 ====================

@router.get("/projects/{project_id}/devices", response_model=Dict[str, Any])
def read_project_devices(
        project_id: int,
        db: Session = Depends(get_db),
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(10, ge=1, le=100, description="每页数量")
):
    """获取项目的设备列表"""
    logger.info(f"请求项目 {project_id} 的设备列表")

    try:
        # 检查项目是否存在
        project = db.query(models.Project).filter(models.Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=400, detail=f"项目ID {project_id} 不存在")

        skip = (page - 1) * page_size
        query = db.query(models.Device).filter(models.Device.project_id == project_id)

        # 计算总数
        total = query.count()

        # 获取设备数据
        devices = query.order_by(models.Device.updated_at.desc()).offset(skip).limit(page_size).all()

        # 格式化设备数据
        device_list = []
        for device in devices:
            device_data = {
                "id": device.id,
                "uuid": str(device.uuid),
                "name": device.name,
                "identifier": device.identifier,
                "description": device.description,
                "status": device.status,
                "location": device.location,
                "project_id": device.project_id,
                "device_metadata": device.device_metadata or {},
                "created_at": device.created_at.isoformat() if device.created_at else None,
                "updated_at": device.updated_at.isoformat() if device.updated_at else None,
            }

            # 添加设备模型和版本信息（从设备模型训练表获取准确信息）
            training_info = db.query(models.DeviceModelTraining).filter(
                models.DeviceModelTraining.device_id == device.id
            ).first()

            if training_info and training_info.model_version:
                device_data["model_version_info"] = {
                    "id": training_info.model_version.id,
                    "version": training_info.model_version.version,
                    "description": training_info.model_version.description,
                    "model_type": training_info.model_type,
                    "last_trained_at": training_info.last_trained_at.isoformat() if training_info.last_trained_at else None,
                    "training_status": training_info.training_status
                }
            elif device.model_version:  # 回退到设备表中的model_version字段
                device_data["model_version_info"] = {
                    "id": device.model_version.id,
                    "version": device.model_version.version,
                    "description": device.model_version.description
                }

            device_list.append(device_data)

        return {
            "devices": device_list,
            "total": total,
            "project_id": project_id,
            "project_name": project.name
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目设备列表失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取项目设备列表失败: {str(e)}")


@router.post("/projects/{project_id}/devices", response_model=Dict[str, Any], status_code=201)
def create_project_device(
        project_id: int,
        device_data: Dict[str, Any],
        db: Session = Depends(get_db)
):
    """为项目创建设备"""
    logger.info(f"为项目 {project_id} 创建设备: {device_data}")

    try:
        # 检查项目是否存在
        project = db.query(models.Project).filter(models.Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=400, detail=f"项目ID {project_id} 不存在")

        # 检查设备标识符在项目内是否唯一
        existing = db.query(models.Device).filter(
            models.Device.project_id == project_id,
            models.Device.identifier == device_data.get("identifier")
        ).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"设备标识符 '{device_data.get('identifier')}' 在项目内已存在"
            )

        # 获取模型版本ID
        model_version_id = device_data.get("model_version_id")
        model_type = device_data.get("model_type", "xgboost")

        # 创建设备 - 关键修改：直接设置 model_version_id
        db_device = models.Device(
            project_id=project_id,
            name=device_data.get("name"),
            identifier=device_data.get("identifier"),
            description=device_data.get("description"),
            status=device_data.get("status", "active"),
            location=device_data.get("location"),
            device_metadata=device_data.get("device_metadata", {}),
            model_version_id=model_version_id  # 新增：直接设置模型版本ID
        )

        db.add(db_device)

        # 提交以获得设备ID
        db.commit()
        db.refresh(db_device)

        # 如果提供了模型版本信息，创建设备模型训练记录
        if model_version_id:
            # 检查模型版本是否存在
            model_version = db.query(models.DeviceModelVersion).filter(
                models.DeviceModelVersion.id == model_version_id
            ).first()

            if model_version:
                # 创建设备模型训练记录
                training_record = models.DeviceModelTraining(
                    device_id=db_device.id,
                    model_version_id=model_version_id,
                    model_type=model_type
                )
                db.add(training_record)
                db.commit()  # 提交训练记录

        # 更新项目的设备计数
        project.device_count = db.query(func.count(models.Device.id)).filter(
            models.Device.project_id == project_id
        ).scalar()

        db.commit()
        db.refresh(db_device)

        # 格式化响应
        response_data = {
            "id": db_device.id,
            "uuid": str(db_device.uuid),
            "name": db_device.name,
            "identifier": db_device.identifier,
            "description": db_device.description,
            "status": db_device.status,
            "location": db_device.location,
            "project_id": db_device.project_id,
            "device_metadata": db_device.device_metadata or {},
            "created_at": db_device.created_at.isoformat() if db_device.created_at else None,
            "updated_at": db_device.updated_at.isoformat() if db_device.updated_at else None,
        }

        # 添加项目信息（如果有关联）
        if db_device.project:
            response_data["project"] = {
                "id": db_device.project.id,
                "name": db_device.project.name,
                "code": db_device.project.code
            }

        # 添加模型版本信息
        if model_version_id and db_device.model_version:
            response_data["model_version_info"] = {
                "id": db_device.model_version.id,
                "version": db_device.model_version.version,
                "description": db_device.model_version.description
            }
        else:
            # 从设备模型训练表获取
            training_info = db.query(models.DeviceModelTraining).filter(
                models.DeviceModelTraining.device_id == db_device.id
            ).first()

            if training_info and training_info.model_version:
                response_data["model_version_info"] = {
                    "id": training_info.model_version.id,
                    "version": training_info.model_version.version,
                    "description": training_info.model_version.description,
                    "model_type": training_info.model_type,
                    "last_trained_at": training_info.last_trained_at.isoformat() if training_info.last_trained_at else None,
                    "training_status": training_info.training_status
                }

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建设备失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建设备失败: {str(e)}")


# ==================== 设备统计端点 ====================

@router.get("/stats/summary")
def get_device_stats(db: Session = Depends(get_db)):
    """获取设备统计摘要"""
    logger.info("请求设备统计")

    try:
        total_devices = db.query(func.count(models.Device.id)).scalar() or 0
        active_devices = db.query(func.count(models.Device.id)).filter(
            models.Device.status == "active"
        ).scalar() or 0
        inactive_devices = total_devices - active_devices

        # 按项目统计
        project_stats = db.query(
            models.Project.name,
            func.count(models.Device.id).label('device_count')
        ).join(
            models.Device, models.Project.id == models.Device.project_id, isouter=True
        ).group_by(
            models.Project.id
        ).all()

        return {
            "total_devices": total_devices,
            "active_devices": active_devices,
            "inactive_devices": inactive_devices,
            "project_stats": [
                {"project_name": stat[0], "device_count": stat[1]}
                for stat in project_stats
            ]
        }
    except Exception as e:
        logger.error(f"获取设备统计失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取设备统计失败: {str(e)}")


# ==================== 测试端点 ====================

@router.get("/test/ping")
def device_ping():
    """设备API连通性测试"""
    from datetime import datetime
    return {
        "message": "设备API工作正常",
        "timestamp": datetime.now().isoformat()
    }