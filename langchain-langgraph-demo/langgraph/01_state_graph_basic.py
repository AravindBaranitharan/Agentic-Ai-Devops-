"""
LangGraph · 01 — The graph model (nodes + edges + shared state).

A LangGraph app is a GRAPH:
  • STATE   — a typed dict shared by every node
  • NODES   — functions that read state and return an update to it
  • EDGES   — define the order / control flow (START → … → END)

This one has NO LLM, so it runs offline — it's just to make the mental model click.

Run:  python 01_state_graph_basic.py
"""

from typing import TypedDict
from langgraph.graph import StateGraph, START, END


# 1) STATE — the shared memory that flows through the graph
class State(TypedDict):
    text: str
    words: int
    steps: list


# 2) NODES — each returns a PARTIAL update to the state
def clean(state: State):
    return {"text": state["text"].strip(), "steps": state["steps"] + ["clean"]}

def normalize(state: State):
    return {"text": state["text"].lower(), "steps": state["steps"] + ["normalize"]}

def count_words(state: State):
    return {"words": len(state["text"].split()), "steps": state["steps"] + ["count"]}


# 3) EDGES — wire the nodes into a flow
g = StateGraph(State)
g.add_node("clean", clean)
g.add_node("normalize", normalize)
g.add_node("count", count_words)
g.add_edge(START, "clean")
g.add_edge("clean", "normalize")
g.add_edge("normalize", "count")
g.add_edge("count", END)

app = g.compile()

if __name__ == "__main__":
    print("Graph:  START → clean → normalize → count → END\n")
    result = app.invoke({"text": "   Hello   LangGraph   WORLD  ", "words": 0, "steps": []})
    print("Nodes run :", " → ".join(result["steps"]))
    print("Final text:", repr(result["text"]))
    print("Word count:", result["words"])
    print("\nEvery node updated the SAME shared state — that's the whole idea.")
