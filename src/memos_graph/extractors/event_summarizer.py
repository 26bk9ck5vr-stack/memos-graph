"""混合事件总结器 - 模板 + 抽取式 + LLM Fallback"""

import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class HybridEventSummarizer:
    """
    混合事件总结器
    
    策略:
    1. 模板匹配 (60% 标准事件) - <5ms
    2. 抽取式总结 (30% 普通事件) - <50ms
    3. LLM (10% 复杂事件) - 1-2 秒 (Fallback)
    """
    
    # 事件模板
    TEMPLATES = [
        (r'用户 (要求 | 请求 | 请 | 想要)\s*(.+)', 'user_request'),
        (r'我 (答应 | 承诺 | 保证 | 一定)\s*(.+)', 'promise'),
        (r'(完成 | 做完 | 搞定 | 成功)\s*(.+)', 'task_completed'),
        (r'遇到 (问题 | 错误|bug|故障)\s*(.+)', 'issue_reported'),
        (r'发现 (了 | 一个 | 有个)\s*(.+)', 'discovery'),
        (r'建议\s*(.+)', 'suggestion'),
        (r'喜欢 | 讨厌 | 满意 | 失望\s*(.+)', 'feedback'),
    ]
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
    
    async def summarize(self, text: str) -> List[Dict]:
        """
        总结事件
        
        Returns:
            事件列表
        """
        # 阶段 1: 模板匹配
        for pattern, event_type in self.TEMPLATES:
            match = re.search(pattern, text)
            if match:
                content = match.group(2) if len(match.groups()) > 1 else match.group(0)
                return [{
                    'event_type': event_type,
                    'summary': match.group(0)[:200],
                    'content': content,
                    'confidence': 0.85,
                    'source': 'template'
                }]
        
        # 阶段 2: 抽取式总结 (取前 2 句)
        sentences = re.split(r'[.!?。！？]', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        
        if sentences:
            summary = '。'.join(sentences[:2]) + '。'
            return [{
                'event_type': 'general',
                'summary': summary[:200],
                'content': summary,
                'confidence': 0.7,
                'source': 'extractive'
            }]
        
        # 阶段 3: LLM Fallback
        if self.llm_client:
            try:
                data = await self.llm_client.summarize_event(text[:3000])
                return data if isinstance(data, list) else [data] if data else []
            except Exception as e:
                logger.warning(f"LLM event summarization failed: {e}")
        
        return []
