# app/crud/__init__.py
from .data_source import *
from .projects import (
    get_project,
    get_project_by_uuid,
    get_project_by_code,
    get_projects,
    create_project,
    update_project,
    delete_project,
    get_project_stats,
    search_projects_with_stats  # ✅ 添加这一行
)
__all__ = [
    "get_project",
    "get_project_by_uuid",
    "get_project_by_code",
    "get_projects",
    "create_project",
    "update_project",
    "delete_project",
    "get_project_stats",
    "search_projects_with_stats"
]