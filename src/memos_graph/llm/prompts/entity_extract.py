"""Prompts for entity extraction."""

ENTITY_EXTRACT_PROMPT = """You are an expert entity extraction system. Given a conversation transcript, identify all named entities mentioned.

Extract entities of these types:
- person: Specific people names (@username, "John", etc.)
- place: Locations, cities, countries ("Tokyo", "remote")
- event: Things that happened or will happen ("meeting", "release")
- object: Physical or digital things ("projector", "GitHub repo")
- concept: Abstract ideas ("privacy", "agile development")
- organization: Companies, teams, projects ("Acme Corp", "backend team")

Output a JSON object with an "entities" array. Each entity has: name, type, metadata (optional context).
Only extract entities with high confidence. If no entities, return {{"entities": []}}.

Transcript:
{transcript}

JSON output:"""
