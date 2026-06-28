"""LangChain data analysis tools."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.tools import tool

from tradingagents.equity_research.tools import data_tools


@tool
def csv_reader(path: Annotated[str, "Path to CSV file"]) -> dict[str, Any]:
    """Read a CSV file and return schema summary."""
    return data_tools.csv_reader(path)


@tool
def dataframe_profiler(path: Annotated[str, "Path to CSV or JSON data file"]) -> dict[str, Any]:
    """Profile dataframe schema, dtypes, missing values, and stats."""
    return data_tools.dataframe_profiler(path)


@tool
def calculator(
    expression: Annotated[str, "Numeric expression, e.g. (1+2)*3"],
    data: Annotated[dict | None, "Optional variable map for {name} substitution"] = None,
) -> dict[str, Any]:
    """Evaluate a safe numeric expression."""
    return data_tools.calculator(expression, data=data)


@tool
def chart_generator(
    data: Annotated[list[dict] | dict, "Chart data rows"],
    chart_spec: Annotated[dict, "Chart spec with type, x, y, title, filename"],
) -> dict[str, Any]:
    """Generate a chart image file from data."""
    return data_tools.chart_generator(data, chart_spec)


@tool
def statistical_test(
    data: Annotated[list[float] | dict, "Numeric sample data"],
    test_type: Annotated[str, "Statistical test name, e.g. ttest"] = "ttest",
) -> dict[str, Any]:
    """Run a statistical test on numeric data."""
    return data_tools.statistical_test(data, test_type=test_type)


@tool
def regression_runner(
    data: Annotated[list[dict], "Regression dataset rows"],
    formula: Annotated[str, "Statsmodels formula, e.g. y ~ x1 + x2"],
) -> dict[str, Any]:
    """Run OLS regression analysis."""
    return data_tools.regression_runner(data, formula)


@tool
def time_series_analyzer(
    data: Annotated[list[dict], "Time series rows with date and value fields"],
    date_key: Annotated[str, "Date column name"] = "date",
    value_key: Annotated[str, "Value column name"] = "value",
) -> dict[str, Any]:
    """Analyze time series trend and change."""
    return data_tools.time_series_analyzer(data, date_key=date_key, value_key=value_key)
