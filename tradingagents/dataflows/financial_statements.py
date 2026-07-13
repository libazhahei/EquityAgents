"""Structured financial statements with YoY / QoQ as markdown tables.

Used by equity-research ``financial_statement_fetch`` only. Leaves the legacy
CSV-string APIs in ``y_finance.py`` unchanged.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

from tradingagents.dataflows.stockstats_utils import yf_retry
from tradingagents.dataflows.symbol_utils import NoMarketDataError, normalize_symbol

_ANNUAL_PERIODS = 3
_QUARTERLY_PERIODS = 12


def fetch_financial_statements_markdown(
    ticker: str,
    period: str = "annual",
) -> dict[str, Any]:
    """Fetch income / balance / cash-flow statements as wide markdown tables.

    Annual: last 3 fiscal years with value + YoY columns.
    Quarterly: last 12 quarters with value + YoY + QoQ columns.
    Growth cells are formatted as percentages (e.g. ``+25.0%``).
    """
    freq = "annual" if str(period).lower().startswith("a") else "quarterly"
    canonical = normalize_symbol(ticker)
    tk = yf.Ticker(canonical)

    if freq == "annual":
        inc_raw = yf_retry(lambda: tk.income_stmt)
        bal_raw = yf_retry(lambda: tk.balance_sheet)
        cf_raw = yf_retry(lambda: tk.cashflow)
        n_display = _ANNUAL_PERIODS
        include_qoq = False
        yoy_shift = 1
    else:
        inc_raw = yf_retry(lambda: tk.quarterly_income_stmt)
        bal_raw = yf_retry(lambda: tk.quarterly_balance_sheet)
        cf_raw = yf_retry(lambda: tk.quarterly_cashflow)
        n_display = _QUARTERLY_PERIODS
        include_qoq = True
        yoy_shift = 4

    if inc_raw is None or getattr(inc_raw, "empty", True):
        raise NoMarketDataError(ticker, canonical, f"no {freq} income statement data")

    # Align all statements to the income-statement column set (newest → oldest).
    all_cols = list(inc_raw.columns)
    n_display = min(n_display, len(all_cols))
    display_cols = all_cols[:n_display]

    def _align(raw: pd.DataFrame | None) -> pd.DataFrame:
        if raw is None or getattr(raw, "empty", True):
            return pd.DataFrame(np.nan, index=[], columns=all_cols)
        return raw.reindex(columns=all_cols)

    income = _statement_to_markdown(
        _align(inc_raw), display_cols, yoy_shift=yoy_shift, include_qoq=include_qoq
    )
    balance = _statement_to_markdown(
        _align(bal_raw), display_cols, yoy_shift=yoy_shift, include_qoq=include_qoq
    )
    cash_flow = _statement_to_markdown(
        _align(cf_raw), display_cols, yoy_shift=yoy_shift, include_qoq=include_qoq
    )

    return {
        "ticker": canonical,
        "period": freq,
        "income_statement": income,
        "balance_sheet": balance,
        "cash_flow": cash_flow,
    }


def _statement_to_markdown(
    data: pd.DataFrame,
    display_cols: list,
    *,
    yoy_shift: int,
    include_qoq: bool,
) -> str:
    if data.empty or not display_cols:
        return "_No data available._"

    numeric = data.apply(pd.to_numeric, errors="coerce")
    yoy = _pct_change(numeric, yoy_shift)
    qoq = _pct_change(numeric, 1) if include_qoq else None

    periods = [str(c)[:10] for c in display_cols]
    headers = ["Line Item"]
    for p in periods:
        headers.append(p)
        headers.append(f"{p} YoY")
        if include_qoq:
            headers.append(f"{p} QoQ")

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for idx in numeric.index:
        row = [str(idx)]
        for col in display_cols:
            val = numeric.at[idx, col] if col in numeric.columns else np.nan
            yoy_val = yoy.at[idx, col] if col in yoy.columns else np.nan
            row.append(_fmt_value(val))
            row.append(_fmt_pct(yoy_val))
            if include_qoq and qoq is not None:
                qoq_val = qoq.at[idx, col] if col in qoq.columns else np.nan
                row.append(_fmt_pct(qoq_val))
        # Escape pipes in line-item names so markdown tables stay intact.
        row[0] = row[0].replace("|", "\\|")
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def _pct_change(data: pd.DataFrame, shift: int) -> pd.DataFrame:
    """(current - prior) / |prior|; columns are newest → oldest."""
    prior = data.shift(-shift, axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        change = (data - prior) / prior.abs()
    return change


def _fmt_value(v: Any) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)) or pd.isna(v):
        return "N/A"
    try:
        num = float(v)
    except (TypeError, ValueError):
        return str(v)
    abs_v = abs(num)
    if abs_v >= 1e9:
        return f"{num / 1e9:.2f}B"
    if abs_v >= 1e6:
        return f"{num / 1e6:.1f}M"
    if abs_v >= 1e3:
        return f"{num / 1e3:.1f}K"
    if abs_v == 0:
        return "0"
    if abs_v < 1:
        return f"{num:.4f}"
    return f"{num:.2f}"


def _fmt_pct(v: Any) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)) or pd.isna(v):
        return "N/A"
    try:
        return f"{float(v) * 100:+.1f}%"
    except (TypeError, ValueError):
        return "N/A"
