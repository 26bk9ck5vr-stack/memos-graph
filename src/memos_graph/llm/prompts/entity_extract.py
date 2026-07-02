"""LLM prompts for memos-graph."""

ENTITY_EXTRACT_PROMPT = """You are an entity and relation extractor for AI agent memory.

Extract entities and their relations from the given text.

Output JSON in this format:
{
  "entities": [
    {"name": "entity name", "type": "person|place|event|object|concept", "metadata": {}}
  ],
  "relations": [
    {"from": "entity1", "to": "entity2", "type": "relation_type", "confidence": 0.0-1.0}
  ]
}

Rules:
- Extract only significant entities (names, places, events, important objects)
- Use consistent entity names
- Relation types: knows, likes, dislikes, works_at, lives_in, created, participated_in, etc.
- Confidence: 0.0-1.0 based on how clear the relation is

Text:
"""
