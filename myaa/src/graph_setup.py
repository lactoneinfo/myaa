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
from langchain.schema import SystemMessage, HumanMessage, AIMessage

from .tools.nature_cli import get_room_temp, set_ac, set_light

# ---------------------------------------------------------------------------
# 1. ENV + LLM
# ---------------------------------------------------------------------------
load_dotenv()
llm = init_chat_model(os.environ["GEMINI_MODEL"])

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
persona_file = os.path.join(root_dir, "personas.yaml")
if os.path.exists(persona_file):
    with open(persona_file, encoding="utf-8") as f:
        persona_configs = yaml.safe_load(f)
else:
    persona_configs = {}
default_persona_id = persona_configs.get("default_persona", "example")


# ---------------------------------------------------------------------------
# 2. Tools
# ---------------------------------------------------------------------------
@tool
def human_assistance(query: str) -> str:
    """Fallback: ask a human for help (pauses graph via interrupt)."""
    human_response = interrupt({"query": query})
    return human_response["data"]


search_tool = TavilySearch(max_results=2)
tools = [search_tool, human_assistance, get_room_temp, set_ac, set_light]
llm_with_tools = llm.bind_tools(tools)


# ---------------------------------------------------------------------------
# 3. State & Nodes
# ---------------------------------------------------------------------------
class ChatState(TypedDict):
    messages: Annotated[List, add_messages]
    persona_id: str


graph_builder = StateGraph(ChatState)


def chatbot(state: ChatState):
    pid = state["persona_id"]
    config = persona_configs.get(pid, {})
    name = config.get("name", pid)
    owners = config.get("owners") or (
        [] if config.get("owner") is None else [config.get("owner")]
    )
    owners_str = ", ".join(owners) if owners else None
    desc = config.get("description", pid)
    system_msg = SystemMessage(
        content=(
            f"You are {name}. \n{desc}\n" + f"Your owner: {owners_str}.\n"
            if owners_str
            else ""
            + "Human messages are read in the format 'name: content'.\n"
            + "Please do not include the name in the reply, only output the message content.\n"
        )
    )
    history = state.get("messages", [])
    messages = [system_msg] + history
    raw = llm_with_tools.invoke(messages)
    ai_msg = None
    if isinstance(raw, AIMessage):
        ai_msg = raw.model_copy(update={"additional_kwargs": {"name": name}})
    else:
        ai_msg = AIMessage(content=f"{name}: {raw}", additional_kwargs={"name": name})
    return {"messages": [ai_msg]}


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
async def stream_chat(thread_id: str, user_text: str, persona_id: str, speaker: str):
    """Invoke the graph and yield AI messages (for streaming to Discord)."""
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    formatted = f"{speaker}: {user_text}"
    payload = {
        "messages": [
            HumanMessage(content=formatted, additional_kwargs={"name": speaker})
        ],
        "persona_id": persona_id,
    }
    events = compiled_graph.stream(payload, config, stream_mode="values")
    for ev in events:
        if "messages" in ev:
            yield ev["messages"][-1].content


async def stream_chat_debug(
    thread_id: str, user_text: str, persona_id: str, speaker: str
):
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    formatted = f"{speaker}: {user_text}"
    payload = {
        "messages": [
            HumanMessage(content=formatted, additional_kwargs={"name": speaker})
        ],
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
        if not cp:
            lines.append("  (no checkpoint found)\n")
            continue
        msgs = cp.checkpoint.get("channel_values", {}).get("messages", [])
        if not msgs:
            lines.append("  (no messages found)\n")
            continue
        for m in msgs:
            # content
            if hasattr(m, "content"):
                raw = m.content or ""
            elif isinstance(m, dict):
                raw = m.get("content") or ""
            else:
                raw = str(m) or ""
            content = raw.strip()
            # role
            kind = m.__class__.__name__.lower()
            role = "user" if "human" in kind else "ai"
            # speaker
            speaker = None
            if hasattr(m, "additional_kwargs"):
                speaker = m.additional_kwargs.get("name")
            elif isinstance(m, dict):
                speaker = m.get("name")
            speaker = speaker or role
            lines.append(f"  [{role}][{speaker}] {content}")
        lines.append("")
    return "\n".join(lines) if lines else "⚠️ No active sessions."
