# crud/device_models.py
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional, List, Dict, Any
from .. import models, schemas
import uuid


class DeviceModelCRUD:
    def __init__(self, db: Session):
        self.db = db

    def get_device_model(self, model_id: int) -> Optional[models.DeviceModel]:
        """获取单个设备模型"""
        return self.db.query(models.DeviceModel).filter(models.DeviceModel.id == model_id).first()

    def get_device_model_by_uuid(self, model_uuid: uuid.UUID) -> Optional[models.DeviceModel]:
        """通过UUID获取设备模型"""
        return self.db.query(models.DeviceModel).filter(models.DeviceModel.uuid == model_uuid).first()

    def get_device_model_by_code(self, code: str) -> Optional[models.DeviceModel]:
        """通过代码获取设备模型"""
        return self.db.query(models.DeviceModel).filter(models.DeviceModel.code == code).first()

    def get_device_models(
            self,
            skip: int = 0,
            limit: int = 100,
            is_predefined: Optional[bool] = None,
            is_active: Optional[bool] = None,
            search: Optional[str] = None
    ) -> List[models.DeviceModel]:
        """获取设备模型列表"""
        query = self.db.query(models.DeviceModel)

        # 应用筛选条件
        if is_predefined is not None:
            query = query.filter(models.DeviceModel.is_predefined == is_predefined)

        if is_active is not None:
            query = query.filter(models.DeviceModel.is_active == is_active)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    models.DeviceModel.name.ilike(search_term),
                    models.DeviceModel.code.ilike(search_term),
                    models.DeviceModel.description.ilike(search_term)
                )
            )

        return query.order_by(models.DeviceModel.id).offset(skip).limit(limit).all()

    def count_device_models(
            self,
            is_predefined: Optional[bool] = None,
            is_active: Optional[bool] = None,
            search: Optional[str] = None
    ) -> int:
        """统计设备模型数量"""
        query = self.db.query(func.count(models.DeviceModel.id))

        # 应用筛选条件
        if is_predefined is not None:
            query = query.filter(models.DeviceModel.is_predefined == is_predefined)

        if is_active is not None:
            query = query.filter(models.DeviceModel.is_active == is_active)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    models.DeviceModel.name.ilike(search_term),
                    models.DeviceModel.code.ilike(search_term),
                    models.DeviceModel.description.ilike(search_term)
                )
            )

        return query.scalar()

    def create_device_model(self, model: schemas.DeviceModelCreate) -> models.DeviceModel:
        """创建设备模型"""
        db_model = models.DeviceModel(
            uuid=uuid.uuid4(),
            name=model.name,
            code=model.code,
            description=model.description,
            is_predefined=model.is_predefined,
            is_active=model.is_active,
            config_schema=model.config_schema or {}
        )
        self.db.add(db_model)
        self.db.commit()
        self.db.refresh(db_model)
        return db_model

    def update_device_model(self, model_id: int, model_update: schemas.DeviceModelUpdate) -> Optional[
        models.DeviceModel]:
        """更新设备模型"""
        db_model = self.get_device_model(model_id)
        if not db_model:
            return None

        update_data = model_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_model, field, value)

        self.db.commit()
        self.db.refresh(db_model)
        return db_model

    def delete_device_model(self, model_id: int) -> bool:
        """删除设备模型"""
        db_model = self.get_device_model(model_id)
        if not db_model:
            return False

        # 检查是否为预定义模型
        if db_model.is_predefined:
            return False

        self.db.delete(db_model)
        self.db.commit()
        return True

    def toggle_device_model_status(self, model_id: int, is_active: bool) -> Optional[models.DeviceModel]:
        """切换设备模型状态"""
        db_model = self.get_device_model(model_id)
        if not db_model:
            return None

        db_model.is_active = is_active
        self.db.commit()
        self.db.refresh(db_model)
        return db_model


class DeviceModelVersionCRUD:
    def __init__(self, db: Session):
        self.db = db

    def get_model_version(self, version_id: int) -> Optional[models.DeviceModelVersion]:
        """获取单个模型版本"""
        return self.db.query(models.DeviceModelVersion) \
            .filter(models.DeviceModelVersion.id == version_id) \
            .first()

    def get_model_version_by_uuid(self, version_uuid: uuid.UUID) -> Optional[models.DeviceModelVersion]:
        """通过UUID获取模型版本"""
        return self.db.query(models.DeviceModelVersion) \
            .filter(models.DeviceModelVersion.uuid == version_uuid) \
            .first()

    def get_model_versions(
            self,
            skip: int = 0,
            limit: int = 100,
            model_id: Optional[int] = None,
            is_active: Optional[bool] = None,
            search: Optional[str] = None
    ) -> List[models.DeviceModelVersion]:
        """获取模型版本列表"""
        query = self.db.query(models.DeviceModelVersion)

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

        return query.order_by(models.DeviceModelVersion.id).offset(skip).limit(limit).all()

    def get_model_versions_by_model(self, model_id: int) -> List[models.DeviceModelVersion]:
        """获取设备模型的所有版本"""
        return self.db.query(models.DeviceModelVersion) \
            .filter(models.DeviceModelVersion.model_id == model_id) \
            .order_by(models.DeviceModelVersion.id) \
            .all()

    def count_model_versions(
            self,
            model_id: Optional[int] = None,
            is_active: Optional[bool] = None,
            search: Optional[str] = None
    ) -> int:
        """统计模型版本数量"""
        query = self.db.query(func.count(models.DeviceModelVersion.id))

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

        return query.scalar()

    def create_model_version(self, version: schemas.DeviceModelVersionCreate) -> models.DeviceModelVersion:
        """创建模型版本"""
        # 检查模型是否存在
        model = self.db.query(models.DeviceModel).filter(models.DeviceModel.id == version.model_id).first()
        if not model:
            raise ValueError(f"设备模型 {version.model_id} 不存在")

        # 检查版本是否已存在
        existing = self.db.query(models.DeviceModelVersion).filter(
            models.DeviceModelVersion.model_id == version.model_id,
            models.DeviceModelVersion.version == version.version
        ).first()

        if existing:
            raise ValueError(f"模型版本 {version.version} 已存在")

        db_version = models.DeviceModelVersion(
            uuid=uuid.uuid4(),
            model_id=version.model_id,
            version=version.version,
            description=version.description,
            config_schema=version.config_schema or {},
            is_active=version.is_active
        )
        self.db.add(db_version)
        self.db.commit()
        self.db.refresh(db_version)
        return db_version

    def update_model_version(self, version_id: int, version_update: schemas.DeviceModelVersionUpdate) -> Optional[
        models.DeviceModelVersion]:
        """更新模型版本"""
        db_version = self.get_model_version(version_id)
        if not db_version:
            return None

        update_data = version_update.dict(exclude_unset=True)

        # 如果更新了版本号，检查是否与其他版本冲突
        if 'version' in update_data and update_data['version'] != db_version.version:
            existing = self.db.query(models.DeviceModelVersion).filter(
                models.DeviceModelVersion.model_id == db_version.model_id,
                models.DeviceModelVersion.version == update_data['version'],
                models.DeviceModelVersion.id != version_id
            ).first()

            if existing:
                raise ValueError(f"模型版本 {update_data['version']} 已存在")

        for field, value in update_data.items():
            setattr(db_version, field, value)

        self.db.commit()
        self.db.refresh(db_version)
        return db_version

    def delete_model_version(self, version_id: int) -> bool:
        """删除模型版本"""
        db_version = self.get_model_version(version_id)
        if not db_version:
            return False

        self.db.delete(db_version)
        self.db.commit()
        return True

    def toggle_model_version_status(self, version_id: int, is_active: bool) -> Optional[models.DeviceModelVersion]:
        """切换模型版本状态"""
        db_version = self.get_model_version(version_id)
        if not db_version:
            return None

        db_version.is_active = is_active
        self.db.commit()
        self.db.refresh(db_version)
        return db_version

    def get_version_with_features(self, version_id: int) -> Optional[Dict[str, Any]]:
        """获取模型版本及其特征"""
        db_version = self.get_model_version(version_id)
        if not db_version:
            return None

        # 获取特征
        from .features import ModelVersionFeatureCRUD
        feature_crud = ModelVersionFeatureCRUD(self.db)
        version_features = feature_crud.get_version_features(version_id)

        result = {
            "version": db_version,
            "features": version_features,
            "feature_count": len(version_features)
        }
        return result