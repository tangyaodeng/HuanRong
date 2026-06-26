#crud/projects.py
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional, List
from .. import models, schemas
import uuid


def get_project(db: Session, project_id: int):
    """获取单个项目"""
    return db.query(models.Project).filter(models.Project.id == project_id).first()


def get_project_by_uuid(db: Session, project_uuid: str):
    """通过UUID获取项目"""
    return db.query(models.Project).filter(models.Project.uuid == uuid.UUID(project_uuid)).first()


def get_project_by_code(db: Session, code: str):
    """通过项目代码获取项目"""
    return db.query(models.Project).filter(models.Project.code == code).first()


def get_projects(
        db: Session,
        skip: int = 0,
        limit: int = 10,
        status: Optional[str] = None,
        search: Optional[str] = None
):
    """获取项目列表（带分页和筛选）"""
    query = db.query(models.Project)

    # 状态筛选
    if status:
        query = query.filter(models.Project.status == status)

    # 搜索（名称、代码、描述、标签）
    if search:
        search_filter = or_(
            models.Project.name.ilike(f"%{search}%"),
            models.Project.code.ilike(f"%{search}%"),
            models.Project.description.ilike(f"%{search}%"),
        )
        query = query.filter(search_filter)

    # 计算总数
    total = query.count()

    # 分页获取数据
    projects = query.order_by(models.Project.updated_at.desc()).offset(skip).limit(limit).all()

    return projects, total


def create_project(db: Session, project: schemas.ProjectCreate):
    """创建新项目"""
    # 检查项目代码是否已存在
    existing = get_project_by_code(db, project.code)
    if existing:
        raise ValueError(f"项目代码 '{project.code}' 已存在")

    db_project = models.Project(
        name=project.name,
        code=project.code,
        description=project.description,
        status=project.status,
        tags=project.tags or []
    )

    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


def update_project(db: Session, project_id: int, project_update: schemas.ProjectUpdate):
    """更新项目"""
    db_project = get_project(db, project_id)
    if not db_project:
        return None

    update_data = project_update.dict(exclude_unset=True)

    # 如果更新了项目代码，检查是否重复
    if "code" in update_data and update_data["code"] != db_project.code:
        existing = get_project_by_code(db, update_data["code"])
        if existing:
            raise ValueError(f"项目代码 '{update_data['code']}' 已存在")

    for field, value in update_data.items():
        setattr(db_project, field, value)

    db.commit()
    db.refresh(db_project)
    return db_project


def delete_project(db: Session, project_id: int):
    """删除项目"""
    db_project = get_project(db, project_id)
    if not db_project:
        return None

    db.delete(db_project)
    db.commit()
    return True


def get_project_stats(db: Session):
    """获取项目统计信息"""
    total_projects = db.query(func.count(models.Project.id)).scalar()
    active_projects = db.query(func.count(models.Project.id)).filter(
        models.Project.status == "active"
    ).scalar()
    total_devices = db.query(func.sum(models.Project.device_count)).scalar() or 0

    return {
        "total_projects": total_projects,
        "active_projects": active_projects,
        "total_devices": total_devices
    }


def search_projects_with_stats(
        db: Session,
        page: int = 1,
        page_size: int = 10,
        status: Optional[str] = None,
        search: Optional[str] = None
):
    """搜索项目并返回统计信息"""
    skip = (page - 1) * page_size

    # 获取项目列表
    projects, total = get_projects(db, skip, page_size, status, search)

    # 获取概览统计
    stats = get_project_stats(db)

    # 计算分页信息
    total_pages = (total + page_size - 1) // page_size

    return {
        "projects": projects,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "overview": stats
    }