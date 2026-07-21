"""实时写入 API - 用于 Hermes Gateway 直接调用"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from typing import List, Optional
import logging
from sqlalchemy import func

from memos_graph.db.session import get_session
from memos_graph.db.models import Chunk, Event, ChunkVector, Entity, ChunkEntity
from memos_graph.embedding import EmbeddingService
from memos_graph.config import load_config

logger = logging.getLogger(__name__)

router = APIRouter()


class SyncRequest:
    """同步请求数据"""
    def __init__(
        self,
        session_id: str,
        messages: List[dict],
        agent_id: str = "hermes"
    ):
        self.session_id = session_id
        self.messages = messages
        self.agent_id = agent_id


@router.post("/sync/realtime")
async def realtime_sync(
    request: dict,
    session: AsyncSession = Depends(get_session),
):
    """
    实时同步 Hermes 对话数据
    
    由 Hermes Gateway 在保存对话时直接调用，实现实时索引
    
    请求格式:
    {
        "session_id": "20260720_123456_abc123",
        "agent_id": "hermes",
        "messages": [
            {
                "role": "user",  # user | assistant | tool
                "content": "消息内容",
                "timestamp": "2026-07-20T12:34:56.789Z"
            }
        ]
    }
    
    响应:
    {
        "success": true,
        "synced_count": 3,
        "message": "Successfully synced 3 messages"
    }
    """
    start_time = datetime.utcnow()
    
    try:
        # 解析请求
        session_id = request.get("session_id")
        agent_id = request.get("agent_id", "hermes")
        messages = request.get("messages", [])
        
        if not session_id or not messages:
            raise HTTPException(status_code=400, detail="session_id and messages are required")
        
        # 加载 embedding 服务
        cfg = load_config()
        embedding_service = EmbeddingService(
            model=cfg.embedding.model,
            base_url=cfg.embedding.base_url,
            api_key=cfg.embedding.api_key,
        )
        
        synced_count = 0
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            timestamp_str = msg.get("timestamp")
            
            if not content:
                continue
            
            # 解析时间戳
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                # 转换为无时区 (数据库使用 TIMESTAMP WITHOUT TIME ZONE)
                timestamp = timestamp.replace(tzinfo=None)
            except:
                timestamp = datetime.utcnow()
            
            # 创建 Chunk
            chunk = Chunk(
                agent_id=agent_id,
                content=content,
                role=role,
                scope="private",
                created_at=timestamp,
                metadata={
                    "source": "realtime_sync",
                    "session_id": session_id
                },
                tsvector=func.to_tsvector('simple', content)  # 生成 FTS 向量
            )
            session.add(chunk)
            await session.flush()  # 获取 chunk.id
            
            # P1 优化：异步向量生成 (先返回，后台生成)
            # 策略：写入时不等待向量生成，后台任务异步生成
            # 优势：写入延迟降低 ~40%
            # 风险：短暂时间内 (秒级) 无法向量召回，但 FTS 仍可用
            async def generate_embedding_async():
                """后台异步生成向量嵌入"""
                try:
                    from memos_graph.db.database import AsyncSessionLocal
                    from memos_graph.db.models import ChunkVector
                    from memos_graph.embedding import EmbeddingService
                    from memos_graph.config import Settings
                    
                    cfg = Settings()
                    embedding_service = EmbeddingService(
                        provider=cfg.embedding.provider,
                        model=cfg.embedding.model,
                        base_url=cfg.embedding.base_url,
                        api_key=cfg.embedding.api_key,
                        dimension=cfg.embedding.dimension,
                        timeout=cfg.embedding.timeout_seconds,
                    )
                    
                    async with AsyncSessionLocal() as bg_session:
                        embedding = await embedding_service.embed(content)
                        # 确保向量是 list[float] 格式
                        if hasattr(embedding, 'tolist'):
                            embedding = embedding.tolist()
                        elif isinstance(embedding, dict):
                            embedding = embedding.get('embedding', [0.0] * 1024)
                        
                        chunk_vector = ChunkVector(
                            chunk_id=chunk.id,
                            embedding=embedding,
                            model=cfg.embedding.model
                        )
                        bg_session.add(chunk_vector)
                        await bg_session.commit()
                        logger.info(f"✅ 异步向量生成成功 (chunk_id={chunk.id})")
                except Exception as e:
                    logger.error(f"❌ 异步向量生成失败：{e}")
            
            # 启动后台任务 (不等待)
            import asyncio
            asyncio.create_task(generate_embedding_async())
            
            # 创建 Event
            event_type = f"message_{role}"
            event = Event(
                agent_id=agent_id,
                event_type=event_type,
                actor=role,
                summary=content[:200],  # 截取前 200 字作为摘要
                payload={
                    "session_id": session_id,
                    "role": role,
                    "timestamp": timestamp.isoformat()
                },
                created_at=timestamp
            )
            session.add(event)
            
            synced_count += 1
        
        # 提交事务
        await session.commit()
        
        elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        logger.info(f"Realtime sync completed: {synced_count} messages in {elapsed_ms:.2f}ms")
        
        return {
            "success": True,
            "synced_count": synced_count,
            "elapsed_ms": elapsed_ms,
            "message": f"Successfully synced {synced_count} messages"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Realtime sync failed: {e}")
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


@router.get("/sync/stats")
async def sync_stats(session: AsyncSession = Depends(get_session)):
    """
    获取同步统计信息
    """
    from sqlalchemy import func, select
    
    # 总 chunk 数
    result = await session.execute(select(func.count(Chunk.id)))
    total_chunks = result.scalar()
    
    # 今天的 chunk 数
    today = datetime.now().date()
    result = await session.execute(
        select(func.count(Chunk.id)).where(func.date(Chunk.created_at) == today)
    )
    today_chunks = result.scalar()
    
    # 最后更新时间
    result = await session.execute(select(func.max(Chunk.created_at)))
    last_update = result.scalar()
    
    return {
        "total_chunks": total_chunks or 0,
        "today_chunks": today_chunks or 0,
        "last_update": last_update.isoformat() if last_update else None,
        "sync_mode": "realtime"
    }
