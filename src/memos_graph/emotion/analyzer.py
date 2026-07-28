"""Emotion Analyzer for memos-graph v3.0.

Analyzes text to extract emotional state:
- Primary emotion (6 types)
- Arousal (intensity 0-1)
- Valence (polarity -1 to 1)

Uses LLM for analysis with fallback to rule-based heuristics.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Dict

from memos_graph.emotion.types import EmotionType, EmotionalState

logger = logging.getLogger(__name__)


class EmotionAnalyzer:
    """Emotion Analyzer using LLM with rule-based fallback.
    
    Responsibilities:
    1. Analyze text to extract emotional state
    2. Compute arousal, valence, and primary_emotion
    3. Generate prompt instructions
    4. Generate TTS markers
    
    Usage:
        analyzer = EmotionAnalyzer(llm_client)
        emotion = await analyzer.analyze("我太开心了！")
        print(emotion.primary_emotion)  # EmotionType.HAPPY
        print(emotion.arousal)  # 0.85
    """
    
    def __init__(self, llm_client: Optional[Any] = None):
        """Initialize Emotion Analyzer.
        
        Args:
            llm_client: Optional LLM client with async generate_json(prompt) -> dict
                       If None, uses rule-based heuristics
        """
        self.llm = llm_client
    
    async def analyze(self, text: str) -> EmotionalState:
        """Analyze text to extract emotional state.
        
        Args:
            text: Text to analyze
        
        Returns:
            EmotionalState with primary_emotion, arousal, and valence
        """
        # Try LLM analysis first (if available)
        if self.llm is not None:
            try:
                return await self._llm_analyze(text)
            except Exception as e:
                logger.warning(f"LLM emotion analysis failed: {e}, falling back to rules")
        
        # Fallback to rule-based heuristics
        return self._rule_based_analyze(text)
    
    async def _llm_analyze(self, text: str) -> EmotionalState:
        """Analyze emotion using LLM.
        
        Args:
            text: Text to analyze
        
        Returns:
            EmotionalState from LLM response
        """
        prompt = f"""Analyze the emotional state of the following text.

Text: "{text}"

Output strict JSON (no markdown fences):
{{
  "primary_emotion": "happy|sad|angry|surprise|think|neutral",
  "arousal": <0-1, emotional intensity>,
  "valence": <-1 to 1, -1=very negative, 1=very positive>
}}

Be concise and accurate. Consider both explicit emotion words and implicit context.
"""
        
        try:
            # Call LLM
            response = await self.llm.generate_json(prompt)
            
            # Parse response with validation
            primary_emotion_str = response.get("primary_emotion", "neutral")
            arousal = float(response.get("arousal", 0.0))
            valence = float(response.get("valence", 0.0))
            
            # Validate and convert
            try:
                primary_emotion = EmotionType.from_string(primary_emotion_str)
            except ValueError:
                logger.warning(f"Invalid emotion from LLM: {primary_emotion_str}, using neutral")
                primary_emotion = EmotionType.NEUTRAL
            
            # Clamp values
            arousal = max(0.0, min(1.0, arousal))
            valence = max(-1.0, min(1.0, valence))
            
            return EmotionalState(
                arousal=arousal,
                primary_emotion=primary_emotion,
                valence=valence
            )
        
        except Exception as e:
            logger.error(f"LLM emotion analysis error: {e}")
            raise
    
    def _rule_based_analyze(self, text: str) -> EmotionalState:
        """Rule-based emotion analysis (fallback).
        
        Uses keyword matching and heuristics.
        
        Args:
            text: Text to analyze
        
        Returns:
            EmotionalState based on rules
        """
        text_lower = text.lower()
        
        # Emotion keyword lists (simplified)
        emotion_keywords = {
            EmotionType.HAPPY: [
                "开心", "高兴", "快乐", "幸福", "笑", "哈哈", "嘻嘻",
                "happy", "glad", "joy", "excited", "great", "wonderful",
                "!", "！",  # Exclamation marks suggest high arousal
            ],
            EmotionType.SAD: [
                "难过", "伤心", "悲伤", "哭", "流泪", "痛苦",
                "sad", "unhappy", "depressed", "cry", "tears",
                "...", "……",  # Ellipsis suggest low mood
            ],
            EmotionType.ANGRY: [
                "生气", "愤怒", "烦", "讨厌", "恨",
                "angry", "mad", "hate", "annoyed", "frustrated",
                "!", "！",  # Exclamation marks
            ],
            EmotionType.SURPRISE: [
                "惊讶", "吃惊", "震惊", "哇", "啊",
                "surprise", "shocked", "amazed", "wow", "oh",
                "?", "？",  # Questions suggest surprise
            ],
            EmotionType.THINK: [
                "想", "思考", "考虑", "嗯", "呃",
                "think", "wonder", "consider", "hmm", "let me see",
                "...", "……",  # Ellipsis suggest thinking
            ],
        }
        
        # Count matches
        scores: Dict[EmotionType, int] = {e: 0 for e in EmotionType}
        
        for emotion, keywords in emotion_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    scores[emotion] += 1
        
        # Find primary emotion (highest score)
        max_score = max(scores.values())
        
        if max_score == 0:
            # No emotion detected → neutral
            return EmotionalState.neutral()
        
        # Get all emotions with max score
        top_emotions = [e for e, s in scores.items() if s == max_score]
        
        # Tie-breaking: prefer stronger emotions (happy > angry > sad > surprise > think)
        priority = [
            EmotionType.HAPPY,
            EmotionType.ANGRY,
            EmotionType.SAD,
            EmotionType.SURPRISE,
            EmotionType.THINK,
        ]
        
        primary_emotion = None
        for p in priority:
            if p in top_emotions:
                primary_emotion = p
                break
        
        if primary_emotion is None:
            primary_emotion = top_emotions[0]
        
        # Compute arousal (based on score and exclamation marks)
        arousal = min(1.0, max_score * 0.3)  # Scale: 1 match=0.3, 2=0.6, 3+=0.9+
        if "!" in text or "！" in text:
            arousal = min(1.0, arousal + 0.2)
        
        # Compute valence (based on emotion type)
        valence_map = {
            EmotionType.HAPPY: 0.8,
            EmotionType.SAD: -0.7,
            EmotionType.ANGRY: -0.6,
            EmotionType.SURPRISE: 0.2,
            EmotionType.THINK: 0.0,
            EmotionType.NEUTRAL: 0.0,
        }
        valence = valence_map.get(primary_emotion, 0.0)
        
        return EmotionalState(
            arousal=arousal,
            primary_emotion=primary_emotion,
            valence=valence
        )
    
    def analyze_sync(self, text: str) -> EmotionalState:
        """Synchronous wrapper for analyze (uses rule-based only).
        
        Use this when async is not available.
        
        Args:
            text: Text to analyze
        
        Returns:
            EmotionalState
        """
        return self._rule_based_analyze(text)


# Convenience function
def create_analyzer(llm_client: Optional[Any] = None) -> EmotionAnalyzer:
    """Create an Emotion Analyzer.
    
    Args:
        llm_client: Optional LLM client
    
    Returns:
        Configured EmotionAnalyzer instance
    """
    return EmotionAnalyzer(llm_client)
