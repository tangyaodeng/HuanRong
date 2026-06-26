# backend/app/api/knowledge_feeding.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from sqlalchemy.orm import Session
from typing import Optional, List
import os
import shutil
from ..dependencies.database import get_db
from .. import crud, schemas, models
from ..crud.knowledge_feeding import (
    search_knowledge_files,
    get_knowledge_file_stats,
    create_knowledge_file,
    get_knowledge_file as crud_get_file,
    delete_knowledge_file as crud_delete_file,
    update_knowledge_file_status as crud_update_status
)
from ..tasks.knowledge_tasks import process_file_async
from ..services.file_extractor import ALLOWED_EXTENSIONS

router = APIRouter(prefix="/knowledge-feeding", tags=["knowledge-feeding"])

UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "uploads",
    "knowledge"
)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ==================== 文件列表 ====================
@router.get("/", response_model=schemas.KnowledgeFileList)
def list_knowledge_files(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None, description="状态筛选"),
    search: Optional[str] = Query(None, description="搜索文件名")
):
    """获取知识文件列表（分页、筛选、搜索）"""
    try:
        result = search_knowledge_files(
            db, page=page, page_size=page_size,
            status=status, search=search
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文件列表失败: {str(e)}"
        )

# ==================== 统计信息 ====================
@router.get("/stats", response_model=schemas.KnowledgeFileStats)
def get_knowledge_stats(db: Session = Depends(get_db)):
    """获取知识文件统计"""
    stats = get_knowledge_file_stats(db)
    return stats

# ==================== 上传文件 ====================
@router.post("/upload", response_model=List[schemas.KnowledgeFileOut], status_code=status.HTTP_201_CREATED)
async def upload_knowledge_file(
    files: List[UploadFile] = File(...),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """上传知识文件（支持批量）"""
    results = []
    for file in files:
        # 校验文件类型
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise HTTPException(status_code=400, detail=f"不支持的文件格式: {file.filename}，仅支持 {allowed}")

        # 保存文件到本地
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        base, ext_no = os.path.splitext(file.filename)
        counter = 1
        while os.path.exists(file_path):
            file_path = os.path.join(UPLOAD_DIR, f"{base}_{counter}{ext_no}")
            counter += 1

        try:
            await file.seek(0)  # 确保文件指针在开头
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

        # 记录到数据库
        db_file = create_knowledge_file(
            db,
            original_name=file.filename,
            stored_path=file_path,
            file_size=os.path.getsize(file_path),
            description=description
        )
        process_file_async.delay(db_file.id)
        results.append(db_file)

    return results

# ==================== 删除文件 ====================
@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_file(file_id: int, db: Session = Depends(get_db)):
    """删除知识文件（同时删除物理文件）"""
    db_file = crud_get_file(db, file_id)
    if not db_file:
        raise HTTPException(status_code=404, detail="文件未找到")

    # 删除物理文件
    if os.path.exists(db_file.stored_path):
        os.remove(db_file.stored_path)

    crud_delete_file(db, file_id)
    return None

# ==================== 重新处理（可选） ====================
@router.post("/{file_id}/reprocess", response_model=schemas.KnowledgeFileOut)
def reprocess_file(file_id: int, db: Session = Depends(get_db)):
    """重新索引文件"""
    db_file = crud_update_status(db, file_id, "pending")
    if not db_file:
        raise HTTPException(status_code=404, detail="文件未找到")
    process_file_async.delay(file_id)            # 别忘了触发任务！
    # 触发后台处理
    return db_file