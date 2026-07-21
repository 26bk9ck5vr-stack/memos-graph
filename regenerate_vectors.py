#!/usr/bin/env python3
"""重新生成所有 chunks 的向量嵌入"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from sqlalchemy import select, update, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from memos_graph.db.models import Chunk, ChunkVector
from memos_graph.embedding import EmbeddingService
from memos_graph.config import load_config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def regenerate_vectors():
    """重新生成所有向量的嵌入"""
    cfg = load_config()
    
    # 初始化 embedding 服务
    embedding_service = EmbeddingService(
        model=cfg.embedding.model,
        base_url=cfg.embedding.base_url,
        api_key=cfg.embedding.api_key,
        timeout=float(cfg.embedding.timeout_seconds),
    )
    
    # 连接数据库
    engine = create_async_engine(
        cfg.database.url,
        pool_size=cfg.database.pool_size,
        pool_recycle=cfg.database.pool_recycle
    )
    
    async with engine.connect() as conn:
        # 获取所有 chunks
        result = await conn.execute(
            select(Chunk.id, Chunk.content).where(Chunk.content.isnot(None))
        )
        chunks = result.fetchall()
        
        total = len(chunks)
        logger.info(f"开始重新生成 {total} 个 chunks 的向量...")
        
        success_count = 0
        error_count = 0
        
        for i, (chunk_id, content) in enumerate(chunks, 1):
            try:
                # 生成嵌入
                embedding = await embedding_service.embed(content)
                
                if not embedding or len(embedding) != 1024:
                    logger.warning(f"Chunk {chunk_id}: 嵌入维度错误 ({len(embedding) if embedding else 'None'})")
                    error_count += 1
                    continue
                
                # 检查是否有 NaN 或 Inf
                if any(not (-10 < v < 10) for v in embedding[:10]):  # 抽样检查
                    logger.warning(f"Chunk {chunk_id}: 嵌入值异常")
                    error_count += 1
                    continue
                
                # 更新或插入向量
                await conn.execute(
                    text("""
                        INSERT INTO chunk_vectors (chunk_id, embedding, model)
                        VALUES (:chunk_id, :embedding, :model)
                        ON CONFLICT (chunk_id) DO UPDATE SET
                            embedding = :embedding,
                            model = :model
                    """),
                    {
                        "chunk_id": chunk_id,
                        "embedding": f"[{','.join(str(v) for v in embedding)}]",
                        "model": cfg.embedding.model
                    }
                )
                
                success_count += 1
                
                if i % 100 == 0:
                    logger.info(f"进度：{i}/{total} ({i/total*100:.1f}%), 成功：{success_count}, 失败：{error_count}")
                    await conn.commit()  # 每 100 条提交一次
                
            except Exception as e:
                logger.error(f"Chunk {chunk_id} 失败：{e}")
                error_count += 1
        
        # 最终提交
        await conn.commit()
        
        logger.info(f"完成！成功：{success_count}, 失败：{error_count}")
        logger.info(f"成功率：{success_count/total*100:.1f}%")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(regenerate_vectors())
