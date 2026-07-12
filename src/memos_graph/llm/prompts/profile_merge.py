"""Prompts for user profile merging."""

PROFILE_MERGE_PROMPT = """You are a user profile merge system. Given an existing profile and new information from a conversation, update the profile intelligently.

Existing profile attributes: {existing_attributes}
New information from conversation: {new_information}

Merge rules:
- Merge lists (interests, preferences) by union, avoid duplicates
- Update scalar fields (mood, energy) with weighted average favoring recent
- Add new fields for new discovered attributes
- Preserve information that hasn't changed

Return JSON: {{"attributes": {{...merged profile...}}, "changes": ["list of changes made"]}}"""
