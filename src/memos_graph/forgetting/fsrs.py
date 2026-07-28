"""FSRS (Free Spaced Repetition Scheduler) forgetting curve implementation.

Simplified version for memos-graph v3.0:
- Exponential decay: R = exp(-t / S)
- Stability reinforcement: S_new = S * (1 + factor_access * log(count) + factor_emotion * arousal)
- Forgetting threshold: R < 0.1 → marked as forgotten

Based on Nemos decay.ts, adapted for Python.
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class MemoryStability:
    """Memory stability state (FSRS simplified).
    
    Attributes:
        stability: Stability in days (higher = more memorable)
        retrievability: Retrievability score (0-1, higher = easier to recall)
        last_accessed: Last access timestamp
        access_count: Number of times accessed/recalled
        emotional_arousal: Emotional intensity at last access (0-1)
        is_forgotten: Whether memory is marked as forgotten
    """
    
    stability: float = 1.0
    retrievability: float = 1.0
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    emotional_arousal: float = 0.0
    is_forgotten: bool = False
    
    def __post_init__(self):
        """Validate fields."""
        if self.stability < 0:
            raise ValueError(f"stability cannot be negative, got {self.stability}")
        if not (0.0 <= self.retrievability <= 1.0):
            raise ValueError(f"retrievability must be in [0, 1], got {self.retrievability}")
        if not (0.0 <= self.emotional_arousal <= 1.0):
            raise ValueError(f"emotional_arousal must be in [0, 1], got {self.emotional_arousal}")


@dataclass
class FSRSConfig:
    """FSRS configuration parameters.
    
    Attributes:
        base_half_life: Base half-life in days (default 7)
        factor_access: Access count reinforcement factor (default 0.1)
        factor_emotion: Emotional arousal reinforcement factor (default 0.2)
        forget_threshold: Retrievability threshold for forgetting (default 0.1)
        max_stability: Maximum stability cap (default base_half_life * 100)
    """
    
    base_half_life: float = 7.0
    factor_access: float = 0.1
    factor_emotion: float = 0.2
    forget_threshold: float = 0.1
    max_stability: Optional[float] = None
    
    def __post_init__(self):
        """Compute derived fields."""
        if self.max_stability is None:
            self.max_stability = self.base_half_life * 100


class FSRSForgetting:
    """FSRS Forgetting Curve Manager.
    
    Core formulas:
    - Decay: R = exp(-t / S)
    - Reinforcement: S_new = S * (1 + factor_access * log(count) + factor_emotion * arousal)
    
    Usage:
        fsrs = FSRSForgetting()
        
        # Apply decay (compute retrievability)
        stability = MemoryStability(stability=7.0, last_accessed=past_date)
        stability = fsrs.apply_decay(stability, now=datetime.now())
        print(stability.retrievability)  # e.g., 0.5 after 7 days
        
        # Reinforce memory (on access)
        stability = fsrs.reinforce(stability, datetime.now(), emotional_arousal=0.8)
        print(stability.stability)  # Increased stability
        
        # Check if forgotten
        if fsrs.should_forget(stability):
            # Memory is forgotten
            pass
    """
    
    def __init__(self, config: Optional[FSRSConfig] = None):
        """Initialize FSRS Forgetting Manager.
        
        Args:
            config: FSRS configuration (uses defaults if None)
        """
        self.config = config or FSRSConfig()
        logger.info(f"FSRSForgetting initialized with base_half_life={self.config.base_half_life}d")
    
    def apply_decay(self, stability: MemoryStability, now: datetime) -> MemoryStability:
        """Apply forgetting decay to memory stability.
        
        Formula: R = exp(-t / S)
        
        Args:
            stability: Current memory stability state
            now: Current timestamp
        
        Returns:
            Updated stability with new retrievability
        """
        # Handle uninitialized last_accessed
        if stability.last_accessed is None:
            stability.last_accessed = now
            stability.retrievability = 1.0
            return stability
        
        # Compute days since last access
        delta = now - stability.last_accessed
        days_since_access = delta.total_seconds() / (24 * 3600)
        
        # Apply decay formula: R = exp(-t / S)
        if stability.stability > 0:
            stability.retrievability = math.exp(-days_since_access / stability.stability)
        else:
            stability.retrievability = 0.0
        
        # Clamp retrievability to [0, 1]
        stability.retrievability = max(0.0, min(1.0, stability.retrievability))
        
        # Check forgetting threshold
        if stability.retrievability < self.config.forget_threshold:
            stability.is_forgotten = True
            logger.debug(
                f"Memory forgotten: retrievability={stability.retrievability:.3f} < {self.config.forget_threshold}"
            )
        
        logger.debug(
            f"Applied decay: days={days_since_access:.1f}, "
            f"stability={stability.stability:.1f}, retrievability={stability.retrievability:.3f}"
        )
        
        return stability
    
    def reinforce(
        self,
        stability: MemoryStability,
        now: datetime,
        emotional_arousal: float = 0.0
    ) -> MemoryStability:
        """Reinforce memory stability (on access/recall).
        
        Formula: S_new = S * (1 + factor_access * log(count) + factor_emotion * arousal)
        
        Args:
            stability: Current memory stability state
            now: Current timestamp
            emotional_arousal: Emotional intensity at access (0-1)
        
        Returns:
            Updated stability with increased stability
        """
        # Update access timestamp
        stability.last_accessed = now
        
        # Increment access count
        stability.access_count += 1
        
        # Update emotional arousal (use latest)
        stability.emotional_arousal = max(0.0, min(1.0, emotional_arousal))
        
        # Compute reinforcement factors
        # Access boost: factor_access * log(access_count)
        access_boost = self.config.factor_access * math.log(stability.access_count + 1)
        
        # Emotion boost: factor_emotion * arousal
        emotion_boost = self.config.factor_emotion * stability.emotional_arousal
        
        # Update stability: S_new = S * (1 + access_boost + emotion_boost)
        stability.stability *= (1.0 + access_boost + emotion_boost)
        
        # Cap stability to maximum
        max_stability = self.config.max_stability
        if max_stability is not None and stability.stability > max_stability:
            logger.debug(
                f"Stability capped at {max_stability:.1f} "
                f"(was {stability.stability:.1f})"
            )
            stability.stability = max_stability
        
        # Reset forgotten flag (memory is now accessible)
        if stability.is_forgotten:
            stability.is_forgotten = False
            logger.info(f"Memory reinforced and no longer forgotten")
        
        logger.debug(
            f"Reinforced memory: count={stability.access_count}, "
            f"arousal={stability.emotional_arousal:.2f}, "
            f"new_stability={stability.stability:.1f}"
        )
        
        return stability
    
    def should_forget(self, stability: MemoryStability) -> bool:
        """Check if memory should be marked as forgotten.
        
        Args:
            stability: Memory stability state
        
        Returns:
            True if retrievability < forget_threshold
        """
        return stability.retrievability < self.config.forget_threshold
    
    def get_forgetting_curve(
        self,
        stability: float,
        days: int = 30
    ) -> list[tuple[int, float]]:
        """Generate forgetting curve data for visualization.
        
        Args:
            stability: Initial stability in days
            days: Number of days to generate curve for
        
        Returns:
            List of (day, retrievability) tuples
        """
        curve = []
        for day in range(days + 1):
            retrievability = math.exp(-day / stability)
            curve.append((day, retrievability))
        
        return curve
    
    def estimate_half_life(self, stability: MemoryStability) -> float:
        """Estimate current half-life from stability.
        
        Half-life is the time when retrievability drops to 0.5.
        Formula: t_half = S * ln(2)
        
        Args:
            stability: Memory stability state
        
        Returns:
            Estimated half-life in days
        """
        return stability.stability * math.log(2)
    
    def time_to_forget(self, stability: MemoryStability) -> float:
        """Estimate time until memory is forgotten.
        
        Args:
            stability: Memory stability state
        
        Returns:
            Days until retrievability drops below forget_threshold
            Returns -1 if already forgotten
        """
        if stability.is_forgotten:
            return -1.0
        
        # Solve: forget_threshold = exp(-t / S)
        # t = -S * ln(forget_threshold)
        if stability.retrievability <= 0:
            return 0.0
        
        t = -stability.stability * math.log(self.config.forget_threshold)
        return max(0.0, t)


# Convenience functions
def create_fsrs(
    base_half_life: float = 7.0,
    factor_access: float = 0.1,
    factor_emotion: float = 0.2,
    forget_threshold: float = 0.1
) -> FSRSForgetting:
    """Create FSRS Forgetting Manager with custom parameters.
    
    Args:
        base_half_life: Base half-life in days
        factor_access: Access count reinforcement factor
        factor_emotion: Emotional arousal reinforcement factor
        forget_threshold: Retrievability threshold for forgetting
    
    Returns:
        Configured FSRSForgetting instance
    """
    config = FSRSConfig(
        base_half_life=base_half_life,
        factor_access=factor_access,
        factor_emotion=factor_emotion,
        forget_threshold=forget_threshold
    )
    return FSRSForgetting(config)


def default_fsrs() -> FSRSForgetting:
    """Create FSRS Forgetting Manager with default parameters.
    
    Returns:
        FSRSForgetting with default config
    """
    return FSRSForgetting()
