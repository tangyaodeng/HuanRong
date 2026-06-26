import os
import logging
import ollama
import re
from ..celery_app import celery_app
from ..models import KnowledgeFile, DocumentChunk
from ..database import SessionLocal
from ..crud.knowledge_feeding import update_knowledge_file_status

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = 'nomic-embed-text'
CHUNK_SIZE = 2000      # 单块上限（实际略超也接受）
CHUNK_GROW = 50        # 允许微超的缓冲
MAX_RETRIES = 3        # 单块嵌入失败重试次数


def split_text(text):
    """QA 感知分块：按 **数字. 拆分 QA，超长再按句号切"""
    import re

    chunks = []
    qa_parts = re.split(r'(?=\*\*\d+[\s.、])', text)
    qa_parts = [p.strip() for p in qa_parts if p.strip()]

    for qa in qa_parts:
        if len(qa) <= CHUNK_SIZE:
            chunks.append(qa)
            continue

        title_match = re.match(r'(\*\*\d+[\s.、][^*]+\*\*\s*)', qa)
        prefix = title_match.group(1) if title_match else ""
        body_start = title_match.end() if title_match else 0

        sentences = re.split(r'(?<=[。！？])\s*', qa[body_start:])
        current = qa[:body_start]  # 标题部分不参加句子拆分
        merged = []
        for sent in sentences:
            if not sent.strip():
                continue
            # 单句超限：先填满当前块，再拆剩余
            while len(sent) > CHUNK_SIZE:
                take = CHUNK_SIZE - len(current)
                if take > 0:
                    current += sent[:take]
                    sent = sent[take:]
                if current.strip():
                    merged.append(current.strip())
                    current = ""
            if len(current) + len(sent) <= CHUNK_SIZE:
                current += sent
            else:
                if current.strip():
                    merged.append(current.strip())
                current = sent
        if current.strip():
            merged.append(current.strip())

        # 如果第一块太短（仅有标题），合并到下一块
        if len(merged) > 1 and len(merged[0]) < 100:
            merged[1] = merged[0] + merged[1]
            merged.pop(0)

        # 非首块补标题前缀
        for i, m in enumerate(merged):
            if i == 0:
                chunks.append(m)
            else:
                chunks.append(prefix + "(续)\n" + m)

    return chunks


@celery_app.task(bind=True, max_retries=3, name='app.tasks.knowledge_tasks.process_file_async')
def process_file_async(self, file_id: int):
    db = SessionLocal()
    try:
        db_file = update_knowledge_file_status(db, file_id, "indexing")
        if not db_file:
            raise ValueError(f"文件ID {file_id} 不存在")

        file_path = db_file.stored_path
        source_name = db_file.original_name

        from ..services.file_extractor import extract_text
        text = extract_text(file_path)

        chunks = split_text(text)
        logger.info(f"文件 {source_name} 分块完成，共 {len(chunks)} 个块")

        embedded = 0
        skipped = 0

        for i, chunk in enumerate(chunks):
            # 去重：跳过已存在的相同内容
            existing = db.query(DocumentChunk).filter(
                DocumentChunk.file_id == file_id,
                DocumentChunk.content == chunk
            ).first()
            if existing:
                logger.info(f"  块 {i+1}/{len(chunks)} 已存在，跳过")
                skipped += 1
                continue

            # 嵌入，失败重试
            last_err = None
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    resp = ollama.embeddings(model=EMBEDDING_MODEL, prompt=chunk)
                    embedding = resp['embedding']
                    break
                except Exception as e:
                    last_err = e
                    if attempt < MAX_RETRIES:
                        logger.warning(f"  块 {i+1} 嵌入失败 (尝试 {attempt}/{MAX_RETRIES}): {e}")
                    else:
                        logger.error(f"  块 {i+1} 嵌入最终失败: {e}")

            if embedding is None:
                logger.error(f"  块 {i+1} 嵌入失败，跳过: {last_err}")
                skipped += 1
                continue

            doc_chunk = DocumentChunk(
                source=source_name,
                content=chunk,
                embedding=embedding,
                file_id=file_id,
                chunk_index=i
            )
            db.add(doc_chunk)
            embedded += 1

            if (i + 1) % 10 == 0:
                db.commit()
                logger.info(f"  已嵌入 {embedded}/{len(chunks)} 个块")

        db.commit()
        update_knowledge_file_status(db, file_id, "completed")
        logger.info(f"文件 {file_id} ({source_name}) 处理完成，嵌入 {embedded} 个块，跳过 {skipped} 个")

    except Exception as e:
        db.rollback()
        logger.error(f"处理文件 {file_id} 失败: {str(e)}")
        try:
            update_knowledge_file_status(db, file_id, "failed")
        except Exception:
            pass
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()
