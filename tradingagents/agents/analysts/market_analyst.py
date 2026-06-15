from typing import Any, Callable, Dict, List, Sequence, TypedDict, Annotated

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import END, START, StateGraph, add_messages
from langgraph.managed import RemainingSteps
from langgraph.prebuilt import create_react_agent

from tradingagents.agents.utils.agent_utils import (
    get_indicators,
    get_instrument_context_from_state,
    get_language_instruction,
    get_stock_data,
    get_briefing_stock_info,
)

_COMMON_AGENT_PREFIX = (
    "You are a helpful AI assistant collaborating with other assistants. "
    "Use the provided tools to progress towards answering the question. "
    "If you are unable to fully answer, that is OK; another assistant with "
    "different tools will help where you left off. Execute what you can to "
    "make progress. "
    "You have access to multiple tools. You can call all necessary data-gathering tools simultaneously in a single step whenever possible"
)

PRICE_ACTION_TOOLS = [get_stock_data, get_briefing_stock_info]
MOMENTUM_TOOLS = [get_stock_data, get_indicators]
ORDER_FLOW_TOOLS = [get_stock_data, get_indicators, get_briefing_stock_info]  


class MarketSubgraphState(TypedDict, total=False):
    # initial input from outer graph
    messages: Annotated[List[BaseMessage], add_messages]
    company_of_interest: str
    trade_date: str

    # subagent outputs
    price_action_report: str
    momentum_report: str
    order_flow_report: str

    # final output
    market_report: str


class SpecialistAgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    remaining_steps: RemainingSteps
    company_of_interest: str
    trade_date: str


PRICE_ACTION_SYSTEM = (
    "You are a Price Action Analyst specialized in reading raw candlestick charts. "
    "Your role is to study recent OHLCV data for given company."
    "and produce a structured report by selecting the most relevant analytical tools from the following list. "
    "- basic_stats: Provides an overview of the stock's historical performance. Usage: Use this as a quick reference to understand the stock's price range, volatility and average performance over the specified period. Tips: Look for trends in the data, such as increasing volatility or a narrowing price range, which may indicate upcoming price movements\n"
    "- volume_stats: Volume Stats: Summarizes trading text-art volume profile. Usage: Analyze the average daily volume and identify any spikes in trading activity, including Point of Control, Value Area High / Low, High Volume Nodes, Low Volume Nodes. Tips: Unusual volume can signal significant news or a potential breakout; always investigate the context behind volume changes\n"
    "- structure_stats: Structure Stats: Analyzes the stock's price structure, including support and resistance levels by Dow Theory, Price Action, and ICT-SMC. Usage: Identify key price levels where the stock has historically found support or resistance, as well as any emerging patterns. Tips: Use this information to anticipate potential price reactions at these levels, and consider combining with other indicators for confirmation\n"
    "- resistance_stats: Resistance Stats: Focuses on identifying resistance levels and patterns in the stock's price history by Local Extrema + K-Means Clustering. Usage: Pinpoint price levels where the stock has historically struggled to move above, and analyze any patterns that may indicate strong resistance. Tips: Resistance levels can act as barriers to price increases; watch for multiple tests of these levels, which may weaken them and lead to breakouts\n"
    "- pattern_stats: Pattern Stats: Detects common price patterns in the stock's historical data, such as candlestick reversals, head and shoulders, double tops/bottoms, and triangles. Usage: Recognizing these patterns can provide insights into potential future price movements and trend reversals. Tips: Look for patterns that have formed over a significant number of trading days, as these tend to be more reliable; always confirm pattern signals with volume and other indicators.\n\n"
    "Select stats that provide diverse and complementary information. Also briefly explain why they are suitable for the given market context. When you tool call, please use the exact name of the indicators provided above as they are defined parameters, otherwise your call will fail. Please make sure to call get_stock_data first to retrieve the CSV that is needed to generate indicators. Then use get_briefing_stock_info with the specific names. Write a very detailed and nuanced report of the trends you observe. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
    "Write a very detailed and nuanced report of the text-art charts and stats you observe in Markdown format. Be concise and specific. Do NOT discuss derived indicators or off-chain data not covered by these core tools. Provide specific, actionable insights with supporting evidence to help traders make informed decisions. Make sure to append a Markdown table at the end of the report to organize key points in the report, making it structured and easy to read."
    + "\n\n"
    + get_language_instruction()
)

MOMENTUM_SYSTEM = (
    "You are a Momentum Analyst.  "
    "Your role is to analyse the following technical indicators and produce a structured report:\n"
    "Moving Averages:\n"
    "- close_50_sma: 50 SMA: A medium-term trend indicator. Usage: Identify trend direction and serve as dynamic support/resistance. Tips: It lags price; combine with faster indicators for timely signals.\n"
    "- close_200_sma: 200 SMA: A long-term trend benchmark. Usage: Confirm overall market trend and identify golden/death cross setups. Tips: It reacts slowly; best for strategic trend confirmation rather than frequent trading entries.\n"
    "- close_10_ema: 10 EMA: A responsive short-term average. Usage: Capture quick shifts in momentum and potential entry points. Tips: Prone to noise in choppy markets; use alongside longer averages for filtering false signals.\n"
    "\n"
    "MACD Related:\n"
    "- macd: MACD: Computes momentum via differences of EMAs. Usage: Look for crossovers and divergence as signals of trend changes. Tips: Confirm with other indicators in low-volatility or sideways markets.\n"
    "- macds: MACD Signal: An EMA smoothing of the MACD line. Usage: Use crossovers with the MACD line to trigger trades. Tips: Should be part of a broader strategy to avoid false positives.\n"
    "- macdh: MACD Histogram: Shows the gap between the MACD line and its signal. Usage: Visualize momentum strength and spot divergence early. Tips: Can be volatile; complement with additional filters in fast-moving markets.\n"
    "Momentum Indicators:\n"
    "- rsi: RSI: Measures momentum to flag overbought/oversold conditions. Usage: Apply 70/30 thresholds and watch for divergence to signal reversals. Tips: In strong trends, RSI may remain extreme; always cross-check with trend analysis.\n"
    "\n"
    "Volatility Indicators:\n"
    "- boll: Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. Usage: Acts as a dynamic benchmark for price movement. Tips: Combine with the upper and lower bands to effectively spot breakouts or reversals.\n"
    "- boll_ub: Bollinger Upper Band: Typically 2 standard deviations above the middle line. Usage: Signals potential overbought conditions and breakout zones. Tips: Confirm signals with other tools; prices may ride the band in strong trends.\n"
    "- boll_lb: Bollinger Lower Band: Typically 2 standard deviations below the middle line. Usage: Indicates potential oversold conditions. Tips: Use additional analysis to avoid false reversal signals.\n"
    "- atr: ATR: Averages true range to measure volatility. Usage: Set stop-loss levels and adjust position sizes based on current market volatility. Tips: It's a reactive measure, so use it as part of a broader risk management strategy.\n"
    "Volume-Based Indicators:\n"
    "- vwma: VWMA: A moving average weighted by volume. Usage: Confirm trends by integrating price action with volume data. Tips: Watch for skewed results from volume spikes; use in combination with other volume analyses.\n"
    "\n"
    "Select indicators that provide diverse and complementary information. Avoid redundancy (e.g., do not select both rsi and stochrsi). Also briefly explain why they are suitable for the given market context. When you tool call, please use the exact name of the indicators provided above as they are defined parameters, otherwise your call will fail. Please make sure to call get_stock_data first to retrieve the CSV that is needed to generate indicators. Then use get_indicators with the specific indicator names. Write a very detailed and nuanced report of the trends you observe. Provide specific, actionable insights with supporting evidence to help traders make informed decisions.\n"
    "Write a very detailed and nuanced report and stats you observe in Markdown format. Be concise and specific. Do NOT discuss derived indicators or off-chain data not covered by these core tools. Provide specific, actionable insights with supporting evidence to help traders make informed decisions. Make sure to append a Markdown table at the end of the report to organize key points in the report, making it structured and easy to read."
    + get_language_instruction()
)

ORDER_FLOW_SYSTEM = (
    "You are an Order Flow Analyst specializing in market microstructure and volume dynamics. "
    "Your objective is to study recent trading activity for given company "
    "To conduct your analysis, you must utilize the following analytical tools to gather insights"
    "Step 1: Retrieve Base Data"
    "You must call get_stock_data first to retrieve the OHLCV CSV data necessary for generating all subsequent indicators and statistics. \n"
    "Step 2: Generate Order Flow Indicators"
    "Call get_indicators using exactly the following indicator names to capture momentum and conviction:"
    " - vwma: Volume-Weighted Moving Average. Usage: Integrates price action with volume to confirm trends. Use it to determine if current price action has actual volume conviction.\n"
    " - atr: Average True Range. Usage: Measures the current volatility regime (expanding vs. contracting) to inform position sizing and risk management.\n"
    "Step 3: Retrieve Volume & Statistical Profiles"
    "Call get_briefing_stock_info (or the respective profile tool) using the following parameters:\n"
    "- basic_stats: Provides an overview of the stock's historical performance, price range, and baseline volatility trends.\n"
    "- volume_stats: Summarizes the text-art volume profile. Usage: Identify the Point of Control (POC), Value Area High/Low, and High Volume Nodes to pinpoint where the heaviest institutional and retail trading activity occurred.\n"
    "Using the raw data and text-art provided by these tools, write a highly detailed and nuanced report structured into exactly these four sections:\n"
    "- Volume Trend: Is the volume confirming or diverging from the current price movement? (Reference average daily volume spikes, POC, and volume profile distribution)."
    "- VWMA vs Price: Is the current price above or below the VWMA? What does the spread between price and the volume-weighted average imply about market conviction?"
    "- ATR & Volatility Regime: What is the current ATR reading? Is volatility expanding or contracting, and how should this dictate stop-loss placement?"
    "- Net Interpretation: Synthesize the volume profile, VWMA, and ATR data. Are market participants positioned aggressively or defensively? Provide specific, actionable insights"
    "Write a very detailed and nuanced report and stats you observe in Markdown format. Be concise and specific. Do NOT discuss derived indicators or off-chain data not covered by these core tools. Provide specific, actionable insights with supporting evidence to help traders make informed decisions. Make sure to append a Markdown table at the end of the report to organize key points in the report, making it structured and easy to read."
    + get_language_instruction()
)


def _extract_final_report(messages: Sequence[BaseMessage]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            return msg.content if isinstance(msg.content, str) else str(msg.content)
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content if isinstance(msg.content, str) else str(msg.content)
    return ""


def _make_specialist_prompt(system_message_template: str, tools: Sequence[Any]) -> Callable:
    def prompt_fn(state: SpecialistAgentState) -> List[BaseMessage]:
        company = state.get("company_of_interest", "")
        current_date = state.get("trade_date", "")
        instrument_context = build_instrument_context(company) if company else ""
        tool_names = ", ".join(t.name for t in tools)
        system_content = (
            _COMMON_AGENT_PREFIX
            + f"You have access to the following tools: {tool_names}.\n"
            + system_message_template.format(
                company_of_interest=company,
                current_date=current_date,
            )
            + f"\nThe current date is {current_date}. {instrument_context}"
        )
        return [SystemMessage(content=system_content)] + list(state.get("messages", []))

    return prompt_fn


def _build_specialist_react_agent(
    llm: Any,
    tools: Sequence[Any],
    system_message_template: str,
    name: str,
):
    return create_react_agent(
        model=llm,
        tools=list(tools),
        prompt=_make_specialist_prompt(system_message_template, tools),
        state_schema=SpecialistAgentState,
        name=name,
    )


def _wrap_react_agent(compiled_agent: Any, report_key: str):
    def node(state: MarketSubgraphState) -> Dict[str, Any]:
        company = state.get("company_of_interest")
        trade_date = state.get("trade_date")
        if company is None or trade_date is None:
            raise ValueError("trade_date and company_of_interest are required")

        result = compiled_agent.invoke({
            "messages": [
                HumanMessage(content=f"Analyze {company} as of {trade_date}.")
            ],
            "company_of_interest": company,
            "trade_date": trade_date,
        })
        report = _extract_final_report(result.get("messages", []))
        return {report_key: report}

    node.__name__ = f"run_{report_key}"
    return node


def _make_synthesizer_node(llm: Any):
    """
    Reads the three specialist reports from state and produces one integrated
    deep market analysis.  Does not use tools – pure reasoning step.
    """
    system_message = (
        "You are the Market Synthesizer. You have received three specialist "
        "sub-reports on {company_of_interest} as of {current_date}.\n\n"
        "=== PRICE ACTION REPORT ===\n{price_action_report}\n\n"
        "=== MOMENTUM REPORT ===\n{momentum_report}\n\n"
        "=== ORDER FLOW REPORT ===\n{order_flow_report}\n\n"
        "Your task: write ONE integrated, deep market analysis report that:\n"
        "- Reconciles agreements and conflicts between the three views.\n"
        "- Identifies the highest-conviction signals.\n"
        "- States the overall directional bias and key risks.\n"
        "- Proposes 1-3 actionable observations for the trading team.\n"
        "Use clear section headings. Append a Markdown summary table.\n"
        + get_language_instruction()
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        MessagesPlaceholder(variable_name="messages"),
    ])

    chain = prompt | llm  # no tools needed

    def synthesizer_node(state: MarketSubgraphState) -> Dict[str, Any]:
        current_date = state.get("trade_date", "")
        result = chain.invoke({
            "company_of_interest": state.get("company_of_interest", ""),
            "current_date": current_date,
            "price_action_report": state.get("price_action_report") or "(not available)",
            "momentum_report":     state.get("momentum_report")     or "(not available)",
            "order_flow_report":   state.get("order_flow_report")   or "(not available)",
            "messages": [HumanMessage(content="Please produce the integrated market report now.")],
        })
        return {
            "messages": [],              # synthesizer is the final node; clear
            "market_report": result.content,
        }

    return synthesizer_node


class MarketAnalystSubgraph:
    """
    Builds and compiles the Market Analyst sub-graph.

    Each specialist runs as a LangGraph ``create_react_agent`` sub-graph so
    tool-call loops and message pairing are handled by the framework.
    Vendor routing is handled transparently by interface.py.

    Usage
    -----
        subgraph = MarketAnalystSubgraph(
            quick_thinking_llm=quick_llm,
            deep_thinking_llm=deep_llm,
        ).compile()

        # In GraphSetup.setup_graph():
        workflow.add_node("Market Analyst", subgraph)

    Extending with new order-flow tools
    ------------------------------------
    When new tools (open_interest, funding_rates, …) are added to
    interface.py, simply append them to ORDER_FLOW_TOOLS at the top of this
    file.  The sub-graph will pick them up automatically on the next build.
    """

    def __init__(self, quick_thinking_llm: Any, deep_thinking_llm: Any):
        self.quick_llm = quick_thinking_llm
        self.deep_llm = deep_thinking_llm

    def build(self) -> StateGraph:
        price_action_agent = _build_specialist_react_agent(
            self.quick_llm,
            PRICE_ACTION_TOOLS,
            PRICE_ACTION_SYSTEM,
            "Price Action Agent",
        )
        momentum_agent = _build_specialist_react_agent(
            self.quick_llm,
            MOMENTUM_TOOLS,
            MOMENTUM_SYSTEM,
            "Momentum Agent",
        )
        order_flow_agent = _build_specialist_react_agent(
            self.quick_llm,
            ORDER_FLOW_TOOLS,
            ORDER_FLOW_SYSTEM,
            "Order Flow Agent",
        )

        wf = StateGraph(MarketSubgraphState)
        wf.add_node(
            "Price Action Agent",
            _wrap_react_agent(price_action_agent, "price_action_report"),
        )
        wf.add_node(
            "Momentum Agent",
            _wrap_react_agent(momentum_agent, "momentum_report"),
        )
        wf.add_node(
            "Order Flow Agent",
            _wrap_react_agent(order_flow_agent, "order_flow_report"),
        )
        wf.add_node("Market Synthesizer", _make_synthesizer_node(self.quick_llm))

        wf.add_edge(START, "Price Action Agent")
        wf.add_edge(START, "Momentum Agent")
        wf.add_edge(START, "Order Flow Agent")

        wf.add_edge("Price Action Agent", "Market Synthesizer")
        wf.add_edge("Momentum Agent", "Market Synthesizer")
        wf.add_edge("Order Flow Agent", "Market Synthesizer")
        wf.add_edge("Market Synthesizer", END)

        return wf

    def compile(self, **kwargs):
        """Build and compile the sub-graph."""
        return self.build().compile(**kwargs)


# def create_market_analyst(llm):

#     def market_analyst_node(state):
#         current_date = state["trade_date"]
#         instrument_context = build_instrument_context(state["company_of_interest"])

#         tools = [
#             get_stock_data,
#             get_indicators,
#         ]

#         system_message = (
#             """You are a trading assistant tasked with analyzing financial markets. Your role is to select the **most relevant indicators** for a given market condition or trading strategy from the following list. The goal is to choose up to **8 indicators** that provide complementary insights without redundancy. Categories and each category's indicators are:

# Moving Averages:
# - close_50_sma: 50 SMA: A medium-term trend indicator. Usage: Identify trend direction and serve as dynamic support/resistance. Tips: It lags price; combine with faster indicators for timely signals.
# - close_200_sma: 200 SMA: A long-term trend benchmark. Usage: Confirm overall market trend and identify golden/death cross setups. Tips: It reacts slowly; best for strategic trend confirmation rather than frequent trading entries.
# - close_10_ema: 10 EMA: A responsive short-term average. Usage: Capture quick shifts in momentum and potential entry points. Tips: Prone to noise in choppy markets; use alongside longer averages for filtering false signals.

# MACD Related:
# - macd: MACD: Computes momentum via differences of EMAs. Usage: Look for crossovers and divergence as signals of trend changes. Tips: Confirm with other indicators in low-volatility or sideways markets.
# - macds: MACD Signal: An EMA smoothing of the MACD line. Usage: Use crossovers with the MACD line to trigger trades. Tips: Should be part of a broader strategy to avoid false positives.
# - macdh: MACD Histogram: Shows the gap between the MACD line and its signal. Usage: Visualize momentum strength and spot divergence early. Tips: Can be volatile; complement with additional filters in fast-moving markets.

# Momentum Indicators:
# - rsi: RSI: Measures momentum to flag overbought/oversold conditions. Usage: Apply 70/30 thresholds and watch for divergence to signal reversals. Tips: In strong trends, RSI may remain extreme; always cross-check with trend analysis.

# Volatility Indicators:
# - boll: Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. Usage: Acts as a dynamic benchmark for price movement. Tips: Combine with the upper and lower bands to effectively spot breakouts or reversals.
# - boll_ub: Bollinger Upper Band: Typically 2 standard deviations above the middle line. Usage: Signals potential overbought conditions and breakout zones. Tips: Confirm signals with other tools; prices may ride the band in strong trends.
# - boll_lb: Bollinger Lower Band: Typically 2 standard deviations below the middle line. Usage: Indicates potential oversold conditions. Tips: Use additional analysis to avoid false reversal signals.
# - atr: ATR: Averages true range to measure volatility. Usage: Set stop-loss levels and adjust position sizes based on current market volatility. Tips: It's a reactive measure, so use it as part of a broader risk management strategy.

# Volume-Based Indicators:
# - vwma: VWMA: A moving average weighted by volume. Usage: Confirm trends by integrating price action with volume data. Tips: Watch for skewed results from volume spikes; use in combination with other volume analyses.

# - Select indicators that provide diverse and complementary information. Avoid redundancy (e.g., do not select both rsi and stochrsi). Also briefly explain why they are suitable for the given market context. When you tool call, please use the exact name of the indicators provided above as they are defined parameters, otherwise your call will fail. Please make sure to call get_stock_data first to retrieve the CSV that is needed to generate indicators. Then use get_indicators with the specific indicator names. Write a very detailed and nuanced report of the trends you observe. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."""
#             + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
#             + get_language_instruction()
#         )

#         prompt = ChatPromptTemplate.from_messages(
#             [
#                 (
#                     "system",
#                     "You are a helpful AI assistant, collaborating with other assistants."
#                     " Use the provided tools to progress towards answering the question."
#                     " If you are unable to fully answer, that's OK; another assistant with different tools"
#                     " will help where you left off. Execute what you can to make progress."
#                     " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
#                     " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
#                     " You have access to the following tools: {tool_names}.\n{system_message}"
#                     "For your reference, the current date is {current_date}. {instrument_context}",
#                 ),
#                 MessagesPlaceholder(variable_name="messages"),
#             ]
#         )

#         prompt = prompt.partial(system_message=system_message)
#         prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
#         prompt = prompt.partial(current_date=current_date)
#         prompt = prompt.partial(instrument_context=instrument_context)

#         chain = prompt | llm.bind_tools(tools)

#         result = chain.invoke(state["messages"])

#         report = ""

#         if len(result.tool_calls) == 0:
#             report = result.content

#         return {
#             "messages": [result],
#             "market_report": report,
#         }

#     return market_analyst_node
