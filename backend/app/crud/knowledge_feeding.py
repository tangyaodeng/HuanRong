# backend/app/crud/knowledge_feeding.py
from sqlalchemy.orm import Session
from sqlalchemy import func
from .. import models

def search_knowledge_files(db: Session, page: int, page_size: int, status: str = None, search: str = None):
    query = db.query(models.KnowledgeFile)
    if status:
        query = query.filter(models.KnowledgeFile.status == status)
    if search:
        query = query.filter(models.KnowledgeFile.original_name.ilike(f"%{search}%"))
    total = query.count()
    items = query.order_by(models.KnowledgeFile.created_at.desc())\
                 .offset((page - 1) * page_size)\
                 .limit(page_size)\
                 .all()
    total_pages = (total + page_size - 1) // page_size
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }

def get_knowledge_file_stats(db: Session):
    query = db.query(
        models.KnowledgeFile.status,
        func.count(models.KnowledgeFile.id).label("count")
    ).group_by(models.KnowledgeFile.status).all()
    stats = {"total": 0, "pending": 0, "indexing": 0, "completed": 0, "failed": 0}
    for status, count in query:
        stats[status] = count
        stats["total"] += count
    return stats

def create_knowledge_file(db: Session, original_name: str, stored_path: str, file_size: int, description: str = None):
    db_file = models.KnowledgeFile(
        original_name=original_name,
        stored_path=stored_path,
        file_size=file_size,
        description=description,
        status="pending"
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return db_file

def get_knowledge_file(db: Session, file_id: int):
    return db.query(models.KnowledgeFile).filter(models.KnowledgeFile.id == file_id).first()

def delete_knowledge_file(db: Session, file_id: int):
    db_file = get_knowledge_file(db, file_id)
    if db_file:
        db.delete(db_file)
        db.commit()
        return True
    return False

def update_knowledge_file_status(db: Session, file_id: int, new_status: str):
    db_file = get_knowledge_file(db, file_id)
    if db_file:
        db_file.status = new_status
        db.commit()
        db.refresh(db_file)
    return db_file