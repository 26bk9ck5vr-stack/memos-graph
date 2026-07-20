"""查询分类器 - 智能路由查询到不同召回路径"""

import re
import logging
from typing import Literal

logger = logging.getLogger(__name__)

QueryType = Literal['simple', 'medium', 'complex']

class QueryClassifier:
    """
    查询分类器
    
    将查询分为三类:
    - simple: 短查询，无空格，纯关键词 (<10 字符)
    - medium: 中等长度，有空格，简单语义 (10-30 字符)
    - complex: 长查询，复杂语义，多条件 (>30 字符)
    """
    
    # 简单查询关键词 (直接返回，无需重排)
    SIMPLE_KEYWORDS = [
        '安装', '配置', '部署', '使用', '怎么', '如何',
        '什么', '哪里', '何时', '谁', '为什么',
        'install', 'setup', 'config', 'how', 'what',
    ]
    
    # 复杂查询标识 (需要完整召回路径)
    COMPLEX_INDICATORS = [
        '并且', '或者', '但是', '如果', '虽然',
        '比较', '对比', '分析', '总结', '评价',
        'and', 'or', 'but', 'if', 'compare',
        '?', '？',  # 问句
    ]
    
    def classify(self, query: str) -> QueryType:
        """
        分类查询
        
        Args:
            query: 用户查询
            
        Returns:
            'simple' | 'medium' | 'complex'
        """
        query = query.strip()
        length = len(query)
        
        # 规则 1: 极短查询 (<5 字符)
        if length < 5:
            return 'simple'
        
        # 规则 2: 超长查询 (>30 字符)
        if length > 30:
            return 'complex'
        
        # 规则 3: 复杂指示词优先判断
        has_complex_indicator = any(ind in query for ind in self.COMPLEX_INDICATORS)
        if has_complex_indicator:
            return 'complex'
        
        # 规则 4: 空格判断 (英文查询)
        has_space = ' ' in query
        if length < 10 and not has_space:
            return 'simple'
        
        # 规则 5: 简单关键词判断
        has_simple_keyword = any(kw in query for kw in self.SIMPLE_KEYWORDS)
        if has_simple_keyword and length < 15:
            return 'simple'
        
        # 默认：中等查询
        return 'medium'
    
    def get_strategy(self, query_type: QueryType) -> dict:
        """
        根据查询类型获取召回策略
        
        Returns:
            策略配置字典
        """
        strategies = {
            'simple': {
                'use_fts': True,
                'use_pattern': True,
                'use_time': False,
                'use_llm_rerank': False,
                'use_cache': True,
                'top_k': 5,
                'description': '快速路径 - FTS + Pattern only'
            },
            'medium': {
                'use_fts': True,
                'use_pattern': True,
                'use_time': True,
                'use_llm_rerank': True,  # Cross-Encoder
                'use_cache': True,
                'top_k': 10,
                'description': '标准路径 - FTS + Pattern + Time + Cross-Encoder'
            },
            'complex': {
                'use_fts': True,
                'use_pattern': True,
                'use_time': True,
                'use_llm_rerank': True,  # Cross-Encoder
                'use_cache': False,  # 复杂查询不缓存
                'top_k': 20,
                'description': '完整路径 - 全量召回 + Cross-Encoder'
            }
        }
        
        return strategies.get(query_type, strategies['medium'])
