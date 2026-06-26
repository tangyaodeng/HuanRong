from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Dict, Any, Optional
from ..dependencies.database import get_db
from .. import models
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/device_models", tags=["device_models"])


@router.get("/", response_model=List[Dict[str, Any]])
def get_device_models(
        db: Session = Depends(get_db),
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        search: Optional[str] = None
):
    """获取设备模型列表"""
    try:
        query = db.query(models.DeviceModel)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    models.DeviceModel.name.ilike(search_term),
                    models.DeviceModel.code.ilike(search_term),
                    models.DeviceModel.description.ilike(search_term)
                )
            )

        device_models = query.order_by(models.DeviceModel.name).offset(skip).limit(limit).all()

        return [
            {
                "id": model.id,
                "name": model.name,
                "code": model.code,
                "description": model.description,
                "is_active": getattr(model, 'is_active', True),
                "created_at": model.created_at.isoformat() if model.created_at else None,
                "updated_at": model.updated_at.isoformat() if model.updated_at else None
            }
            for model in device_models
        ]
    except Exception as e:
        logger.error(f"获取设备模型列表失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取设备模型列表失败: {str(e)}")


@router.post("/", response_model=Dict[str, Any])
def create_device_model(
        model_data: dict,
        db: Session = Depends(get_db)
):
    """创建设备模型"""
    try:
        # 检查code是否已存在
        existing_model = db.query(models.DeviceModel) \
            .filter(models.DeviceModel.code == model_data.get('code')) \
            .first()

        if existing_model:
            raise HTTPException(status_code=400, detail="设备模型代码已存在")

        # 创建设备模型
        new_model = models.DeviceModel(
            name=model_data.get('name'),
            code=model_data.get('code'),
            description=model_data.get('description', ''),
            is_active=model_data.get('is_active', True)
        )

        db.add(new_model)
        db.commit()
        db.refresh(new_model)

        return {
            "id": new_model.id,
            "name": new_model.name,
            "code": new_model.code,
            "description": new_model.description,
            "is_active": new_model.is_active,
            "created_at": new_model.created_at.isoformat() if new_model.created_at else None,
            "updated_at": new_model.updated_at.isoformat() if new_model.updated_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建设备模型失败: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建设备模型失败: {str(e)}")


@router.get("/{model_id}", response_model=Dict[str, Any])
def get_device_model(model_id: int, db: Session = Depends(get_db)):
    """获取单个设备模型详情"""
    try:
        model = db.query(models.DeviceModel) \
            .filter(models.DeviceModel.id == model_id) \
            .first()

        if not model:
            raise HTTPException(status_code=404, detail="设备模型未找到")

        return {
            "id": model.id,
            "name": model.name,
            "code": model.code,
            "description": model.description,
            "is_active": getattr(model, 'is_active', True),
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取设备模型失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取设备模型失败: {str(e)}")


@router.put("/{model_id}", response_model=Dict[str, Any])
def update_device_model(
        model_id: int,
        model_data: dict,
        db: Session = Depends(get_db)
):
    """更新设备模型"""
    try:
        model = db.query(models.DeviceModel) \
            .filter(models.DeviceModel.id == model_id) \
            .first()

        if not model:
            raise HTTPException(status_code=404, detail="设备模型未找到")

        # 如果修改了code，检查是否与其他模型冲突
        new_code = model_data.get('code')
        if new_code and new_code != model.code:
            existing_model = db.query(models.DeviceModel) \
                .filter(models.DeviceModel.code == new_code, models.DeviceModel.id != model_id) \
                .first()

            if existing_model:
                raise HTTPException(status_code=400, detail="设备模型代码已存在")

        # 更新字段
        for key, value in model_data.items():
            if hasattr(model, key) and key not in ['id', 'created_at', 'updated_at']:
                setattr(model, key, value)

        db.commit()
        db.refresh(model)

        return {
            "id": model.id,
            "name": model.name,
            "code": model.code,
            "description": model.description,
            "is_active": model.is_active,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新设备模型失败: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新设备模型失败: {str(e)}")


@router.delete("/{model_id}")
def delete_device_model(
        model_id: int,
        db: Session = Depends(get_db)
):
    """删除设备模型"""
    try:
        model = db.query(models.DeviceModel) \
            .filter(models.DeviceModel.id == model_id) \
            .first()

        if not model:
            raise HTTPException(status_code=404, detail="设备模型未找到")

        # 检查是否有版本关联
        version_count = db.query(models.DeviceModelVersion) \
            .filter(models.DeviceModelVersion.model_id == model_id) \
            .count()

        if version_count > 0:
            raise HTTPException(status_code=400, detail="存在关联的模型版本，请先删除相关版本")

        db.delete(model)
        db.commit()

        return {"message": "设备模型删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除设备模型失败: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除设备模型失败: {str(e)}")


@router.patch("/{model_id}/status")
def toggle_device_model_status(
        model_id: int,
        is_active: bool = Query(..., description="是否激活"),
        db: Session = Depends(get_db)
):
    """切换设备模型状态"""
    try:
        model = db.query(models.DeviceModel) \
            .filter(models.DeviceModel.id == model_id) \
            .first()

        if not model:
            raise HTTPException(status_code=404, detail="设备模型未找到")

        model.is_active = is_active
        db.commit()
        db.refresh(model)

        return {
            "id": model.id,
            "name": model.name,
            "is_active": model.is_active,
            "message": f"设备模型已{'启用' if is_active else '禁用'}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"切换设备模型状态失败: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"切换设备模型状态失败: {str(e)}")


@router.get("/versions/", response_model=List[Dict[str, Any]])
def get_all_model_versions(
        db: Session = Depends(get_db),
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        model_id: Optional[int] = Query(None, description="按设备模型ID筛选"),
        is_active: Optional[bool] = Query(None, description="按激活状态筛选"),
        search: Optional[str] = Query(None, description="搜索版本号或描述")
):
    """获取所有模型版本列表（可筛选）"""
    try:
        query = db.query(models.DeviceModelVersion)

        # 应用筛选条件
        if model_id is not None:
            query = query.filter(models.DeviceModelVersion.model_id == model_id)

        if is_active is not None:
            query = query.filter(models.DeviceModelVersion.is_active == is_active)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    models.DeviceModelVersion.version.ilike(search_term),
                    models.DeviceModelVersion.description.ilike(search_term)
                )
            )

        versions = query.order_by(models.DeviceModelVersion.created_at.desc()) \
            .offset(skip) \
            .limit(limit) \
            .all()

        # 获取对应的设备模型名称
        result = []
        for version in versions:
            model = db.query(models.DeviceModel) \
                .filter(models.DeviceModel.id == version.model_id) \
                .first()

            result.append({
                "id": version.id,
                "model_id": version.model_id,
                "model_name": model.name if model else "未知模型",
                "model_code": model.code if model else "",
                "version": version.version,
                "description": version.description,
                "is_active": version.is_active,
                "created_at": version.created_at.isoformat() if version.created_at else None,
                "updated_at": version.updated_at.isoformat() if version.updated_at else None
            })

        return result
    except Exception as e:
        logger.error(f"获取模型版本列表失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取模型版本列表失败: {str(e)}")


@router.post("/versions/", response_model=Dict[str, Any])
def create_model_version(
        version_data: dict,
        db: Session = Depends(get_db)
):
    """创建设备模型版本"""
    try:
        # 检查模型是否存在
        model = db.query(models.DeviceModel) \
            .filter(models.DeviceModel.id == version_data.get('model_id')) \
            .first()

        if not model:
            raise HTTPException(status_code=404, detail="设备模型未找到")

        # 检查版本号是否已存在（同一模型下）
        existing_version = db.query(models.DeviceModelVersion) \
            .filter(
            models.DeviceModelVersion.model_id == version_data.get('model_id'),
            models.DeviceModelVersion.version == version_data.get('version')
        ) \
            .first()

        if existing_version:
            raise HTTPException(status_code=400, detail="该模型下版本号已存在")

        # 创建模型版本
        new_version = models.DeviceModelVersion(
            model_id=version_data.get('model_id'),
            version=version_data.get('version'),
            description=version_data.get('description', ''),
            is_active=version_data.get('is_active', True)
        )

        db.add(new_version)
        db.commit()
        db.refresh(new_version)

        return {
            "id": new_version.id,
            "model_id": new_version.model_id,
            "version": new_version.version,
            "description": new_version.description,
            "is_active": new_version.is_active,
            "created_at": new_version.created_at.isoformat() if new_version.created_at else None,
            "updated_at": new_version.updated_at.isoformat() if new_version.updated_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建设备模型版本失败: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建设备模型版本失败: {str(e)}")


@router.get("/versions/{version_id}", response_model=Dict[str, Any])
def get_model_version(version_id: int, db: Session = Depends(get_db)):
    """获取单个模型版本"""
    try:
        version = db.query(models.DeviceModelVersion) \
            .filter(models.DeviceModelVersion.id == version_id) \
            .first()

        if not version:
            raise HTTPException(status_code=404, detail="模型版本未找到")

        # 获取关联的设备模型信息
        model = db.query(models.DeviceModel) \
            .filter(models.DeviceModel.id == version.model_id) \
            .first()

        return {
            "id": version.id,
            "model_id": version.model_id,
            "model_name": model.name if model else "未知模型",
            "model_code": model.code if model else "",
            "version": version.version,
            "description": version.description,
            "is_active": version.is_active,
            "created_at": version.created_at.isoformat() if version.created_at else None,
            "updated_at": version.updated_at.isoformat() if version.updated_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取模型版本失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取模型版本失败: {str(e)}")


@router.put("/versions/{version_id}", response_model=Dict[str, Any])
def update_model_version(
        version_id: int,
        version_data: dict,
        db: Session = Depends(get_db)
):
    """更新模型版本"""
    try:
        version = db.query(models.DeviceModelVersion) \
            .filter(models.DeviceModelVersion.id == version_id) \
            .first()

        if not version:
            raise HTTPException(status_code=404, detail="模型版本未找到")

        # 如果修改了版本号，检查是否与其他版本冲突
        new_version = version_data.get('version')
        if new_version and new_version != version.version:
            existing_version = db.query(models.DeviceModelVersion) \
                .filter(
                models.DeviceModelVersion.model_id == version.model_id,
                models.DeviceModelVersion.version == new_version,
                models.DeviceModelVersion.id != version_id
            ) \
                .first()

            if existing_version:
                raise HTTPException(status_code=400, detail="该模型下版本号已存在")

        # 更新字段
        for key, value in version_data.items():
            if hasattr(version, key) and key not in ['id', 'model_id', 'created_at', 'updated_at']:
                setattr(version, key, value)

        db.commit()
        db.refresh(version)

        return {
            "id": version.id,
            "model_id": version.model_id,
            "version": version.version,
            "description": version.description,
            "is_active": version.is_active,
            "created_at": version.created_at.isoformat() if version.created_at else None,
            "updated_at": version.updated_at.isoformat() if version.updated_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新模型版本失败: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新模型版本失败: {str(e)}")


@router.delete("/versions/{version_id}")
def delete_model_version(
        version_id: int,
        db: Session = Depends(get_db)
):
    """删除模型版本"""
    try:
        version = db.query(models.DeviceModelVersion) \
            .filter(models.DeviceModelVersion.id == version_id) \
            .first()

        if not version:
            raise HTTPException(status_code=404, detail="模型版本未找到")

        db.delete(version)
        db.commit()

        return {"message": "模型版本删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除模型版本失败: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除模型版本失败: {str(e)}")


@router.patch("/versions/{version_id}/status")
def toggle_model_version_status(
        version_id: int,
        is_active: bool = Query(..., description="是否激活"),
        db: Session = Depends(get_db)
):
    """切换模型版本状态"""
    try:
        version = db.query(models.DeviceModelVersion) \
            .filter(models.DeviceModelVersion.id == version_id) \
            .first()

        if not version:
            raise HTTPException(status_code=404, detail="模型版本未找到")

        version.is_active = is_active
        db.commit()
        db.refresh(version)

        return {
            "id": version.id,
            "version": version.version,
            "is_active": version.is_active,
            "message": f"模型版本已{'启用' if is_active else '禁用'}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"切换模型版本状态失败: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"切换模型版本状态失败: {str(e)}")


@router.get("/{model_id}/versions", response_model=List[Dict[str, Any]])
def get_device_model_versions(
        model_id: int,
        db: Session = Depends(get_db),
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000)
):
    """获取设备模型版本列表"""
    try:
        # 检查模型是否存在
        model = db.query(models.DeviceModel) \
            .filter(models.DeviceModel.id == model_id) \
            .first()

        if not model:
            raise HTTPException(status_code=404, detail="设备模型未找到")

        versions = db.query(models.DeviceModelVersion) \
            .filter(models.DeviceModelVersion.model_id == model_id) \
            .order_by(models.DeviceModelVersion.created_at.desc()) \
            .offset(skip) \
            .limit(limit) \
            .all()

        return [
            {
                "id": version.id,
                "model_id": version.model_id,
                "version": version.version,
                "description": version.description,
                "is_active": version.is_active,
                "created_at": version.created_at.isoformat() if version.created_at else None,
                "updated_at": version.updated_at.isoformat() if version.updated_at else None
            }
            for version in versions
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取设备模型版本失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取设备模型版本失败: {str(e)}")