# TradingAgents/graph/setup.py

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from tradingagents.agents import (
    create_aggressive_debator,
    create_bear_researcher,
    create_bull_researcher,
    create_conservative_debator,
    create_fundamentals_analyst,
    create_msg_delete,
    create_neutral_debator,
    create_news_analyst,
    create_portfolio_manager,
    create_research_manager,
    create_sentiment_analyst,
    create_trader,
)
from tradingagents.agents import *
from tradingagents.agents.analysts.market_analyst import MarketAnalystSubgraph
from tradingagents.agents.utils.agent_states import AgentState

from .analyst_execution import build_analyst_execution_plan
from .conditional_logic import ConditionalLogic

# Analysts whose tool loops are fully handled inside a compiled sub-graph.
SELF_CONTAINED_ANALYSTS = frozenset({"market"})


def _wrap_market_analyst_subgraph(compiled_graph):
    """Wrap a compiled market analyst subgraph to work with parent AgentState.
    
    This ensures proper state mapping and handles the message channel correctly.
    """
    def market_analyst_node(state: AgentState) -> Dict[str, Any]:
        # Create subgraph input state
        subgraph_input = {
            "messages": state["messages"],
            "company_of_interest": state["company_of_interest"],
            "trade_date": state["trade_date"],
        }
        
        # Run the compiled subgraph
        result = compiled_graph.invoke(subgraph_input)
        
        # Sub-graph owns its tool loop; parent only needs the final report.
        return {
            "market_report": result.get("market_report", ""),
            "price_action_report": result.get("price_action_report", ""),
            "momentum_report": result.get("momentum_report", ""),
            "order_flow_report": result.get("order_flow_report", ""),
            "messages": [],
        }
    
    return market_analyst_node


class GraphSetup:
    """Handles the setup and configuration of the agent graph."""

    def __init__(
        self,
        quick_thinking_llm: Any,
        deep_thinking_llm: Any,
        tool_nodes: dict[str, ToolNode],
        conditional_logic: ConditionalLogic,
        analyst_concurrency_limit: int = 1,
    ):
        """Initialize with required components."""
        self.quick_thinking_llm = quick_thinking_llm
        self.deep_thinking_llm = deep_thinking_llm
        self.tool_nodes = tool_nodes
        self.conditional_logic = conditional_logic
        self.analyst_concurrency_limit = analyst_concurrency_limit

    def setup_graph(
        self, selected_analysts=("market", "social", "news", "fundamentals")
    ):
        """Set up and compile the agent workflow graph.

        Args:
            selected_analysts (list): List of analyst types to include. Options are:
                - "market": Market analyst
                - "social": Social media analyst
                - "news": News analyst
                - "fundamentals": Fundamentals analyst
        """
        plan = build_analyst_execution_plan(
            selected_analysts,
            concurrency_limit=self.analyst_concurrency_limit,
        )
        if len(selected_analysts) == 0:
            raise ValueError("Trading Agents Graph Setup Error: no analysts selected!")

        # Create analyst nodes
        analyst_nodes = {}
        delete_nodes = {}
        tool_nodes = {}

        if "market" in selected_analysts:
            compiled_market_graph = MarketAnalystSubgraph(
                quick_thinking_llm=self.quick_thinking_llm,
                deep_thinking_llm=self.deep_thinking_llm
            ).compile()
            # Wrap the compiled subgraph to handle parent state mapping
            analyst_nodes["market"] = _wrap_market_analyst_subgraph(compiled_market_graph)
            delete_nodes["market"] = create_msg_delete()

        if "social" in selected_analysts:
            # "social" selector key preserved for back-compat with existing
            # user configs; the underlying agent has been renamed to
            # sentiment_analyst (the old name advertised social-media data
            # the agent never had access to — see issue #557).
            analyst_nodes["social"] = create_sentiment_analyst(
                self.quick_thinking_llm
            )
            delete_nodes["social"] = create_msg_delete()
            tool_nodes["social"] = self.tool_nodes["social"]

        if "news" in selected_analysts:
            analyst_nodes["news"] = create_news_analyst(self.quick_thinking_llm)
            delete_nodes["news"] = create_msg_delete()
            tool_nodes["news"] = self.tool_nodes["news"]

        if "fundamentals" in selected_analysts:
            analyst_nodes["fundamentals"] = create_fundamentals_analyst(
                self.quick_thinking_llm
            )
            delete_nodes["fundamentals"] = create_msg_delete()
            tool_nodes["fundamentals"] = self.tool_nodes["fundamentals"]
            
        # analyst_factories = {
        #     "market": lambda: create_market_analyst(self.quick_thinking_llm),
        #     "social": lambda: create_sentiment_analyst(self.quick_thinking_llm),
        #     "news": lambda: create_news_analyst(self.quick_thinking_llm),
        #     "fundamentals": lambda: create_fundamentals_analyst(self.quick_thinking_llm),
        # }

        # Create researcher and manager nodes
        bull_researcher_node = create_bull_researcher(self.quick_thinking_llm)
        bear_researcher_node = create_bear_researcher(self.quick_thinking_llm)
        research_manager_node = create_research_manager(self.deep_thinking_llm)
        trader_node = create_trader(self.quick_thinking_llm)

        # Create risk analysis nodes
        aggressive_analyst = create_aggressive_debator(self.quick_thinking_llm)
        neutral_analyst = create_neutral_debator(self.quick_thinking_llm)
        conservative_analyst = create_conservative_debator(self.quick_thinking_llm)
        portfolio_manager_node = create_portfolio_manager(self.deep_thinking_llm)

        # Create workflow
        workflow = StateGraph(AgentState)

        # Add analyst nodes to the graph
        for analyst_type, node in analyst_nodes.items():
            workflow.add_node(f"{analyst_type.capitalize()} Analyst", node)
            workflow.add_node(
                f"Msg Clear {analyst_type.capitalize()}", delete_nodes[analyst_type]
            )
            if analyst_type not in SELF_CONTAINED_ANALYSTS:
                workflow.add_node(f"tools_{analyst_type}", tool_nodes[analyst_type])

        # Add other nodes
        workflow.add_node("Bull Researcher", bull_researcher_node)
        workflow.add_node("Bear Researcher", bear_researcher_node)
        workflow.add_node("Research Manager", research_manager_node)
        workflow.add_node("Trader", trader_node)
        workflow.add_node("Aggressive Analyst", aggressive_analyst)
        workflow.add_node("Neutral Analyst", neutral_analyst)
        workflow.add_node("Conservative Analyst", conservative_analyst)
        workflow.add_node("Portfolio Manager", portfolio_manager_node)

        # Define edges
        # Start with the first analyst
        workflow.add_edge(START, plan.specs[0].agent_node)

        # Connect analysts in sequence
        for i, spec in enumerate(plan.specs):
            current_analyst = spec.agent_node
            current_tools = spec.tool_node
            current_clear = spec.clear_node

            if analyst_type in SELF_CONTAINED_ANALYSTS:
                workflow.add_edge(current_analyst, current_clear)
            else:
                workflow.add_conditional_edges(
                    current_analyst,
                    getattr(self.conditional_logic, f"should_continue_{analyst_type}"),
                    {
                        current_tools: current_tools,
                        current_clear: current_clear,
                    },
                )
                workflow.add_edge(current_tools, current_analyst)

            # Connect to next analyst or to Bull Researcher if this is the last analyst
            if i < len(plan.specs) - 1:
                workflow.add_edge(current_clear, plan.specs[i + 1].agent_node)
            else:
                # workflow.add_edge(current_clear, "Bull Researcher")
                workflow.add_edge(current_clear, END)

        # Add remaining edges
        # workflow.add_conditional_edges(
        #     "Bull Researcher",
        #     self.conditional_logic.should_continue_debate,
        #     {
        #         "Bear Researcher": "Bear Researcher",
        #         "Research Manager": "Research Manager",
        #     },
        # )
        # workflow.add_conditional_edges(
        #     "Bear Researcher",
        #     self.conditional_logic.should_continue_debate,
        #     {
        #         "Bull Researcher": "Bull Researcher",
        #         "Research Manager": "Research Manager",
        #     },
        # )
        # workflow.add_edge("Research Manager", "Trader")
        # workflow.add_edge("Trader", "Aggressive Analyst")
        # workflow.add_conditional_edges(
        #     "Aggressive Analyst",
        #     self.conditional_logic.should_continue_risk_analysis,
        #     {
        #         "Conservative Analyst": "Conservative Analyst",
        #         "Portfolio Manager": "Portfolio Manager",
        #     },
        # )
        # workflow.add_conditional_edges(
        #     "Conservative Analyst",
        #     self.conditional_logic.should_continue_risk_analysis,
        #     {
        #         "Neutral Analyst": "Neutral Analyst",
        #         "Portfolio Manager": "Portfolio Manager",
        #     },
        # )
        # workflow.add_conditional_edges(
        #     "Neutral Analyst",
        #     self.conditional_logic.should_continue_risk_analysis,
        #     {
        #         "Aggressive Analyst": "Aggressive Analyst",
        #         "Portfolio Manager": "Portfolio Manager",
        #     },
        # )

        # workflow.add_edge("Portfolio Manager", END)

        return workflow
