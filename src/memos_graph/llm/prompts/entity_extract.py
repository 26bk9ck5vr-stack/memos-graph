"""Prompts for entity extraction."""

ENTITY_EXTRACT_PROMPT = """You are an expert entity and relationship extraction system. Given a conversation transcript, identify all named entities mentioned AND the relationships between them.

Extract entities of these types:
- person: Specific people names (@username, "John", etc.)
- place: Locations, cities, countries ("Tokyo", "remote")
- event: Things that happened or will happen ("meeting", "release")
- object: Physical or digital things ("projector", "GitHub repo")
- concept: Abstract ideas ("privacy", "agile development")
- organization: Companies, teams, projects ("Acme Corp", "backend team")

Extract relationships between entities. Each relationship has:
- source: name of the source entity
- target: name of the target entity  
- type: relationship type (e.g., "works_at", "located_in", "part_of", "related_to", "created", "discussed")

Output a JSON object with:
- "entities": array of {name, type, metadata (optional)}
- "relations": array of {source, target, type}

Only extract high-confidence entities and relations. If none, return {"entities": [], "relations": []}.

Transcript:
{transcript}

JSON output:"""
