"""Pluggable external information source registry."""

from __future__ import annotations

from typing import Any, Protocol


class InfoSource(Protocol):
    name: str

    def fetch(self, ticker: str, query: str, **kwargs: Any) -> dict[str, Any]: ...


class YFinanceInfoSource:
    name = "yfinance"

    def fetch(self, ticker: str, query: str, **kwargs: Any) -> dict[str, Any]:
        try:
            import yfinance as yf

            info = yf.Ticker(ticker).info
            return {
                "source": self.name,
                "query": query,
                "data": {
                    "sector": info.get("sector"),
                    "industry": info.get("industry"),
                    "market_cap": info.get("marketCap"),
                    "trailing_pe": info.get("trailingPE"),
                    "forward_pe": info.get("forwardPE"),
                    "revenue_growth": info.get("revenueGrowth"),
                },
            }
        except Exception as exc:
            return {"source": self.name, "query": query, "error": str(exc)}


class InfoSourceRegistry:
    def __init__(self):
        self._sources: dict[str, InfoSource] = {}

    def register(self, source: InfoSource) -> None:
        self._sources[source.name] = source

    def fetch_all(self, ticker: str, query: str) -> list[dict[str, Any]]:
        return [s.fetch(ticker, query) for s in self._sources.values()]


def default_registry() -> InfoSourceRegistry:
    reg = InfoSourceRegistry()
    reg.register(YFinanceInfoSource())
    return reg
