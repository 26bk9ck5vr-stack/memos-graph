"""Emotion types and data structures for memos-graph v3.0.

Simplified from AIRI's 9 emotions to 6 basic emotions:
- happy: Joy, excitement, satisfaction
- sad: Sadness, disappointment, grief
- angry: Anger, frustration, annoyance
- surprise: Surprise, shock, amazement
- think: Thinking, curiosity, contemplation
- neutral: No strong emotion

Each emotion has:
- arousal: Intensity (0-1)
- primary_emotion: One of the 6 basic emotions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional
from enum import Enum


class EmotionType(str, Enum):
    """6 basic emotion types (simplified from AIRI's 9)."""
    
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    SURPRISE = "surprise"
    THINK = "think"
    NEUTRAL = "neutral"
    
    @classmethod
    def from_string(cls, value: str) -> EmotionType:
        """Create EmotionType from string (case-insensitive).
        
        Args:
            value: String value (e.g., "Happy", "HAPPY", "happy")
        
        Returns:
            Corresponding EmotionType
        
        Raises:
            ValueError: If value is not a valid emotion
        """
        value_lower = value.lower().strip()
        
        # Map common variations
        mapping = {
            "joy": cls.HAPPY,
            "excited": cls.HAPPY,
            "glad": cls.HAPPY,
            "sadness": cls.SAD,
            "unhappy": cls.SAD,
            "depressed": cls.SAD,
            "anger": cls.ANGRY,
            "mad": cls.ANGRY,
            "frustrated": cls.ANGRY,
            "surprised": cls.SURPRISE,
            "shocked": cls.SURPRISE,
            "amazed": cls.SURPRISE,
            "thinking": cls.THINK,
            "curious": cls.THINK,
            "contemplative": cls.THINK,
            "neutral": cls.NEUTRAL,
            "none": cls.NEUTRAL,
        }
        
        if value_lower in mapping:
            return mapping[value_lower]
        
        # Try direct match
        for emotion in cls:
            if emotion.value == value_lower:
                return emotion
        
        raise ValueError(f"Invalid emotion: {value}. Valid: {[e.value for e in cls]}")


@dataclass
class EmotionalState:
    """Emotional state (simplified: arousal + primary_emotion).
    
    Attributes:
        arousal: Emotional intensity (0-1, 0=neutral, 1=very intense)
        primary_emotion: Primary emotion type
        valence: Emotional polarity (-1 to 1, -1=negative, 1=positive)
            Optional, computed from primary_emotion if not provided
    """
    
    arousal: float = 0.0
    primary_emotion: EmotionType = EmotionType.NEUTRAL
    valence: Optional[float] = None
    
    def __post_init__(self):
        """Validate and compute derived fields."""
        # Validate arousal
        if not (0.0 <= self.arousal <= 1.0):
            raise ValueError(f"arousal must be in [0, 1], got {self.arousal}")
        
        # Compute valence if not provided
        if self.valence is None:
            self.valence = self._default_valence()
        
        # Validate valence
        if not (-1.0 <= self.valence <= 1.0):
            raise ValueError(f"valence must be in [-1, 1], got {self.valence}")
    
    def _default_valence(self) -> float:
        """Compute default valence from primary_emotion."""
        valence_map = {
            EmotionType.HAPPY: 0.8,
            EmotionType.SAD: -0.7,
            EmotionType.ANGRY: -0.6,
            EmotionType.SURPRISE: 0.2,  # Can be positive or negative
            EmotionType.THINK: 0.0,
            EmotionType.NEUTRAL: 0.0,
        }
        return valence_map.get(self.primary_emotion, 0.0)
    
    def to_prompt_instruction(self) -> str:
        """Generate prompt instruction for this emotional state.
        
        Returns:
            String instruction for LLM (e.g., "[当前情感：happy, 强度：0.85]")
        """
        if self.arousal < 0.3:
            return ""  # Too low arousal, no emotion to express
        
        return f"[当前情感：{self.primary_emotion.value}, 强度：{self.arousal:.2f}]"
    
    def to_tts_marker(self) -> str:
        """Generate TTS special marker for this emotional state.
        
        Returns:
            TTS marker string (e.g., "[EMOTION:happy:0.85]")
            Empty string if arousal is too low
        """
        if self.arousal < 0.3:
            return ""  # Too low arousal, no emotion marker
        
        return f"[EMOTION:{self.primary_emotion.value}:{self.arousal:.2f}]"
    
    def is_neutral(self) -> bool:
        """Check if this is a neutral emotional state."""
        return (
            self.primary_emotion == EmotionType.NEUTRAL or
            self.arousal < 0.2
        )
    
    @classmethod
    def neutral(cls) -> EmotionalState:
        """Create a neutral emotional state."""
        return cls(arousal=0.0, primary_emotion=EmotionType.NEUTRAL, valence=0.0)
    
    @classmethod
    def happy(cls, arousal: float = 0.8) -> EmotionalState:
        """Create a happy emotional state."""
        return cls(arousal=arousal, primary_emotion=EmotionType.HAPPY, valence=0.8)
    
    @classmethod
    def sad(cls, arousal: float = 0.6) -> EmotionalState:
        """Create a sad emotional state."""
        return cls(arousal=arousal, primary_emotion=EmotionType.SAD, valence=-0.7)
    
    @classmethod
    def angry(cls, arousal: float = 0.7) -> EmotionalState:
        """Create an angry emotional state."""
        return cls(arousal=arousal, primary_emotion=EmotionType.ANGRY, valence=-0.6)


# Convenience constants
NEUTRAL_EMOTION = EmotionalState.neutral()
HAPPY_EMOTION = EmotionalState.happy()
SAD_EMOTION = EmotionalState.sad()
ANGRY_EMOTION = EmotionalState.angry()
