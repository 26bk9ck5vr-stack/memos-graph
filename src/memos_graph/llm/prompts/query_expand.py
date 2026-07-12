"""Prompts for query expansion."""

QUERY_EXPAND_PROMPT = """You are a query expansion system. Given a user query, expand it to improve memory search recall.

Original query: {query}

Expand by:
1. Adding synonyms and related terms
2. Including possible variations (singular/plural, past/present)
3. Adding domain-specific terms if applicable
4. Breaking compound queries into sub-queries

Return JSON: {{"expanded_queries": ["query1", "query2", ...], "keywords": ["key1", "key2"]}}"""
