"""Event summarization prompt."""

EVENT_SUMMARIZE_PROMPT = """You are an event summarizer for AI agent memory.

Summarize the given conversation turn into a structured event.

Output JSON in this format:
{
  "event_type": "message|task_completed|mood_change|promise_made|promise_fulfilled|learning",
  "summary": "One sentence summary",
  "actor": "user|agent|system",
  "payload": {
    "key_points": ["point1", "point2"],
    "emotions": ["happy", "curious"],
    "topics": ["topic1", "topic2"]
  }
}

Rules:
- Be concise but capture the essence
- Identify the main actor (who initiated)
- Detect emotions and topics when present

Text:
"""
