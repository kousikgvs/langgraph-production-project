from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from utils.llm_call import llm
from utils.state import State

def generate_content(state: State) -> dict:
    response = llm.invoke(
        [
            SystemMessage(content="You are a helpful writer that drafts concise content."),
            HumanMessage(content=f"Write content about: {state['topic']}")
        ]
    )
    return {"content": response.content}


def critique_content(state: State) -> dict:
    response = llm.invoke(
        [
            SystemMessage(content="You are a strict editor that gives concise critiques."),
            HumanMessage(content=f"Critique this content:\n{state['content']}")
        ]
    )
    return {"critique": response.content}
