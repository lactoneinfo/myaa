import os
from typing import Annotated, TypedDict, List
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langchain_tavily import TavilySearch  # type: ignore
from langchain_core.tools import tool
from langgraph.types import interrupt
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
import yaml
from langchain.schema import SystemMessage

# ---------------------------------------------------------------------------
# 1. ENV + LLM
# ---------------------------------------------------------------------------
load_dotenv()
llm = init_chat_model(os.environ["GEMINI_MODEL"])


persona_file = os.path.join(os.path.dirname(__file__), "personas.yaml")
if os.path.exists(persona_file):
    with open(persona_file, encoding="utf-8") as f:
        persona_configs = yaml.safe_load(f)
else:
    persona_configs = {}


# ---------------------------------------------------------------------------
# 2. Tools
# ---------------------------------------------------------------------------
@tool
def human_assistance(query: str) -> str:
    """Fallback: ask a human for help (pauses graph via interrupt)."""
    human_response = interrupt({"query": query})
    return human_response["data"]


search_tool = TavilySearch(max_results=2)
tools = [search_tool, human_assistance]
llm_with_tools = llm.bind_tools(tools)


# ---------------------------------------------------------------------------
# 3. State & Nodes
# ---------------------------------------------------------------------------
class ChatState(TypedDict):
    messages: Annotated[List, add_messages]
    persona_id: str


graph_builder = StateGraph(ChatState)


def chatbot(state: ChatState):
    # persona_id を使ったシステムメッセージを先頭に挿入
    pid = state["persona_id"]
    config = persona_configs.get(pid, {})
    name = config.get("name", pid)
    desc = config.get("description", "You are a sample assistant character.")
    system_msg = SystemMessage(content=f"あなたはキャラクター『{name}』です。\n{desc}")
    history = [
        m
        for m in state["messages"]
        if not (getattr(m, "role", None) == "ai" and m.content.strip() == "")
    ]
    messages = [system_msg] + history
    reply = llm_with_tools.invoke(messages)
    return {"messages": [reply]}


graph_builder.add_node("chatbot", chatbot)

tool_node = ToolNode(tools=tools)
graph_builder.add_node("tools", tool_node)

graph_builder.add_conditional_edges("chatbot", tools_condition)
graph_builder.add_edge("tools", "chatbot")

graph_builder.set_entry_point("chatbot")

# Single‑file memory (can be swapped with RedisSaver etc.)
memory = MemorySaver()
compiled_graph = graph_builder.compile(checkpointer=memory)


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------
async def stream_chat(thread_id: str, user_text: str, persona_id: str):
    """Invoke the graph and yield AI messages (for streaming to Discord)."""
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    payload = {
        "messages": [{"role": "user", "content": user_text}],
        "persona_id": persona_id,
    }
    events = compiled_graph.stream(payload, config, stream_mode="values")
    for ev in events:
        if "messages" in ev:
            yield ev["messages"][-1].content  # Return raw string only


async def stream_chat_debug(thread_id: str, user_text: str, persona_id: str):
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    payload = {
        "messages": [{"role": "user", "content": user_text}],
        "persona_id": persona_id,
    }
    events = compiled_graph.stream(payload, config, stream_mode="debug")
    for ev in events:
        print("🛠 EVENT:", ev)

        if "tool_calls" in ev:
            print("➡️ tool_calls:", ev["tool_calls"])
        if "tool_results" in ev:
            print("⬅️ tool_results:", ev["tool_results"])

        if "messages" in ev:
            for m in ev["messages"]:
                print(f"   · [{m.role}] {m.content}")
            yield ev["messages"][-1].content


def list_graph_states(session_mgr) -> str:
    if not isinstance(memory, InMemorySaver):
        return "⚠️ This memory backend does not support inspection."

    lines: list[str] = []
    for thread_id in session_mgr.list_thread_ids():
        lines.append(f"🧵 Thread ID: {thread_id}")

        cp = memory.get_tuple({"configurable": {"thread_id": thread_id}})
        if cp is None:
            lines.append("  (no checkpoint found)\n")
            continue

        values = cp.checkpoint.get("channel_values", {}) or {}
        messages = values.get("messages", [])

        if not messages:
            lines.append("  (no messages found)\n")
            continue

        for m in messages:
            if hasattr(m, "content"):
                content = m.content
            elif isinstance(m, dict):
                content = m.get("content", "")
            else:
                content = str(m)

            kind = m.__class__.__name__.lower()
            if "human" in kind:
                role = "user"
            elif "ai" in kind:
                role = "ai"
            else:
                role = m.get("role", "?") if isinstance(m, dict) else "?"

            lines.append(f"  [{role}] {content.strip()}")
        lines.append("")

    return "\n".join(lines) if lines else "⚠️ No active sessions."
