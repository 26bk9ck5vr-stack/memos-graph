"""Promise extraction prompt."""

PROMISE_EXTRACT_PROMPT = """You are a promise extractor for AI agent memory.

Detect any promises, commitments, or intentions in the given text.

Output JSON in this format:
{
  "promises": [
    {
      "content": "What was promised",
      "promiser": "Who promised",
      "beneficiary": "To whom",
      "due_at": "YYYY-MM-DD or null if unspecified",
      "confidence": 0.0-1.0
    }
  ],
  "has_promise": true|false
}

Rules:
- Look for speech acts like "I promise", "I will", "I'll make sure", "I guarantee", "I promise to"
- Also detect implicit promises ("Let me do that for you" implies commitment)
- If no promise detected, return {"promises": [], "has_promise": false}

Text:
"""
