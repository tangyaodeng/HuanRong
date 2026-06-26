# crud/features.py
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional, List, Dict, Any
from .. import models, schemas
import uuid


class FeatureCRUD:
    def __init__(self, db: Session):
        self.db = db

    def get_feature(self, feature_id: int) -> Optional[models.Feature]:
        """获取单个特征"""
        return self.db.query(models.Feature).filter(models.Feature.id == feature_id).first()

    def get_feature_by_uuid(self, feature_uuid: uuid.UUID) -> Optional[models.Feature]:
        """通过UUID获取特征"""
        return self.db.query(models.Feature).filter(models.Feature.uuid == feature_uuid).first()

    def get_feature_by_code(self, code: str) -> Optional[models.Feature]:
        """通过代码获取特征"""
        return self.db.query(models.Feature).filter(models.Feature.code == code).first()

    def get_features(
            self,
            skip: int = 0,
            limit: int = 100,
            data_type: Optional[str] = None,
            is_required: Optional[bool] = None,
            search: Optional[str] = None
    ) -> List[models.Feature]:
        """获取特征列表"""
        query = self.db.query(models.Feature)

        # 应用筛选条件
        if data_type:
            query = query.filter(models.Feature.data_type == data_type)

        if is_required is not None:
            query = query.filter(models.Feature.is_required == is_required)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    models.Feature.name.ilike(search_term),
                    models.Feature.code.ilike(search_term),
                    models.Feature.description.ilike(search_term)
                )
            )

        return query.order_by(models.Feature.id).offset(skip).limit(limit).all()

    def get_features_by_ids(self, feature_ids: List[int]) -> List[models.Feature]:
        """通过ID列表获取特征"""
        if not feature_ids:
            return []
        return self.db.query(models.Feature).filter(models.Feature.id.in_(feature_ids)).all()

    def count_features(
            self,
            data_type: Optional[str] = None,
            is_required: Optional[bool] = None,
            search: Optional[str] = None
    ) -> int:
        """统计特征数量"""
        query = self.db.query(func.count(models.Feature.id))

        # 应用筛选条件
        if data_type:
            query = query.filter(models.Feature.data_type == data_type)

        if is_required is not None:
            query = query.filter(models.Feature.is_required == is_required)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    models.Feature.name.ilike(search_term),
                    models.Feature.code.ilike(search_term),
                    models.Feature.description.ilike(search_term)
                )
            )

        return query.scalar()

    def create_feature(self, feature: schemas.FeatureCreate) -> models.Feature:
        """创建特征（包含映射字段）"""
        db_feature = models.Feature(
            uuid=uuid.uuid4(),
            name=feature.name,
            code=feature.code,
            data_type=feature.data_type,
            unit=feature.unit,
            description=feature.description,
            is_required=feature.is_required,
            default_value=feature.default_value,
            validation_rules=feature.validation_rules or {},
            # 新增映射字段
            data_source_id=feature.data_source_id,
            database_name=feature.database_name,
            table_name=feature.table_name,
            column_name=feature.column_name or 'PointValue',  # 使用传入值或默认值
            timestamp_column=feature.timestamp_column or 'UpdateDateTime'
        )
        self.db.add(db_feature)
        self.db.commit()
        self.db.refresh(db_feature)
        return db_feature

    def update_feature(self, feature_id: int, feature_update: schemas.FeatureUpdate) -> Optional[models.Feature]:
        """更新特征"""
        db_feature = self.get_feature(feature_id)
        if not db_feature:
            return None

        update_data = feature_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_feature, field, value)

        self.db.commit()
        self.db.refresh(db_feature)
        return db_feature

    def delete_feature(self, feature_id: int) -> bool:
        """删除特征"""
        db_feature = self.get_feature(feature_id)
        if not db_feature:
            return False

        self.db.delete(db_feature)
        self.db.commit()
        return True

    def search_features(self, keyword: str, limit: int = 20) -> List[models.Feature]:
        """搜索特征"""
        search_term = f"%{keyword}%"
        return self.db.query(models.Feature).filter(
            or_(
                models.Feature.name.ilike(search_term),
                models.Feature.code.ilike(search_term)
            )
        ).limit(limit).all()


class ModelVersionFeatureCRUD:
    def __init__(self, db: Session):
        self.db = db

    def get_version_features(self, version_id: int) -> List[models.ModelVersionFeature]:
        """获取模型版本的特征列表"""
        return self.db.query(models.ModelVersionFeature) \
            .filter(models.ModelVersionFeature.version_id == version_id) \
            .order_by(models.ModelVersionFeature.display_order) \
            .all()

    def get_version_feature_ids(self, version_id: int) -> List[int]:
        """获取模型版本的特征ID列表"""
        features = self.get_version_features(version_id)
        return [f.feature_id for f in features]

    def add_feature_to_version(self, version_id: int, feature_id: int, display_order: int = 0) -> Optional[
        models.ModelVersionFeature]:
        """添加特征到模型版本"""
        # 检查是否已存在
        existing = self.db.query(models.ModelVersionFeature).filter(
            models.ModelVersionFeature.version_id == version_id,
            models.ModelVersionFeature.feature_id == feature_id
        ).first()

        if existing:
            return existing

        db_version_feature = models.ModelVersionFeature(
            version_id=version_id,
            feature_id=feature_id,
            display_order=display_order
        )
        self.db.add(db_version_feature)
        self.db.commit()
        self.db.refresh(db_version_feature)
        return db_version_feature

    def remove_feature_from_version(self, version_id: int, feature_id: int) -> bool:
        """从模型版本移除特征"""
        db_version_feature = self.db.query(models.ModelVersionFeature).filter(
            models.ModelVersionFeature.version_id == version_id,
            models.ModelVersionFeature.feature_id == feature_id
        ).first()

        if not db_version_feature:
            return False

        self.db.delete(db_version_feature)
        self.db.commit()
        return True

    # 修改 update_version_features 方法，支持输出特征和主输出特征
    def update_version_features(self, version_id: int, features: List[Dict[str, Any]]) -> bool:
        """更新模型版本特征"""
        try:
            # 删除现有的特征关联
            self.db.query(models.ModelVersionFeature) \
                .filter(models.ModelVersionFeature.version_id == version_id) \
                .delete()

            # 添加新的特征关联
            for idx, feature in enumerate(features):
                db_version_feature = models.ModelVersionFeature(
                    version_id=version_id,
                    feature_id=feature["feature_id"],
                    display_order=feature.get("display_order", idx),
                    is_output=feature.get("is_output", False),  # 输出特征标记
                    is_primary_output=feature.get("is_primary_output", False),  # 主输出特征标记
                    is_status=feature.get("is_status", False)  # 状态特征标记
                )
                self.db.add(db_version_feature)

            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            raise e

    def update_feature_display_order(self, version_feature_id: int, display_order: int) -> Optional[
        models.ModelVersionFeature]:
        """更新特征显示顺序"""
        db_version_feature = self.db.query(models.ModelVersionFeature) \
            .filter(models.ModelVersionFeature.id == version_feature_id) \
            .first()

        if not db_version_feature:
            return None

        db_version_feature.display_order = display_order
        self.db.commit()
        self.db.refresh(db_version_feature)
        return db_version_feature


class DeviceFeatureValueCRUD:
    def __init__(self, db: Session):
        self.db = db

    def get_device_feature_value(self, device_id: int, feature_id: int) -> Optional[models.DeviceFeatureValue]:
        """获取设备特征值"""
        return self.db.query(models.DeviceFeatureValue).filter(
            models.DeviceFeatureValue.device_id == device_id,
            models.DeviceFeatureValue.feature_id == feature_id
        ).first()

    def get_device_feature_values(self, device_id: int) -> List[models.DeviceFeatureValue]:
        """获取设备的所有特征值"""
        return self.db.query(models.DeviceFeatureValue) \
            .filter(models.DeviceFeatureValue.device_id == device_id) \
            .all()

    def set_device_feature_value(self, device_id: int, feature_id: int, value: str) -> models.DeviceFeatureValue:
        """设置设备特征值"""
        db_feature_value = self.get_device_feature_value(device_id, feature_id)

        if db_feature_value:
            db_feature_value.value = value
        else:
            db_feature_value = models.DeviceFeatureValue(
                device_id=device_id,
                feature_id=feature_id,
                value=value
            )
            self.db.add(db_feature_value)

        self.db.commit()
        self.db.refresh(db_feature_value)
        return db_feature_value

    def set_device_feature_values(self, device_id: int, feature_values: Dict[int, str]) -> bool:
        """批量设置设备特征值"""
        try:
            for feature_id, value in feature_values.items():
                self.set_device_feature_value(device_id, feature_id, value)
            return True
        except Exception as e:
            self.db.rollback()
            raise e

    def delete_device_feature_value(self, device_id: int, feature_id: int) -> bool:
        """删除设备特征值"""
        db_feature_value = self.get_device_feature_value(device_id, feature_id)
        if not db_feature_value:
            return False

        self.db.delete(db_feature_value)
        self.db.commit()
        return True

    def delete_device_feature_values(self, device_id: int) -> bool:
        """删除设备的所有特征值"""
        try:
            self.db.query(models.DeviceFeatureValue) \
                .filter(models.DeviceFeatureValue.device_id == device_id) \
                .delete()
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            raise e