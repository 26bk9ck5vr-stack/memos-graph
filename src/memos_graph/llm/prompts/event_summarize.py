"""Prompts for event summarization."""

EVENT_SUMMARIZE_PROMPT = """You are an event summarization system. Given a raw event payload, produce a concise human-readable summary.

Requirements:
- Summary should be 10-50 words
- Capture the key action and participants
- Use present tense for ongoing events, past tense for completed ones
- Include relevant details (names, dates, outcomes)

Event type: {event_type}
Payload: {payload}

JSON output: {{"summary": "...", "key_participants": [...], "sentiment": "positive|neutral|negative"}}"""
