#crud/device.py
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional, List, Dict, Any
from .. import models, schemas
import uuid


def get_device(db: Session, device_id: int):
    """获取单个设备"""
    return db.query(models.Device).filter(models.Device.id == device_id).first()


def get_device_by_uuid(db: Session, device_uuid: str):
    """通过UUID获取设备"""
    return db.query(models.Device).filter(models.Device.uuid == uuid.UUID(device_uuid)).first()


def get_device_by_identifier(db: Session, project_id: int, identifier: str):
    """通过项目ID和设备标识符获取设备"""
    return db.query(models.Device).filter(
        models.Device.project_id == project_id,
        models.Device.identifier == identifier
    ).first()


def get_devices(
        db: Session,
        skip: int = 0,
        limit: int = 10,
        project_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
):
    """获取设备列表（带分页和筛选）"""
    query = db.query(models.Device)

    # 项目筛选
    if project_id:
        query = query.filter(models.Device.project_id == project_id)

    # 状态筛选
    if status:
        query = query.filter(models.Device.status == status)

    # 搜索（名称、标识符、描述、位置）
    if search:
        search_filter = or_(
            models.Device.name.ilike(f"%{search}%"),
            models.Device.identifier.ilike(f"%{search}%"),
            models.Device.description.ilike(f"%{search}%"),
            models.Device.location.ilike(f"%{search}%"),
        )
        query = query.filter(search_filter)

    # 计算总数
    total = query.count()

    # 分页获取数据
    devices = query.order_by(models.Device.updated_at.desc()).offset(skip).limit(limit).all()

    return devices, total


def create_device(db: Session, device: schemas.DeviceBase, project_id: Optional[int] = None):
    """为项目创建设备"""
    # 检查项目是否存在
    if not project_id:
        # 如果没有指定项目，使用第一个项目或返回错误
        first_project = db.query(models.Project).first()
        if not first_project:
            raise ValueError("没有可用的项目，请先创建项目")
        project_id = first_project.id

    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise ValueError(f"项目ID {project_id} 不存在")

    # 检查设备标识符在项目内是否唯一
    existing = get_device_by_identifier(db, project_id, device.identifier)
    if existing:
        raise ValueError(f"设备标识符 '{device.identifier}' 在项目内已存在")

    db_device = models.Device(
        project_id=project_id,
        name=device.name,
        identifier=device.identifier,
        description=device.description,
        status=device.status,
        location=device.location,
        device_metadata=device.device_metadata or {}
    )

    db.add(db_device)

    # 更新项目的设备计数
    project.device_count = db.query(func.count(models.Device.id)).filter(
        models.Device.project_id == project_id
    ).scalar()

    db.commit()
    db.refresh(db_device)
    return db_device


def update_device(db: Session, device_id: int, device_update: schemas.DeviceBase):
    """更新设备"""
    db_device = get_device(db, device_id)
    if not db_device:
        return None

    update_data = device_update.dict(exclude_unset=True)

    # 如果更新了设备标识符，检查是否重复
    if "identifier" in update_data and update_data["identifier"] != db_device.identifier:
        existing = get_device_by_identifier(db, db_device.project_id, update_data["identifier"])
        if existing:
            raise ValueError(f"设备标识符 '{update_data['identifier']}' 在项目内已存在")

    for field, value in update_data.items():
        setattr(db_device, field, value)

    db.commit()
    db.refresh(db_device)
    return db_device


def delete_device(db: Session, device_id: int):
    """删除设备"""
    db_device = get_device(db, device_id)
    if not db_device:
        return False

    project_id = db_device.project_id
    db.delete(db_device)

    # 更新项目的设备计数
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if project:
        project.device_count = db.query(func.count(models.Device.id)).filter(
            models.Device.project_id == project_id
        ).scalar()

    db.commit()
    return True


def get_project_devices(db: Session, project_id: int, skip: int = 0, limit: int = 10):
    """获取指定项目的设备列表"""
    # 检查项目是否存在
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise ValueError(f"项目ID {project_id} 不存在")

    query = db.query(models.Device).filter(models.Device.project_id == project_id)

    # 计算总数
    total = query.count()

    # 分页获取数据
    devices = query.order_by(models.Device.updated_at.desc()).offset(skip).limit(limit).all()

    return {
        "devices": devices,
        "total": total,
        "project_id": project_id,
        "project_name": project.name
    }


def search_devices_with_stats(
        db: Session,
        page: int = 1,
        page_size: int = 10,
        project_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
):
    """搜索设备并返回统计信息"""
    skip = (page - 1) * page_size

    # 获取设备列表
    devices, total = get_devices(db, skip, page_size, project_id, status, search)

    # 计算分页信息
    total_pages = (total + page_size - 1) // page_size

    return {
        "devices": devices,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }