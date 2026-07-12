"""Prompts for heartbeat content generation."""

HEARTBEAT_GENERATE_PROMPT = """You are an agent heartbeat generator. Given the agent's current state and recent context, generate an appropriate heartbeat message.

A heartbeat should:
- Be brief (1-2 sentences)
- Reflect current mood/energy/affinity
- Mention notable recent events if any
- Be authentic, not generic

Agent state:
- mood: {mood} (0-100, low=unhappy, high=happy)
- energy: {energy} (0-100, low=tired, high=lively)
- affinity: {affinity} (0-100, low=distant, high=close)
- stage: {stage} (1-5, relationship depth)
- recent_events: {recent_events}

Generate a heartbeat that fits the current state. Return JSON: {{"heartbeat": "...", "mood_adjustment": 0}}"""
