"""Regression tests for LangGraph message reducer behavior in research subgraphs."""

from typing import Annotated, Any, TypedDict, get_type_hints

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph, add_messages
from langgraph.prebuilt import ToolNode

from tradingagents.equity_research.runtime.state import AgentState
from tradingagents.equity_research.runtime.utils.messages import clear_messages_update


@tool
def echo_tool(value: str) -> str:
    """Echo a value."""
    return value


def test_agent_state_uses_add_messages_reducer():
    hints = get_type_hints(AgentState, include_extras=True)["messages"].__metadata__
    assert add_messages in hints


def test_tool_node_appends_tool_message_without_dropping_ai_tool_call():
    class MiniState(TypedDict):
        messages: Annotated[list[Any], add_messages]

    graph = StateGraph(MiniState)
    graph.add_node(
        "agent",
        lambda state: {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[{"id": "tc1", "name": "echo_tool", "args": {"value": "ok"}}],
                )
            ]
        },
    )
    graph.add_node("tools", ToolNode([echo_tool]))
    graph.add_edge(START, "agent")
    graph.add_edge("agent", "tools")
    graph.add_edge("tools", END)
    compiled = graph.compile()

    result = compiled.invoke({"messages": [HumanMessage(content="go")]})
    messages = result["messages"]

    assert len(messages) == 3
    assert isinstance(messages[0], HumanMessage)
    assert isinstance(messages[1], AIMessage)
    assert messages[1].tool_calls
    assert isinstance(messages[2], ToolMessage)
    assert messages[2].tool_call_id == "tc1"


def test_clear_messages_update_removes_all_messages():
    class MiniState(TypedDict):
        messages: Annotated[list[Any], add_messages]

    graph = StateGraph(MiniState)
    graph.add_node("seed", lambda _state: {"messages": [HumanMessage(content="hello")]})
    graph.add_node("clear", lambda _state: clear_messages_update())
    graph.add_edge(START, "seed")
    graph.add_edge("seed", "clear")
    graph.add_edge("clear", END)
    compiled = graph.compile()

    result = compiled.invoke({})
    assert result["messages"] == []
