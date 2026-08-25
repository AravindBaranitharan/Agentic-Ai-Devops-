# LangChain & LangGraph — live demo

Runnable examples for two sessions. **LangChain** = compose LLM apps from components
(`prompt | model | parser`). **LangGraph** = build *stateful, looping, multi-step* agents
as a graph of nodes + edges. LangGraph is built by the LangChain team and uses LangChain
components inside its nodes.

## Setup
```bash
cd langchain-langgraph-demo
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp env.sample .env        # paste your OPENAI_API_KEY
```

## LangChain examples (`langchain/`)
| File | Shows | Live? |
|------|-------|-------|
| `01_lcel_chain.py` | LCEL — `prompt \| model \| parser`, plus streaming | needs key |
| `02_tools_agent.py` | `@tool` + `create_agent` — the model calls functions | needs key |
| `03_structured_output.py` | `with_structured_output(PydanticModel)` — typed extraction | needs key |

## LangGraph examples (`langgraph/`)
| File | Shows | Live? |
|------|-------|-------|
| `01_state_graph_basic.py` | **nodes + edges + shared state** (no LLM) | **offline** |
| `02_agent_loop.py` | the **agent loop** — cyclic graph, `tools_condition`, `ToolNode` | needs key |
| `03_human_in_the_loop.py` | **interrupt → resume** — pause for approval (no LLM) | **offline** |

Run any of them: `cd langgraph && python 02_agent_loop.py`

## LangChain vs LangGraph — the comparison
| | **LangChain** | **LangGraph** |
|---|---|---|
| Mental model | a **pipeline / DAG** (`a \| b \| c`) | a **graph / state machine** (nodes + edges) |
| Control flow | linear, left→right | **loops, branches, conditionals** |
| State | passed along the chain (implicit) | **explicit, typed, shared** across nodes |
| Memory / persistence | add-on | **built-in checkpointer** (resume, threads) |
| Human-in-the-loop | manual | **native `interrupt()`** |
| Best for | prompts, RAG, extraction, simple tool use | **agents**, multi-step, retries, approvals, multi-agent |
| Relationship | the components (models, tools, prompts) | the **orchestration** that runs those components |

**Rule of thumb:** reach for **LangChain** when the flow is a straight line;
reach for **LangGraph** the moment you need a **loop, a branch, memory, or a human in the middle**.

## Suggested demo order
1. `langchain/01` → "this is composition."
2. `langchain/02` → "the model can call tools."
3. `langgraph/01` → "now it's a graph with shared state."
4. `langgraph/02` → "and the graph can **loop** — that's a real agent." *(the wow)*
5. `langgraph/03` → "and it can **pause for a human**." *(ties to approvals)*
