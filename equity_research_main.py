#!/usr/bin/env python3
"""Example entry point for Deep Equity Research (MVP1)."""

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.equity_research import EquityResearchGraph


def main():
    config = DEFAULT_CONFIG.copy()
    # config["llm_provider"] = "openai"
    graph = EquityResearchGraph(debug=True, config=config, init_database=True)
    ticker = "NVDA"
    final_state, summary = graph.propagate(ticker)
    print(f"Report generated for {ticker}")
    print(f"Rating: {final_state.get('rating')} | Target: {final_state.get('target_price')}")
    print(summary[:800] if summary else "No summary")
    if final_state.get("final_report"):
        print("\n--- Report excerpt ---\n")
        print(final_state["final_report"][:2000])


if __name__ == "__main__":
    main()
