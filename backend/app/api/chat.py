# backend/app/api/chat.py
from fastapi import APIRouter, HTTPException, File, UploadFile
from pydantic import BaseModel
import ollama
import json
from typing import List, Dict, Optional
import pymysql
from ..config import settings
from .point_map import build_point_map
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from fastapi import Depends
from ..database import get_db
from ..models import ChatConversation, ChatMessage
from ..database import SessionLocal
from ..models import DocumentChunk
from sqlalchemy import func
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from openai import OpenAI
import logging
import tempfile
import subprocess
import os
import shutil
router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None
    model: str = "deepseek"   # 新增字段，可选 "qwen" 或 "deepseek"


class ChatResponse(BaseModel):
    response: str
    conversation_id: int
    title: str


class VoiceResponse(BaseModel):
    text: str
    success: bool = True

POINT_MAP = build_point_map()

# ---------- 数据库查询函数 ----------
def get_point_data(business_name: str,
                   start_time: Optional[str] = None,
                   end_time: Optional[str] = None,
                   aggregation: str = "latest") -> dict:
    if business_name not in POINT_MAP:
        return {"success": False, "message": f"未知的业务名称: {business_name}"}

    tag_ids = POINT_MAP[business_name]
    if not tag_ids:
        return {"success": False, "message": "该业务名下无点位"}

    conn = pymysql.connect(
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        user=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        database=settings.MYSQL_DATABASE,
        charset=settings.MYSQL_CHARSET,
        connect_timeout=10,
        read_timeout=30
    )
    try:
        values = []
        tables_with_data = 0
        with conn.cursor() as cursor:
            for tag in tag_ids:
                table = tag
                time_condition = ""
                if start_time and end_time:
                    time_condition = f"WHERE UpdateDateTime BETWEEN '{start_time}' AND '{end_time}'"
                elif start_time:
                    time_condition = f"WHERE UpdateDateTime >= '{start_time}'"
                elif end_time:
                    time_condition = f"WHERE UpdateDateTime <= '{end_time}'"

                if aggregation == "latest":
                    sql = f"SELECT PointValue FROM `{table}` {time_condition} ORDER BY UpdateDateTime DESC LIMIT 1"
                else:
                    agg_func = aggregation.upper()
                    sql = f"SELECT {agg_func}(PointValue) AS val FROM `{table}` {time_condition}"

                print(f"[DEBUG] 查询表 {table}，SQL: {sql}")

                try:
                    cursor.execute(sql)
                    row = cursor.fetchone()
                    if row is not None:
                        tables_with_data += 1
                        if row[0] is not None:
                            values.append(float(row[0]))
                except Exception as e:
                    print(f"[ERROR] 查询表 {table} 失败: {e}")
                    return {"success": False, "message": f"查询表 {table} 失败: {str(e)}"}

        if tables_with_data == 0:
            return {"success": True, "data": None, "message": "该时间段内无数据记录"}

        if not values:
            return {"success": True, "data": 0, "message": "查询成功，但所有数值均为 NULL，按0处理"}

        if aggregation in ("latest", "avg"):
            result = sum(values) / len(values)
        elif aggregation == "sum":
            result = sum(values)
        elif aggregation == "max":
            result = max(values)
        elif aggregation == "min":
            result = min(values)
        else:
            result = sum(values) / len(values)

        return {"success": True, "data": result, "message": "查询成功"}
    finally:
        conn.close()

def retrieve_relevant_chunks(query: str, top_k: int = 50) -> List[tuple]:
    """二阶段检索：关键词粗筛 top 100 → 向量精排 top 50"""
    db = SessionLocal()
    try:
        all_chunks = db.query(DocumentChunk.content).all()
        total = len(all_chunks)
        print(f"[RAG] 知识库共 {total} 条分块，二阶段检索")

        # 阶段一：关键词粗筛
        kw_candidates = []
        for (content,) in all_chunks:
            kw = _keyword_score(query, content)
            if kw > 0:
                kw_candidates.append((kw, content))
        kw_candidates.sort(reverse=True)
        coarse = kw_candidates[:30]
        print(f"[RAG] 关键词命中 {len(kw_candidates)} 块，取 top {len(coarse)} 进入向量精排（限30条控制延迟）")

        if not coarse:
            return []

        # 阶段二：ollama 向量精排
        resp = ollama.embeddings(model='nomic-embed-text', prompt=query)
        query_emb = resp['embedding']
        import numpy as np
        q_vec = np.array(query_emb).reshape(1, -1)

        def _cosine_dist(a, b):
            return 1.0 - float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))

        ranked = []
        for kw, content in coarse:
            emb_resp = ollama.embeddings(model='nomic-embed-text', prompt=content[:1000])
            c_vec = np.array(emb_resp['embedding']).reshape(1, -1)
            dist = _cosine_dist(q_vec[0], c_vec[0])
            ranked.append((dist, kw, content))

        ranked.sort()
        result = [(content, dist) for dist, kw, content in ranked[:top_k]]
        print(f"[RAG] 向量精排完成，返回 top {len(result)}")
        return result
    finally:
        db.close()

def _is_point_data_query(query: str) -> bool:
    """检测是否为点位数据查询（应跳过 RAG，走 get_point_data 工具）"""
    # 1. 查询中包含已知业务名称
    for name in POINT_MAP:
        if name in query or query in name:
            return True

    # 2. 包含数据查询意图词 + 指标关键词
    data_intent = {"多少", "查询", "数据", "今天", "昨天", "最近", "现在", "运行",
                   "是多少", "怎么样", "查一下", "帮我查", "看看", "监测",
                   "功率", "频率", "压力", "温度", "流量", "状态", "能耗"}
    knowledge_intent = {"是什么", "原理", "为什么", "如何实现", "怎么工作",
                        "什么意思", "定义", "解释", "作用", "功能", "组成"}
    # 有数据意图且无明显知识意图
    if any(w in query for w in data_intent) and not any(w in query for w in knowledge_intent):
        return True

    return False

def _clean_chunk(text: str) -> str:
    import re
    text = re.sub(r'\$\s*\\[a-zA-Z]+\s*\$', ' ', text)
    text = re.sub(r'\$[^\$]*\$', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _keyword_score(query: str, text: str) -> float:
    import jieba
    q_words = list(jieba.cut(query))
    t_words = set(jieba.cut(text))
    q_real = {w for w in q_words if len(w.strip()) >= 2}
    if not q_real:
        return 0.0
    return sum(1 for w in q_real if w in t_words) / len(q_real)


def _extract_qa(chunk: str, query: str) -> str:
    import jieba
    import re

    parts = re.split(r'(?=\*\*\d+[\s.、])', chunk)
    if len(parts) <= 1:
        return chunk

    q_words = set(jieba.cut(query))
    best_score = -1
    best_part = chunk
    for part in parts:
        if not part.strip():
            continue
        title_match = re.match(r'(\*\*\d+[\s.、][^*]+\*\*)', part)
        body = part[title_match.end():] if title_match else part
        title_text = title_match.group(1) if title_match else ""
        t_title = set(jieba.cut(title_text))
        t_body = set(jieba.cut(body))
        score = len(q_words & t_title) * 2 + len(q_words & t_body)
        if score > best_score:
            best_score = score
            best_part = part

    return best_part

def _continue_across_chunks(qa: str, all_contents: list = None) -> str:
    """不再跨块拼接，直接返回 qa"""
    return qa

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_point_data",
            "description": (
                "查询工业点位数据。参数 business_name 必须是下列名称之一："
                + ", ".join(sorted(POINT_MAP.keys()))
                + "\n start_time/end_time 格式 YYYY-MM-DD HH:MM:SS，可选。"
                + "\n aggregation 可选 latest, avg, sum, max, min。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "business_name": {"type": "string", "description": "点位业务名"},
                    "start_time": {"type": "string", "description": "开始时间 YYYY-MM-DD HH:MM:SS", "nullable": True},
                    "end_time": {"type": "string", "description": "结束时间 YYYY-MM-DD HH:MM:SS", "nullable": True},
                    "aggregation": {"type": "string", "description": "latest, avg, sum, max, min", "default": "latest"}
                },
                "required": ["business_name"]
            }
        }
    }
]

# ---------- 系统提示 ----------
def build_system_prompt() -> str:
    beijing_tz = timezone(timedelta(hours=8))
    current_datetime = datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")

    names = "\n".join([f"- {name}" for name in sorted(POINT_MAP.keys())])
    prompt = f"""你是一个智慧暖通AI助手，有两个职责：
1. 回答任何通用知识问题（如制冷原理、设备工作原理等）。
2. 当用户询问空调系统运行数据时，使用 get_point_data 工具查询数据库后回答。

当前准确日期时间（北京时间）：{current_datetime}
数据库中所有时间字段均使用北京时间（UTC+8）。

当用户说"最近N天"、"今天"、"昨天"等相对时间时，你必须基于当前北京时间计算 start_time 和 end_time：
- "今天"：start_time = 今天 00:00:00（北京时间），end_time = 当前时间（北京时间）
- "最近N天"：start_time = 当前日期 - N天 的 00:00:00，end_time = 当前完整日期时间（北京时间）

切勿使用训练数据中的任意固定日期，必须基于上面的北京时间进行计算。

【可查询的业务名称】
{names}
...
"""
    return prompt

deepseek_client = OpenAI(
    api_key=settings.DEEPSEEK_APIKEY,
    base_url="https://api.deepseek.com"
)

def call_deepseek_api(messages: List[Dict], tools=None, max_tokens=2048, temperature=0.1) -> dict:
    try:
        kwargs = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            # kwargs["tool_choice"] = "auto"

        response = deepseek_client.chat.completions.create(**kwargs)
        # 将 DeepSeek 的响应包装成与 Ollama 类似的格式，方便后续处理
        choice = response.choices[0]
        result = {
            "message": {
                "role": choice.message.role,
                "content": choice.message.content,
                "tool_calls": []
            }
        }
        if choice.message.tool_calls:
            result["message"]["tool_calls"] = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                } for tc in choice.message.tool_calls
            ]
        return result
    except Exception as e:
        # ✅ 添加调试信息，打印 API 返回的错误详情
        if hasattr(e, 'response'):
            try:
                print(f"[DeepSeek API] 状态码: {e.response.status_code}")
                print(f"[DeepSeek API] 响应体: {e.response.text}")
            except:
                pass
        raise HTTPException(status_code=502, detail=f"DeepSeek API 调用失败: {str(e)}")

# ---------- 核心对话处理 ----------
def process_chat(message: str) -> str:
    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": message}
    ]

    response = ollama.chat(
        model='qwen2.5:14b',
        messages=messages,
        tools=TOOLS,
        options={"temperature": 0.1, "num_predict": 2048}
    )

    if response['message'].get('tool_calls'):
        tool_calls = response['message']['tool_calls']
        for tool_call in tool_calls:
            if tool_call['function']['name'] == 'get_point_data':
                args = tool_call['function']['arguments']
                try:
                    result = get_point_data(
                        business_name=args.get('business_name'),
                        start_time=args.get('start_time'),
                        end_time=args.get('end_time'),
                        aggregation=args.get('aggregation', 'latest')
                    )
                    result_str = json.dumps(result, ensure_ascii=False)
                except Exception as e:
                    result_str = json.dumps({"success": False, "message": str(e)})
                messages.append({"role": "tool", "content": result_str})
            else:
                messages.append({"role": "tool", "content": "未知工具调用"})

        final_response = ollama.chat(model='qwen2.5:14b', messages=messages)
        return final_response['message']['content']
    else:
        return response['message']['content']

# ---------- 离线语音识别（openai-whisper）----------
WHISPER_MODEL_NAME = "base"
FFMPEG_PATH = r"D:\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe"

_whisper_model = None


def _get_whisper():
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    # whisper 内部需要 ffmpeg，先加到 PATH
    ffmpeg_dir = os.path.dirname(FFMPEG_PATH)
    if ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
    import whisper
    logger.info(f"加载 Whisper 模型: {WHISPER_MODEL_NAME}")
    _whisper_model = whisper.load_model(WHISPER_MODEL_NAME)
    logger.info("Whisper 模型加载完成")
    return _whisper_model


def _transcribe_audio(audio_bytes: bytes, original_ext: str = "webm") -> str:
    """接收音频文件 bytes，直接调 openai-whisper 识别（whisper 内部用 ffmpeg 解码）"""
    tmp_dir = tempfile.mkdtemp(prefix="voice_")
    input_path = os.path.join(tmp_dir, f"input.{original_ext}")
    try:
        # 写入原始音频到临时文件
        with open(input_path, "wb") as f:
            f.write(audio_bytes)

        # openai-whisper 识别（initial_prompt 引导简体中文输出）
        model = _get_whisper()
        result_obj = model.transcribe(
            input_path,
            language="zh",
            initial_prompt="以下是普通话的简体中文转写结果："
        )
        result = (result_obj.get("text") or "").strip()
        if not result:
            return ""
        logger.info(f"语音识别完成: {result[:80]}...")
        return result

    except Exception as e:
        logger.error(f"语音识别异常: {e}")
        raise RuntimeError(f"语音识别失败: {str(e)}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------- FastAPI 路由 ----------
@router.post("/", response_model=ChatResponse)
async def chat_with_ai(request: ChatRequest, db: Session = Depends(get_db)):
    # 1. 如果没有传 conversation_id，创建新会话
    if request.conversation_id is None:
        new_conv = ChatConversation(title="新对话")
        db.add(new_conv)
        db.commit()
        db.refresh(new_conv)
        conv_id = new_conv.id
    else:
        conv = db.query(ChatConversation).filter(
            ChatConversation.id == request.conversation_id,
            ChatConversation.is_deleted == False
        ).first()
        if not conv:
            raise HTTPException(status_code=404, detail="对话不存在")
        conv_id = conv.id

    # 2. 保存用户消息
    user_msg = ChatMessage(conversation_id=conv_id, role="user", content=request.message)
    db.add(user_msg)
    db.commit()

    # 3. 获取历史消息
    history = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conv_id
    ).order_by(ChatMessage.created_at.asc()).all()

    messages_for_ai = build_messages_for_ai(history)

    # 4. 调用 AI
    answer = process_chat_with_history(messages_for_ai, model=request.model)

    # 5. 保存 AI 回复
    assistant_msg = ChatMessage(conversation_id=conv_id, role="assistant", content=answer)
    db.add(assistant_msg)
    db.commit()

    # 6. 更新会话标题
    if len(history) <= 2:
        title = request.message[:20] + ('...' if len(request.message) > 20 else '')
        db.query(ChatConversation).filter(ChatConversation.id == conv_id).update({"title": title})
        db.commit()
    else:
        title = conv.title

    return ChatResponse(response=answer, conversation_id=conv_id, title=title)

@router.get("/conversations")
async def list_conversations(db: Session = Depends(get_db)):
    convs = db.query(ChatConversation).filter(ChatConversation.is_deleted == False).order_by(ChatConversation.updated_at.desc()).all()
    return [
        {"id": c.id, "title": c.title, "created_at": c.created_at.isoformat()}
        for c in convs
    ]

@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.post("/voice", response_model=VoiceResponse)
async def voice_to_text(audio: UploadFile = File(...)):
    """接收浏览器录音（webm/ogg），返回语音识别文本"""
    if not audio.content_type:
        raise HTTPException(status_code=400, detail="未知的音频格式")

    # 推断扩展名
    ext = "webm"
    if "ogg" in audio.content_type or "opus" in audio.content_type:
        ext = "ogg"
    elif "wav" in audio.content_type:
        ext = "wav"
    elif "webm" in audio.content_type:
        ext = "webm"

    try:
        audio_bytes = await audio.read()
        if not audio_bytes or len(audio_bytes) < 100:
            raise HTTPException(status_code=400, detail="音频数据为空")

        text = _transcribe_audio(audio_bytes, original_ext=ext)
        if not text:
            return VoiceResponse(text="", success=False)
        return VoiceResponse(text=text, success=True)

    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"语音识别接口异常: {e}")
        raise HTTPException(status_code=500, detail=f"语音识别服务异常: {str(e)}")

@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: int, db: Session = Depends(get_db)):
    conv = db.query(ChatConversation).filter(ChatConversation.id == conv_id, ChatConversation.is_deleted == False).first()
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    messages = db.query(ChatMessage).filter(ChatMessage.conversation_id == conv_id).order_by(ChatMessage.created_at.asc()).all()
    return {
        "id": conv.id,
        "title": conv.title,
        "messages": [
            {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
            for m in messages
        ]
    }

@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: int, db: Session = Depends(get_db)):
    conv = db.query(ChatConversation).filter(ChatConversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    conv.is_deleted = True
    db.commit()
    return {"message": "对话已删除"}

def build_messages_for_ai(history: List[ChatMessage]) -> List[Dict]:
    messages = [{"role": "system", "content": build_system_prompt()}]
    for msg in history:
        role = msg.role
        if role in ("user", "assistant", "tool"):
            messages.append({"role": role, "content": msg.content})
    return messages


OLLAMA_TIMEOUT = 120  # ollama 调用超时秒数


def _ollama_chat_with_timeout(**kwargs) -> dict:
    """带超时的 ollama.chat 调用，防止小模型卡死"""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(ollama.chat, **kwargs)
        try:
            return future.result(timeout=OLLAMA_TIMEOUT)
        except FutureTimeoutError:
            raise HTTPException(status_code=504, detail="AI 模型响应超时，请简化问题后重试")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI 服务异常: {str(e)}")


# 在文件顶部增加配置常量（可放在函数外）
def process_chat_with_history(messages: List[Dict], model: str = "deepseek", enable_rag: bool = True) -> str:
    user_query = ""
    for m in reversed(messages):
        if m['role'] == 'user':
            user_query = m['content']
            break

    # RAG 检索 — 收集参考资料供 AI 参考
    rag_refs = []
    if enable_rag and user_query and not _is_point_data_query(user_query):
        try:
            retrieved = retrieve_relevant_chunks(user_query, top_k=50)
            print(f"[RAG] 用户问题: {user_query[:50]}...")
            for content, dist in retrieved:
                kw = _keyword_score(user_query, content)
                print(f"[RAG]   距离{dist:.4f} 关键词{kw:.2f}: {content[:50]}...")

            if retrieved:
                # 筛选有意义的参考资料
                for content, dist in retrieved:
                    kw = _keyword_score(user_query, content)
                    if dist < 0.50 and kw > 0:
                        rag_refs.append((content, dist))
                if not rag_refs:
                    rag_refs = [(retrieved[0][0], retrieved[0][1])]  # 至少保留最佳匹配
                print(f"[RAG] 筛选出 {len(rag_refs)} 条参考资料注入 AI 上下文")

                if rag_refs:
                    # 将参考资料注入到用户消息中，让 AI 结合资料回答
                    ref_context = "以下是与用户问题可能相关的参考资料，请结合这些资料回答：\n\n"
                    for i, (content, dist) in enumerate(rag_refs[:5], 1):
                        clean = _clean_chunk(content)
                        ref_context += f"【参考资料{i}】\n{clean}\n\n"
                    ref_context += "---\n用户问题："

                    # 找到最后一条用户消息并注入参考资料
                    for i in range(len(messages) - 1, -1, -1):
                        if messages[i]['role'] == 'user':
                            messages[i]['content'] = ref_context + messages[i]['content']
                            break
        except Exception as e:
            print(f"[RAG]检索失败: {e}")
            rag_refs = []

    if model == "deepseek":
        response = call_deepseek_api(messages, tools=TOOLS)
    else:
        response = _ollama_chat_with_timeout(
            model='qwen2.5:14b',
            messages=messages,
            tools=TOOLS,
            options={"temperature": 0.1, "num_predict": 2048}
        )

    # 处理工具调用（通用逻辑）
    if response['message'].get('tool_calls'):
        tool_calls = response['message']['tool_calls']
        # 先把 assistant 的 tool_calls 消息加入历史
        messages.append({
            "role": response['message']['role'],
            "content": response['message']['content'],
            "tool_calls": [
                {
                    "id": tc.get("id", ""),
                    "type": "function",
                    "function": tc["function"]
                } for tc in tool_calls
            ]
        })
        for tool_call in tool_calls:
            tc_id = tool_call.get('id', '')
            if tool_call['function']['name'] == 'get_point_data':
                args = tool_call['function']['arguments']
                try:
                    if isinstance(args, str):
                        args = json.loads(args)
                    result = get_point_data(**args)
                    result_str = json.dumps(result, ensure_ascii=False)
                except Exception as e:
                    result_str = json.dumps({"success": False, "message": str(e)})
                messages.append({"role": "tool", "tool_call_id": tc_id, "content": result_str})
            else:
                messages.append({"role": "tool", "tool_call_id": tc_id, "content": "未知工具调用"})

        # 最终回复
        if model == "deepseek":
            final_response = call_deepseek_api(messages)
        else:
            final_response = _ollama_chat_with_timeout(
                model='qwen2.5:14b',
                messages=messages
            )
        answer = final_response['message']['content']
    else:
        answer = response['message']['content']


    # 追加参考资料
    if rag_refs:
        answer += "\n\n---\n📚 **参考资料：**\n"
        for i, (content, dist) in enumerate(rag_refs[:5], 1):
            excerpt = _clean_chunk(content)
            if len(excerpt) > 300:
                excerpt = excerpt[:300] + "..."
            answer += f"\n{i}. {excerpt}  _(相关度: {1-dist:.2f})_\n"

    return answer
