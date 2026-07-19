"""混合实体抽取器 - 规则 + NER + LLM Fallback"""

import re
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class HybridEntityExtractor:
    """
    混合实体抽取器
    
    策略:
    1. 规则匹配 (80% 简单文本) - <10ms
    2. NER 模型 (15% 中等文本) - <100ms
    3. LLM (5% 复杂文本) - 1-3 秒 (Fallback)
    """
    
    # 规则模式
    PATTERNS = {
        'person': [
            r'@(\w+)',  # @username
            r'用户 [：:]\s*(\w+)',
            r'(先生 | 女士 | 小姐 | 老师)[\s:：](\w+)',
        ],
        'organization': [
            r'(公司 | 团队 | 项目 | 部门)[：:]\s*(\w+)',
            r'([A-Za-z\u4e00-\u9fa5]+ 公司)',
            r'([A-Za-z\u4e00-\u9fa5]+ 团队)',
        ],
        'time': [
            r'(\d{4}年\d{1,2}月\d{1,2}日)',
            r'(\d{4}-\d{2}-\d{2})',
            r'(今天 | 明天 | 后天 | 下周 | 上月)',
        ],
        'location': [
            r'(在 | 到 | 从)[\s:：]*(\w+ 市 |\w+ 省 |\w+ 国家)',
            r'(北京 | 上海 | 广州 | 深圳 | 杭州)',
        ],
    }
    
    def __init__(self, llm_client=None, use_ner=True):
        self.llm_client = llm_client
        self.use_ner = use_ner
        self.nlp = None
        
        # 加载 NER 模型 (可选)
        if self.use_ner:
            try:
                import spacy
                self.nlp = spacy.load('zh_core_web_sm')
                logger.info("NER model loaded: zh_core_web_sm")
            except Exception as e:
                logger.warning(f"Failed to load NER model: {e}")
                self.use_ner = False
                self.nlp = None
    
    async def extract(self, text: str) -> Tuple[List[Dict], List[Dict]]:
        """
        抽取实体和关系
        
        Returns:
            (entities, relations)
        """
        # 阶段 1: 规则匹配
        entities = self._rule_extract(text)
        
        # 如果规则抽取到足够多的实体，直接返回
        if len(entities) >= 3:
            logger.debug(f"Rule-based extraction succeeded: {len(entities)} entities")
            return entities, []
        
        # 阶段 2: NER 模型 (如果启用)
        if self.use_ner and self.nlp:
            ner_entities = self._ner_extract(text)
            if ner_entities:
                entities.extend(ner_entities)
                logger.debug(f"NER extraction succeeded: {len(ner_entities)} entities")
                return entities, []
        
        # 阶段 3: LLM Fallback (仅 5% 复杂文本)
        if self.llm_client:
            try:
                llm_entities, relations = await self.llm_client.extract_entities(text[:3000])
                logger.debug(f"LLM extraction succeeded: {len(llm_entities)} entities")
                return llm_entities, relations
            except Exception as e:
                logger.warning(f"LLM extraction failed: {e}")
        
        return entities, []
    
    def _rule_extract(self, text: str) -> List[Dict]:
        """规则匹配"""
        entities = []
        
        for entity_type, patterns in self.PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text):
                    entities.append({
                        'name': match.group(0),
                        'type': entity_type,
                        'confidence': 0.9,
                        'source': 'rule'
                    })
        
        # 去重
        seen = set()
        deduped = []
        for e in entities:
            key = f"{e['type']}:{e['name']}"
            if key not in seen:
                seen.add(key)
                deduped.append(e)
        
        return deduped
    
    def _ner_extract(self, text: str) -> List[Dict]:
        """NER 模型抽取"""
        if not self.nlp:
            return []
        
        doc = self.nlp(text[:512])  # 截断避免过长
        entities = []
        
        type_map = {
            'PERSON': 'person',
            'ORG': 'organization',
            'GPE': 'location',
            'TIME': 'time',
            'DATE': 'time',
        }
        
        for ent in doc.ents:
            entity_type = type_map.get(ent.label_, 'concept')
            entities.append({
                'name': ent.text,
                'type': entity_type,
                'confidence': 0.85,
                'source': 'ner'
            })
        
        return entities
