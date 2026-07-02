"""Query expansion prompt for better recall."""

QUERY_EXPAND_PROMPT = """You are a query expander for AI agent memory retrieval.

Given a user query, generate 3-5 expanded variations that might help find relevant memories.

Output one query per line, no JSON.

Example:
Input: "What does she like to eat?"
Output:
favorite foods
dietary preferences
restaurants she enjoys
cooking interests
food allergies

Input: "Tell me about our first meeting"
Output:
first encounter
when we met
initial conversation
introduction moment
first interaction

Query:
"""
