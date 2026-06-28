"""Data analysis tools."""

from __future__ import annotations

import ast
import operator
from pathlib import Path
from typing import Any

import pandas as pd

from tradingagents.equity_research.tools.workspace_utils import get_document_root, resolve_safe_path

_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_safe_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    raise ValueError("Unsupported expression")


def calculator(expression: str, data: dict | None = None) -> dict[str, Any]:
    if data:
        expr = expression
        for key, val in data.items():
            expr = expr.replace(f"{{{key}}}", str(val))
        expression = expr
    tree = ast.parse(expression, mode="eval")
    result = _safe_eval(tree.body)
    return {"expression": expression, "result": result}


def csv_reader(path: str) -> dict[str, Any]:
    file_path = resolve_safe_path(path)
    df = pd.read_csv(file_path)
    return {
        "path": str(file_path),
        "rows": len(df),
        "columns": list(df.columns),
        "head": df.head(5).to_dict(orient="records"),
        "dtypes": {c: str(t) for c, t in df.dtypes.items()},
    }


def dataframe_profiler(path: str) -> dict[str, Any]:
    file_path = resolve_safe_path(path)
    df = pd.read_csv(file_path) if file_path.suffix.lower() == ".csv" else pd.read_json(file_path)
    missing = {c: int(df[c].isna().sum()) for c in df.columns}
    return {
        "path": str(file_path),
        "schema": list(df.columns),
        "dtypes": {c: str(t) for c, t in df.dtypes.items()},
        "missing": missing,
        "describe": df.describe(include="all").fillna("").to_dict(),
    }


def chart_generator(data: list[dict] | dict, chart_spec: dict) -> dict[str, Any]:
    import matplotlib.pyplot as plt

    root = get_document_root() / "artifacts"
    root.mkdir(parents=True, exist_ok=True)
    chart_type = chart_spec.get("type", "line")
    x_key = chart_spec.get("x", "x")
    y_key = chart_spec.get("y", "y")
    rows = data if isinstance(data, list) else data.get("rows", [])
    xs = [r.get(x_key) for r in rows]
    ys = [r.get(y_key) for r in rows]
    fig, ax = plt.subplots()
    if chart_type == "bar":
        ax.bar(xs, ys)
    else:
        ax.plot(xs, ys)
    ax.set_title(chart_spec.get("title", ""))
    out = root / (chart_spec.get("filename") or "chart.png")
    fig.savefig(out)
    plt.close(fig)
    return {"path": str(out)}


def statistical_test(data: list[float] | dict, test_type: str = "ttest") -> dict[str, Any]:
    from scipy import stats

    values = data if isinstance(data, list) else data.get("values", [])
    if test_type == "ttest" and len(values) >= 2:
        mid = len(values) // 2
        stat, pvalue = stats.ttest_ind(values[:mid], values[mid:])
        return {"test_type": test_type, "statistic": float(stat), "pvalue": float(pvalue)}
    return {"test_type": test_type, "error": "insufficient data"}


def regression_runner(data: list[dict], formula: str) -> dict[str, Any]:
    try:
        import statsmodels.formula.api as smf
    except ImportError:
        return {"error": "statsmodels not installed"}
    df = pd.DataFrame(data)
    model = smf.ols(formula=formula, data=df).fit()
    return {"formula": formula, "summary": str(model.summary()), "params": model.params.to_dict()}


def time_series_analyzer(data: list[dict], date_key: str = "date", value_key: str = "value") -> dict[str, Any]:
    df = pd.DataFrame(data)
    if date_key in df.columns:
        df[date_key] = pd.to_datetime(df[date_key], errors="coerce")
        df = df.sort_values(date_key)
    values = df[value_key].dropna().astype(float)
    if len(values) < 2:
        return {"trend": "insufficient data"}
    trend = "up" if values.iloc[-1] > values.iloc[0] else "down"
    return {
        "trend": trend,
        "start": float(values.iloc[0]),
        "end": float(values.iloc[-1]),
        "change_pct": float((values.iloc[-1] - values.iloc[0]) / values.iloc[0] * 100) if values.iloc[0] else 0,
    }
