"""
Financial Analysis Tool using yfinance
=======================================
Returns 4 DataFrames, each with a 3-level column MultiIndex:
    (period, metric_type)  where metric_type ∈ {value, yoy, qoq}

    income_stmt   – quarterly income statement
    balance_sheet – quarterly balance sheet
    cash_flow     – quarterly cash flow statement
    ratios        – key financial ratios per quarter

Usage
-----
    from financial_analysis import analyze_financials

    inc, bal, cf, ratios = analyze_financials("AAPL", n=8)

    # Raw revenue values
    inc.loc["Total Revenue", (slice(None), "value")]

    # YoY changes for all items
    inc.xs("yoy", axis=1, level=1)

    # All data for a single quarter
    inc["2024-09-30"]
"""

import warnings
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

try:
    import yfinance as yf
except ImportError:
    raise ImportError("请先安装 yfinance：pip install yfinance")


# ── constants ────────────────────────────────────────────────────────────────
DAYS_PER_QUARTER = 91.25

# Candidate row names for each concept (first match wins)
_ROWS = {
    "revenue":       ["Total Revenue", "Revenue"],
    "cogs":          ["Cost Of Revenue", "Cost of Revenue",
                      "Reconciled Cost Of Revenue"],
    "gross_profit":  ["Gross Profit"],
    "op_income":     ["Operating Income", "EBIT"],
    "net_income":    ["Net Income", "Net Income Common Stockholders"],
    "total_assets":  ["Total Assets"],
    "total_equity":  ["Stockholders Equity", "Common Stock Equity",
                      "Total Stockholders Equity"],
    "accounts_rec":  ["Accounts Receivable", "Net Receivables", "Receivables"],
    "inventory":     ["Inventory", "Inventories"],
    "accounts_pay":  ["Accounts Payable", "Payables And Accrued Expenses",
                      "Payables"],
    "cfo":           ["Operating Cash Flow", "Cash Flow From Operations",
                      "Total Cash From Operating Activities"],
}


# ── helpers ──────────────────────────────────────────────────────────────────

def _find_series(df: pd.DataFrame, candidates: list) -> pd.Series | None:
    """Return the first row that matches any candidate name, or None."""
    for name in candidates:
        if name in df.index:
            return df.loc[name]
    return None


def _build_changes(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Given a DataFrame (rows=accounts, cols=periods newest→oldest),
    return (yoy_df, qoq_df) with the same shape.

    YoY: col[i] vs col[i+4]   QoQ: col[i] vs col[i+1]
    Uses pandas .shift() along axis=1 for vectorised computation.
    """
    # Work with float64 so NaN propagates cleanly
    data = df.apply(pd.to_numeric, errors="coerce")

    # shift(k, axis=1) moves values k positions to the LEFT in column space,
    # i.e. prior[i] = data.iloc[:, i+k]  →  we shift the data rightward by k
    # Actually: data.shift(-k, axis=1) shifts columns left (newer period gets older value)
    # We want: pct_change[i] = (data[i] - data[i+k]) / |data[i+k]|
    # Equivalent: divide current by shifted-right version

    def _pct(shift: int) -> pd.DataFrame:
        prior = data.shift(-shift, axis=1)          # each cell gets value k periods older
        change = (data - prior) / prior.abs()
        return change

    yoy = _pct(4)
    qoq = _pct(1)
    return yoy, qoq


def _make_multiindex_df(data: pd.DataFrame,
                        yoy: pd.DataFrame,
                        qoq: pd.DataFrame,
                        periods: list[str]) -> pd.DataFrame:
    """
    Combine value / yoy / qoq into a single DataFrame with
    MultiIndex columns: (period, metric_type).
    """
    frames = {}
    for col_ts, period_label in zip(data.columns, periods):
        frames[(period_label, "value")] = data[col_ts]
        frames[(period_label, "yoy")]   = yoy[col_ts]   if col_ts in yoy.columns   else pd.Series(np.nan, index=data.index)
        frames[(period_label, "qoq")]   = qoq[col_ts]   if col_ts in qoq.columns   else pd.Series(np.nan, index=data.index)

    combined = pd.DataFrame(frames)
    combined.columns = pd.MultiIndex.from_tuples(combined.columns,
                                                  names=["period", "metric"])
    return combined


def _compute_ratios(inc: pd.DataFrame,
                    bal: pd.DataFrame,
                    cf:  pd.DataFrame,
                    all_cols: list,
                    display_cols: list,
                    periods: list[str]) -> pd.DataFrame:
    """
    Compute key financial ratios and return a MultiIndex DataFrame
    (same structure as the statement tables).
    """

    def _get(df, key) -> pd.Series:
        s = _find_series(df, _ROWS[key])
        if s is None:
            return pd.Series(np.nan, index=all_cols, dtype=float)
        return pd.to_numeric(s.reindex(all_cols), errors="coerce")

    rev  = _get(inc, "revenue")
    cogs = _get(inc, "cogs")
    gp   = _get(inc, "gross_profit")
    oi   = _get(inc, "op_income")
    ni   = _get(inc, "net_income")
    ta   = _get(bal, "total_assets")
    te   = _get(bal, "total_equity")
    ar   = _get(bal, "accounts_rec")
    inv  = _get(bal, "inventory")
    ap   = _get(bal, "accounts_pay")
    cfo  = _get(cf,  "cfo")

    # Fill gross profit from revenue - cogs where missing
    gp = gp.where(gp.notna(), rev - cogs)

    Q = DAYS_PER_QUARTER

    ratio_data = {
        "Gross Margin":      gp  / rev,
        "Operating Margin":  oi  / rev,
        "ROE":               ni  / te,
        "ROA":               ni  / ta,
        "DSO (days)":        ar  / (rev  / Q),
        "DIO (days)":        inv / (cogs / Q),
        "DPO (days)":        ap  / (cogs / Q),
        "Accrual Ratio":     (ni - cfo) / ta,
    }

    # CCC = DSO + DIO - DPO
    dso = ratio_data["DSO (days)"]
    dio = ratio_data["DIO (days)"]
    dpo = ratio_data["DPO (days)"]
    ratio_data["CCC (days)"] = dso + dio - dpo

    ratio_df = pd.DataFrame(ratio_data).T          # rows=ratios, cols=all_cols
    ratio_df = ratio_df[display_cols]               # trim to display window

    # YoY / QoQ for ratios (reuse same helper, but ratios are already rates —
    # so change = absolute difference, not %)
    def _ratio_pct(shift: int) -> pd.DataFrame:
        prior = ratio_df.shift(-shift, axis=1)
        return (ratio_df - prior) / prior.abs()

    ryoy = _ratio_pct(4)
    rqoq = _ratio_pct(1)

    return _make_multiindex_df(ratio_df, ryoy, rqoq, periods)


# ── main function ─────────────────────────────────────────────────────────────

def analyze_financials(
    ticker: str,
    n: int = 8,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Fetch quarterly financials and compute YoY / QoQ changes plus key ratios.

    Parameters
    ----------
    ticker : str   Stock ticker (e.g. "AAPL", "0700.HK")
    n      : int   Number of quarterly periods to return. Capped at available data.

    Returns
    -------
    income_stmt   : pd.DataFrame  MultiIndex (period, metric) columns
    balance_sheet : pd.DataFrame  MultiIndex (period, metric) columns
    cash_flow     : pd.DataFrame  MultiIndex (period, metric) columns
    ratios        : pd.DataFrame  MultiIndex (period, metric) columns

    Column metric levels: "value", "yoy", "qoq"
    - value : raw number (currency units from yfinance)
    - yoy   : (current - same_q_last_year) / |same_q_last_year|,  NaN if insufficient history
    - qoq   : (current - prior_quarter)    / |prior_quarter|,      NaN if insufficient history

    Ratio yoy/qoq use absolute-difference / |prior| (since ratios are already scaled).
    """
    tk = yf.Ticker(ticker)

    inc_raw = tk.quarterly_income_stmt    # rows=accounts, cols=Timestamps newest→oldest
    bal_raw = tk.quarterly_balance_sheet
    cf_raw  = tk.quarterly_cashflow

    if inc_raw is None or inc_raw.empty:
        raise ValueError(
            f"No quarterly income statement data for '{ticker}'. "
            "Check the ticker symbol or your network connection."
        )

    all_cols = inc_raw.columns.tolist()          # all available periods
    n_periods = min(n, len(all_cols))
    display_cols = all_cols[:n_periods]          # periods we'll show
    periods = [str(c)[:10] for c in display_cols]

    # Align all statements to the same full column set (NaN-fill missing cols)
    def _align(raw: pd.DataFrame) -> pd.DataFrame:
        if raw is None or raw.empty:
            return pd.DataFrame(np.nan, index=[], columns=all_cols)
        return raw.reindex(columns=all_cols)

    inc = _align(inc_raw)
    bal = _align(bal_raw)
    cf  = _align(cf_raw)

    # ── YoY / QoQ for each statement ────────────────────────────────────────
    inc_yoy, inc_qoq = _build_changes(inc)
    bal_yoy, bal_qoq = _build_changes(bal)
    cf_yoy,  cf_qoq  = _build_changes(cf)

    # ── Trim to display window and build MultiIndex DataFrames ───────────────
    inc_out = _make_multiindex_df(inc[display_cols], inc_yoy[display_cols], inc_qoq[display_cols], periods)
    bal_out = _make_multiindex_df(bal[display_cols], bal_yoy[display_cols], bal_qoq[display_cols], periods)
    cf_out  = _make_multiindex_df(cf[display_cols],  cf_yoy[display_cols],  cf_qoq[display_cols],  periods)

    # ── Ratios ───────────────────────────────────────────────────────────────
    rat_out = _compute_ratios(inc, bal, cf, all_cols, display_cols, periods)

    return inc_out, bal_out, cf_out, rat_out


# ── display helpers ───────────────────────────────────────────────────────────

def _fmt_value(v):
    """Format raw financial value (large numbers → B/M)."""
    if pd.isna(v):
        return "N/A"
    abs_v = abs(v)
    if abs_v >= 1e9:
        return f"{v/1e9:.2f}B"
    if abs_v >= 1e6:
        return f"{v/1e6:.1f}M"
    return f"{v:.0f}"


def _fmt_pct(v):
    if pd.isna(v):
        return "N/A"
    return f"{v*100:+.1f}%"


def _fmt_days(v):
    if pd.isna(v):
        return "N/A"
    return f"{v:.1f}d"


_RATIO_DAYS = {"DSO (days)", "DIO (days)", "DPO (days)", "CCC (days)"}
_RATIO_PCT  = {"Gross Margin", "Operating Margin", "ROE", "ROA", "Accrual Ratio"}


def print_statement(df: pd.DataFrame, title: str, is_ratio: bool = False):
    """Pretty-print a MultiIndex financial DataFrame."""
    periods = df.columns.get_level_values("period").unique().tolist()
    width = max(len(title), 30)

    print(f"\n{'═'*max(80, len(periods)*26)}")
    print(f"  {title}  ({len(periods)} quarters)")
    print(f"{'═'*max(80, len(periods)*26)}")

    # Build display table: for each row, show value / yoy / qoq per period
    rows = []
    for idx in df.index:
        for metric in ("value", "yoy", "qoq"):
            label = f"  {idx}" if metric == "value" else f"    └─ {metric.upper()}"
            row_data = {"Account": label}
            for p in periods:
                try:
                    v = df.loc[idx, (p, metric)]
                except KeyError:
                    v = np.nan
                if metric == "value":
                    if is_ratio:
                        if idx in _RATIO_DAYS:
                            row_data[p] = _fmt_days(v)
                        else:
                            row_data[p] = _fmt_pct(v) if not pd.isna(v) else "N/A"
                    else:
                        row_data[p] = _fmt_value(v)
                else:  # yoy / qoq are always % changes
                    if is_ratio and idx in _RATIO_DAYS:
                        row_data[p] = _fmt_days(v)   # absolute day difference
                    else:
                        row_data[p] = _fmt_pct(v)
            rows.append(row_data)

    display_df = pd.DataFrame(rows).set_index("Account")
    print(display_df.to_string())


def print_report(ticker: str, n: int = 8):
    """Fetch and print all four tables for a ticker."""
    print(f"\nFetching {n} quarters of data for {ticker.upper()} …")
    inc, bal, cf, ratios = analyze_financials(ticker, n)

    print_statement(inc,    f"Income Statement — {ticker.upper()}")
    print_statement(bal,    f"Balance Sheet — {ticker.upper()}")
    print_statement(cf,     f"Cash Flow Statement — {ticker.upper()}")
    print_statement(ratios, f"Key Ratios — {ticker.upper()}", is_ratio=True)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    n      = int(sys.argv[2]) if len(sys.argv) > 2 else 8

    print_report(ticker, n)

    # # Optional Excel export
    # if "--excel" in sys.argv:
    #     inc, bal, cf, ratios = analyze_financials(ticker, n)
    #     out = f"{ticker.upper()}_financials.xlsx"
    #     with pd.ExcelWriter(out, engine="openpyxl") as writer:
    #         inc.to_excel(writer,    sheet_name="Income Stmt")
    #         bal.to_excel(writer,    sheet_name="Balance Sheet")
    #         cf.to_excel(writer,     sheet_name="Cash Flow")
    #         ratios.to_excel(writer, sheet_name="Ratios")
    #     print(f"\nExported to {out}")