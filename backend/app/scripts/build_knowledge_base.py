#backend/app/scripts/build_knowledge_base.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.database import SessionLocal
from app.models import DocumentChunk
import ollama
import re

EMBEDDING_MODEL = 'nomic-embed-text'
CHUNK_SIZE = 2000


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
        current = qa[:body_start]
        merged = []
        for sent in sentences:
            if not sent.strip():
                continue
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

        if len(merged) > 1 and len(merged[0]) < 100:
            merged[1] = merged[0] + merged[1]
            merged.pop(0)

        for i, m in enumerate(merged):
            if i == 0:
                chunks.append(m)
            else:
                chunks.append(prefix + "(续)\n" + m)

    return chunks


def embed_chunks(chunks):
    embeddings = []
    for i, chunk in enumerate(chunks):
        resp = ollama.embeddings(model=EMBEDDING_MODEL, prompt=chunk)
        embeddings.append(resp['embedding'])
        if (i+1) % 10 == 0:
            print(f"  已嵌入 {i+1}/{len(chunks)} 个块")
    return embeddings


def build_knowledge_base(file_path: str, clear_existing: bool = False):
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    chunks = split_text(text)
    print(f"分块完成，共 {len(chunks)} 个块")

    embeddings = embed_chunks(chunks)
    print("嵌入完成，正在写入数据库...")

    db = SessionLocal()
    if clear_existing:
        db.query(DocumentChunk).delete()
        db.commit()
        print("已清空旧知识库")

    source = os.path.basename(file_path)
    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        db.add(DocumentChunk(source=source, content=chunk, embedding=emb, chunk_index=i))
    db.commit()
    db.close()
    print(f"成功写入 {len(chunks)} 条记录")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python build_knowledge_base.py <txt文件路径> [--clear]")
        sys.exit(1)
    clear = '--clear' in sys.argv
    build_knowledge_base(sys.argv[1], clear_existing=clear)
