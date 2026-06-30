from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from utils.cache import cached_llm_call
from utils.llm_call import llm
from utils.state import State

def generate_content(state: State) -> dict:
    topic = state["topic"]

    def compute() -> str:
        response = llm.invoke(
            [
                SystemMessage(content="You are a helpful writer that drafts concise content."),
                HumanMessage(content=f"Write content about: {topic}")
            ]
        )
        return response.content

    content, cached = cached_llm_call("generate_content", topic, compute)
    return {"content": content, "content_cached": cached}


def critique_content(state: State) -> dict:
    content = state["content"]

    def compute() -> str:
        response = llm.invoke(
            [
                SystemMessage(content="You are a strict editor that gives concise critiques."),
                HumanMessage(content=f"Critique this content:\n{content}")
            ]
        )
        return response.content

    critique, cached = cached_llm_call("critique_content", content, compute)
    return {"critique": critique, "critique_cached": cached}
