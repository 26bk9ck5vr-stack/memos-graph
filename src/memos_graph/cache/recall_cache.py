"""缓存层 - 两级缓存 (lru_cache + Redis)"""

import json
import logging
from functools import lru_cache
from typing import Any, Optional, List, Dict
import time

logger = logging.getLogger(__name__)

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not installed, using lru_cache only")

class RecallCache:
    """
    两级缓存
    
    L1: lru_cache (内存，<1ms)
    L2: Redis (网络，<10ms)
    """
    
    def __init__(self, redis_host: str = 'localhost', redis_port: int = 6379, redis_db: int = 0):
        self.redis = None
        self.redis_available = False
        
        if REDIS_AVAILABLE:
            try:
                self.redis = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2
                )
                # 测试连接
                self.redis.ping()
                self.redis_available = True
                logger.info(f"Redis connected: {redis_host}:{redis_port}")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}, using lru_cache only")
                self.redis = None
        
        # L1 缓存：lru_cache (最多 1000 条)
        self._cache = lru_cache(maxsize=1000)(self._get_cached)
        
        # 统计
        self.hits = 0
        self.misses = 0
    
    def _get_cached(self, key: str) -> Optional[Any]:
        """内部获取方法 (被 lru_cache 装饰)"""
        if self.redis and self.redis_available:
            try:
                data = self.redis.get(key)
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.warning(f"Redis get error: {e}")
        return None
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值或 None
        """
        result = self._cache(key)
        
        if result is not None:
            self.hits += 1
            logger.debug(f"Cache hit: {key}")
        else:
            self.misses += 1
            logger.debug(f"Cache miss: {key}")
        
        return result
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """
        设置缓存
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间 (秒), 默认 1 小时
            
        Returns:
            是否成功
        """
        try:
            # 更新 L1 缓存
            self._cache = lru_cache(maxsize=1000)(lambda k: self._get_from_redis(k))
            
            # 设置 L2 缓存
            if self.redis and self.redis_available:
                data = json.dumps(value, ensure_ascii=False)
                self.redis.setex(key, ttl, data)
                logger.debug(f"Cache set: {key} (TTL: {ttl}s)")
                return True
        except Exception as e:
            logger.warning(f"Cache set error: {e}")
        
        return False
    
    def _get_from_redis(self, key: str) -> Optional[Any]:
        """从 Redis 获取 (用于刷新 L1 缓存)"""
        if self.redis and self.redis_available:
            try:
                data = self.redis.get(key)
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.warning(f"Redis get error: {e}")
        return None
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            if self.redis and self.redis_available:
                self.redis.delete(key)
                logger.debug(f"Cache delete: {key}")
                return True
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")
        return False
    
    def clear(self) -> bool:
        """清空所有缓存"""
        try:
            if self.redis and self.redis_available:
                self.redis.flushdb()
                logger.info("Cache cleared")
                return True
        except Exception as e:
            logger.warning(f"Cache clear error: {e}")
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f"{hit_rate:.2f}%",
            'redis_available': self.redis_available,
            'l1_size': 1000  # lru_cache maxsize
        }

# 全局缓存实例
_cache_instance: Optional[RecallCache] = None

def get_cache() -> RecallCache:
    """获取全局缓存实例"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RecallCache()
    return _cache_instance

def generate_cache_key(agent_id: str, query: str, top_k: int) -> str:
    """生成缓存键"""
    import hashlib
    key_str = f"{agent_id}:{query}:{top_k}"
    key_hash = hashlib.md5(key_str.encode()).hexdigest()
    return f"recall:{key_hash}"
