"""Prompts for promise extraction."""

PROMISE_EXTRACT_PROMPT = """You are a promise detection system. Given a conversation transcript, identify all commitments or promises made by the agent.

A promise is:
- A commitment to do something ("I'll send the report", "will review by Friday")
- A guarantee about future behavior ("I will always...")
- A to-do item assigned to the agent
- A stated intention that implies obligation

Output JSON with a "promises" array. Each promise has:
- content: The promise text
- status: "open" (default)
- due_at: ISO date if mentioned, otherwise null
- confidence: 0.0-1.0

Transcript:
{transcript}

JSON output:"""
