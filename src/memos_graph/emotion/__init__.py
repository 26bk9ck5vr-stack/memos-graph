"""memos-graph emotion module (v3.0).

Implements emotional state management:
- 6 basic emotions (simplified from 9)
- Arousal (0-1) for intensity
- Integration with System Prompt
- Integration with TTS markers
"""

from memos_graph.emotion.types import EmotionType, EmotionalState
from memos_graph.emotion.analyzer import EmotionAnalyzer

__all__ = [
    "EmotionType",
    "EmotionalState",
    "EmotionAnalyzer",
]
