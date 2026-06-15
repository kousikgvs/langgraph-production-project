from pathlib import Path

import yaml
from langgraph.graph import END, START, StateGraph

from utils.state import State
from functions.node_functions import critique_content, generate_content


NODE_FUNCTIONS = {
    "generate_content": generate_content,
    "critique_content": critique_content,
}


def load_workflow_config() -> dict:
    workflow_path = Path(__file__).resolve().parent / "workflow" / "workflow.yaml"
    with workflow_path.open("r", encoding="utf-8") as workflow_file:
        return yaml.safe_load(workflow_file)


def build_graph_from_config(config: dict) -> StateGraph:
    graph = StateGraph(State)

    for node_name, node_config in config["nodes"].items():
        function_name = node_config["function"].split(".")[-1]
        graph.add_node(node_name, NODE_FUNCTIONS[function_name])

    for edge in config["edges"]:
        from_node = START if edge["from"] == "START" else edge["from"]
        to_node = END if edge["to"] == "END" else edge["to"]
        graph.add_edge(from_node, to_node)

    return graph


graph = build_graph_from_config(load_workflow_config())
app = graph.compile()

if __name__ == "__main__":
    for update in app.stream({"topic": "LangGraph workflows"}, stream_mode="updates"):
        print(update)