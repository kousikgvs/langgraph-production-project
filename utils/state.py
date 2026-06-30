from typing import TypedDict
from langgraph.graph import StateGraph, START, END

# ── State ─────────────────────────────────────────────────────────────────────
class State(TypedDict):
    topic: str
    content: str
    critique: str
    content_cached: bool
    critique_cached: bool
