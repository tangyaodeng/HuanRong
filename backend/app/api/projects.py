# backend/app/api/projects.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from ..dependencies.database import get_db
from .. import crud, schemas, models

router = APIRouter(prefix="/projects", tags=["projects"])


# ==================== 基础端点 ====================

@router.get("/", response_model=schemas.ProjectList)
def read_projects(
        db: Session = Depends(get_db),
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(10, ge=1, le=100, description="每页数量"),
        project_status: Optional[str] = Query(None, description="状态筛选"),  # ✅ 重命名
        search: Optional[str] = Query(None, description="搜索关键词")
):
    """获取项目列表（分页、搜索、筛选）"""
    try:
        result = crud.search_projects_with_stats(
            db, page=page, page_size=page_size, status=project_status, search=search  # ✅ 传递参数
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,  # ✅ 此处的 status 是导入的模块
            detail=f"获取项目列表失败: {str(e)}"
        )

@router.get("/stats", response_model=schemas.ProjectStats)
def read_project_stats(db: Session = Depends(get_db)):
    """获取项目统计信息"""
    stats = crud.get_project_stats(db)
    return stats


@router.get("/{project_id}", response_model=schemas.Project)
def read_project(project_id: int, db: Session = Depends(get_db)):
    """获取单个项目详情"""
    db_project = crud.get_project(db, project_id)
    if db_project is None:
        raise HTTPException(status_code=404, detail="项目未找到")
    return db_project


@router.post("/", response_model=schemas.Project, status_code=status.HTTP_201_CREATED)
def create_project(project: schemas.ProjectCreate, db: Session = Depends(get_db)):
    """创建新项目"""
    try:
        return crud.create_project(db, project)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建项目失败: {str(e)}"
        )


@router.put("/{project_id}", response_model=schemas.Project)
def update_project(
        project_id: int,
        project_update: schemas.ProjectUpdate,
        db: Session = Depends(get_db)
):
    """更新项目"""
    try:
        db_project = crud.update_project(db, project_id, project_update)
        if db_project is None:
            raise HTTPException(status_code=404, detail="项目未找到")
        return db_project
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新项目失败: {str(e)}"
        )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    """删除项目"""
    success = crud.delete_project(db, project_id)
    if not success:
        raise HTTPException(status_code=404, detail="项目未找到")
    return None


# ==================== 简化设备端点 ====================

@router.get("/{project_id}/devices")
def read_project_devices(project_id: int, db: Session = Depends(get_db)):
    """获取项目的设备列表（简化版）"""
    project = crud.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目未找到")

    try:
        devices = db.query(models.Device) \
            .filter(models.Device.project_id == project_id) \
            .order_by(models.Device.created_at.desc()) \
            .all()

        return {
            "devices": devices,
            "total": len(devices),
            "project_id": project_id,
            "project_name": project.name
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取设备列表失败: {str(e)}"
        )