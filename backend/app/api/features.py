#app/api/features.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from ..dependencies.database import get_db
from .. import models
import logging
from .. import schemas  # 确保导入schemas模块

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/features", tags=["features"])


@router.get("/by_version/{version_id}", response_model=List[dict])
def get_features_by_version(
        version_id: int,
        db: Session = Depends(get_db),
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000)
):
    """获取指定设备模型版本关联的特征列表"""
    try:
        # 检查版本是否存在
        version = db.query(models.DeviceModelVersion) \
            .filter(models.DeviceModelVersion.id == version_id) \
            .first()

        if not version:
            raise HTTPException(status_code=404, detail="设备模型版本未找到")

        # 查询该版本关联的特征
        features = db.query(models.Feature) \
            .join(models.ModelVersionFeature, models.Feature.id == models.ModelVersionFeature.feature_id) \
            .filter(models.ModelVersionFeature.version_id == version_id) \
            .order_by(models.ModelVersionFeature.display_order) \
            .offset(skip) \
            .limit(limit) \
            .all()

        result = []
        for feature in features:
            feature_data = {
                "id": feature.id,
                "name": feature.name,
                "code": feature.code,
                "data_type": feature.data_type,
                "unit": feature.unit or "",
                "description": feature.description or "",
                "is_required": feature.is_required,
                "default_value": feature.default_value or "",
                "validation_rules": feature.validation_rules or {},
            # 新增映射字段
            "data_source_id": feature.data_source_id,
            "database_name": feature.database_name,
            "table_name": feature.table_name,
            "column_name": feature.column_name,
            "timestamp_column": feature.timestamp_column
            }
            result.append(feature_data)

        return result
    except Exception as e:
        logger.error(f"获取版本特征失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取特征失败: {str(e)}")


@router.get("/by_device/{device_id}", response_model=List[dict])
def get_device_feature_values(
        device_id: int,
        db: Session = Depends(get_db)
):
    """获取设备特征值"""
    try:
        # 检查设备是否存在
        device = db.query(models.Device) \
            .filter(models.Device.id == device_id) \
            .first()

        if not device:
            raise HTTPException(status_code=404, detail="设备未找到")

        # 查询设备的特征值
        feature_values = db.query(
            models.Feature.id,
            models.Feature.code,
            models.DeviceFeatureValue.value
        ) \
            .join(models.DeviceFeatureValue, models.Feature.id == models.DeviceFeatureValue.feature_id) \
            .filter(models.DeviceFeatureValue.device_id == device_id) \
            .all()

        result = []
        for feature_id, feature_code, value in feature_values:
            result.append({
                "feature_id": feature_id,
                "feature_code": feature_code,
                "value": value or ""
            })

        return result
    except Exception as e:
        logger.error(f"获取设备特征值失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取特征值失败: {str(e)}")


@router.get("/", response_model=List[dict])
def get_features(
        db: Session = Depends(get_db),
        skip: int = Query(0, ge=0),
        limit: int = Query(1000, ge=1, le=1000)
):
    """获取所有特征"""
    try:
        features = db.query(models.Feature) \
            .order_by(models.Feature.id) \
            .offset(skip) \
            .limit(limit) \
            .all()

        result = []
        for feature in features:
            feature_data = {
                "id": feature.id,
                "name": feature.name,
                "code": feature.code,
                "data_type": feature.data_type,
                "unit": feature.unit or "",
                "description": feature.description or "",
                "is_required": feature.is_required,
                "default_value": feature.default_value or "",
                "validation_rules": feature.validation_rules or {},
                "created_at": feature.created_at.isoformat(),
            # 新增映射字段
            "data_source_id": feature.data_source_id,
            "database_name": feature.database_name,
            "table_name": feature.table_name,
            "column_name": feature.column_name,
            "timestamp_column": feature.timestamp_column
            }
            result.append(feature_data)

        return result
    except Exception as e:
        logger.error(f"获取特征列表失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取特征列表失败: {str(e)}")

# 新增：获取模型版本特征详情（包含输出标记）
@router.get("/version/{version_id}/features/detailed", response_model=List[Dict[str, Any]])
def get_version_features_detailed(
    version_id: int,
    db: Session = Depends(get_db)
):
    """获取模型版本的详细特征信息，包含输出和状态标记"""
    try:
        # 查询版本特征关联
        version_features = db.query(models.ModelVersionFeature) \
            .filter(models.ModelVersionFeature.version_id == version_id) \
            .order_by(models.ModelVersionFeature.display_order) \
            .all()

        result = []
        for vf in version_features:
            # 获取特征详情
            feature = db.query(models.Feature) \
                .filter(models.Feature.id == vf.feature_id) \
                .first()

            if feature:
                result.append({
                    "id": vf.id,
                    "feature_id": feature.id,
                    "feature": {
                        "id": feature.id,
                        "name": feature.name,
                        "code": feature.code,
                        "data_type": feature.data_type,
                        "unit": feature.unit or "",
                        "description": feature.description or "",
                        "is_required": feature.is_required,
                        "default_value": feature.default_value or "",
                        "validation_rules": feature.validation_rules or {}
                    },
                    "display_order": vf.display_order,
                    "is_output": vf.is_output,
                    "is_primary_output": vf.is_primary_output,  # 关键修复：添加主输出标记
                    "is_status": vf.is_status,  # 确保返回状态特征标记
                    "created_at": vf.created_at.isoformat() if vf.created_at else None
                })

        return result
    except Exception as e:
        logger.error(f"获取详细特征信息失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取特征信息失败: {str(e)}")
# 修改 update_version_features 函数，支持多个输出特征但只能有一个主输出
@router.put("/update_version_features/{version_id}")
def update_version_features(
        version_id: int,
        features: List[Dict[str, Any]],
        db: Session = Depends(get_db)
):
    """更新模型版本的特征关联"""
    try:
        from ..crud.features import ModelVersionFeatureCRUD

        crud = ModelVersionFeatureCRUD(db)

        # 检查版本是否存在
        version = db.query(models.DeviceModelVersion) \
            .filter(models.DeviceModelVersion.id == version_id) \
            .first()

        if not version:
            raise HTTPException(status_code=404, detail="设备模型版本未找到")

        # 验证特征ID
        feature_ids = [feature["feature_id"] for feature in features]
        existing_features = db.query(models.Feature) \
            .filter(models.Feature.id.in_(feature_ids)) \
            .all()

        if len(existing_features) != len(feature_ids):
            raise HTTPException(status_code=400, detail="存在无效的特征ID")

        # 检查输出特征和主输出特征
        output_features = [f for f in features if f.get("is_output", False)]
        primary_output_features = [f for f in features if f.get("is_primary_output", False)]

        # 检查主输出特征数量（只能有一个）
        if len(primary_output_features) > 1:
            raise HTTPException(status_code=400, detail="只能设置一个主输出特征")

        # 检查主输出特征必须是输出特征
        for feature in features:
            if feature.get("is_primary_output", False) and not feature.get("is_output", False):
                raise HTTPException(status_code=400, detail="主输出特征必须是输出特征")

        # 检查同一个特征不能同时是输出和状态
        for feature in features:
            if feature.get("is_output", False) and feature.get("is_status", False):
                raise HTTPException(status_code=400, detail="同一个特征不能同时设置为输出特征和状态特征")

        # 更新特征关联
        success = crud.update_version_features(version_id, features)

        if not success:
            raise HTTPException(status_code=500, detail="更新特征关联失败")

        return {"success": True, "message": "特征关联更新成功"}

    except Exception as e:
        logger.error(f"更新版本特征失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新特征失败: {str(e)}")

# 新增：获取模型版本特征详情（包含输出标记）
@router.get("/version/{version_id}/features/detailed", response_model=List[Dict[str, Any]])
def get_version_features_detailed(
    version_id: int,
    db: Session = Depends(get_db)
):
    """获取模型版本的详细特征信息，包含输出和状态标记"""
    try:
        # 查询版本特征关联
        version_features = db.query(models.ModelVersionFeature) \
            .filter(models.ModelVersionFeature.version_id == version_id) \
            .order_by(models.ModelVersionFeature.display_order) \
            .all()

        result = []
        for vf in version_features:
            # 获取特征详情
            feature = db.query(models.Feature) \
                .filter(models.Feature.id == vf.feature_id) \
                .first()

            if feature:
                result.append({
                    "id": vf.id,
                    "feature_id": feature.id,
                    "feature": {
                        "id": feature.id,
                        "name": feature.name,
                        "code": feature.code,
                        "data_type": feature.data_type,
                        "unit": feature.unit or "",
                        "description": feature.description or "",
                        "is_required": feature.is_required,
                        "default_value": feature.default_value or "",
                        "validation_rules": feature.validation_rules or {}
                    },
                    "display_order": vf.display_order,
                    "is_output": vf.is_output,
                    "is_status": vf.is_status,  # 确保返回状态特征标记
                    "created_at": vf.created_at.isoformat() if vf.created_at else None
                })

        return result
    except Exception as e:
        logger.error(f"获取详细特征信息失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取特征信息失败: {str(e)}")


@router.post("/", response_model=dict)
def create_feature(
        feature: schemas.FeatureCreate,
        db: Session = Depends(get_db)
):
    """创建新特征"""
    try:
        from ..crud.features import FeatureCRUD

        crud = FeatureCRUD(db)

        # 检查特征代码是否已存在
        existing = crud.get_feature_by_code(feature.code)
        if existing:
            raise HTTPException(status_code=400, detail="特征代码已存在")

        # 创建特征
        db_feature = crud.create_feature(feature)

        return {
            "success": True,
            "id": db_feature.id,
            "message": "特征创建成功"
        }
    except Exception as e:
        logger.error(f"创建特征失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建特征失败: {str(e)}")


@router.put("/{feature_id}", response_model=dict)
def update_feature(
        feature_id: int,
        feature_update: schemas.FeatureUpdate,
        db: Session = Depends(get_db)
):
    """更新特征"""
    try:
        from ..crud.features import FeatureCRUD

        crud = FeatureCRUD(db)

        # 检查特征是否存在
        db_feature = crud.get_feature(feature_id)
        if not db_feature:
            raise HTTPException(status_code=404, detail="特征未找到")

        # 更新特征
        updated_feature = crud.update_feature(feature_id, feature_update)
        if not updated_feature:
            raise HTTPException(status_code=500, detail="特征更新失败")

        return {
            "success": True,
            "message": "特征更新成功"
        }
    except Exception as e:
        logger.error(f"更新特征失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新特征失败: {str(e)}")


@router.delete("/{feature_id}", response_model=dict)
def delete_feature(
        feature_id: int,
        db: Session = Depends(get_db)
):
    """删除特征"""
    try:
        from ..crud.features import FeatureCRUD

        crud = FeatureCRUD(db)

        # 检查特征是否存在
        db_feature = crud.get_feature(feature_id)
        if not db_feature:
            raise HTTPException(status_code=404, detail="特征未找到")

        # 删除特征
        success = crud.delete_feature(feature_id)
        if not success:
            raise HTTPException(status_code=500, detail="特征删除失败")

        return {
            "success": True,
            "message": "特征删除成功"
        }
    except Exception as e:
        logger.error(f"删除特征失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除特征失败: {str(e)}")