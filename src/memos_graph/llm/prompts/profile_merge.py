"""User profile merge prompt."""

PROFILE_MERGE_PROMPT = """You are a user profile merger for AI agent memory.

Merge multiple user profiles into one coherent profile.

Input: List of profiles, each with attributes like:
- display_name
- likes: [...]
- dislikes: [...]
- work: ...
- relationships: ...
- etc.

Output JSON in this format:
{
  "display_name": "Best name",
  "attributes": {
    "likes": ["merged, deduplicated list"],
    "dislikes": ["merged, deduplicated list"],
    "work": "Best description",
    "relationships": {...}
  },
  "conflicts_resolved": ["List of conflicts and how resolved"]
}

Rules:
- Deduplicate overlapping entries
- Prefer more recent/specific information
- Resolve conflicts by choosing the most detailed/recent
- Keep the structure clean and organized

Profiles:
"""
