"""Shared vendor-chain routing for dataflows and equity research tools."""

from __future__ import annotations

import logging
from typing import Any, Callable

from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.errors import (
    NoMarketDataError,
    VendorNotConfiguredError,
    VendorRateLimitError,
)

logger = logging.getLogger("tradingagents.dataflows.interface")

DEFAULT_VENDOR_ORDER: dict[str, list[str]] = {}


def _is_empty_result(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        return not stripped or stripped.startswith("NO_DATA_AVAILABLE")
    if isinstance(value, (list, tuple, dict)):
        return len(value) == 0
    return False


def resolve_vendor_config(
    method: str,
    category: str | None,
    *,
    config: dict | None = None,
    equity_override: bool = False,
) -> str | None:
    """Resolve vendor chain config string from layered overrides."""
    cfg = config or get_config()
    er = cfg.get("equity_research") or {}

    if equity_override:
        er_tool = (er.get("tool_vendors") or {}).get(method)
        if er_tool:
            return er_tool
        if category:
            er_cat = (er.get("data_vendors") or {}).get(category)
            if er_cat:
                return er_cat

    tool_vendors = cfg.get("tool_vendors") or {}
    if method in tool_vendors:
        return tool_vendors[method]

    if category:
        data_vendors = cfg.get("data_vendors") or {}
        if category in data_vendors:
            return data_vendors[category]

    defaults = DEFAULT_VENDOR_ORDER.get(method)
    if defaults:
        return ",".join(defaults)

    return None


def build_vendor_chain(
    method: str,
    available: dict[str, Callable[..., Any]],
    *,
    category: str | None = None,
    config: dict | None = None,
    equity_override: bool = False,
) -> list[str]:
    """Build ordered vendor chain from config and available implementations."""
    vendor_config = resolve_vendor_config(
        method,
        category,
        config=config,
        equity_override=equity_override,
    )
    all_available = list(available.keys())

    if vendor_config:
        primary_vendors = [v.strip() for v in vendor_config.split(",")]
        explicit = [v for v in primary_vendors if v and v != "default"]
        if explicit:
            vendor_chain = [v for v in explicit if v in available]
            if not vendor_chain:
                raise ValueError(
                    f"Configured vendor(s) {explicit} not available for '{method}'. "
                    f"Available: {all_available}."
                )
            return vendor_chain

    defaults = DEFAULT_VENDOR_ORDER.get(method)
    if defaults:
        chain = [v for v in defaults if v in available]
        if chain:
            return chain

    return all_available


def _format_no_data_message(last_no_data: NoMarketDataError, method: str) -> str:
    sym = last_no_data.symbol
    canonical = last_no_data.canonical
    resolved = "" if canonical == sym else f" (resolved to '{canonical}')"
    reason = f" ({last_no_data.detail})" if last_no_data.detail else ""
    return (
        f"NO_DATA_AVAILABLE: No usable data for '{sym}'{resolved} from "
        f"any configured vendor for '{method}'{reason}. Do not estimate or "
        f"fabricate values — report that data is unavailable."
    )


def execute_vendor_chain(
    method: str,
    vendor_chain: list[str],
    implementations: dict[str, Callable[..., Any]],
    *args,
    wrap_metadata: bool = False,
    no_data_as_string: bool = True,
    **kwargs,
) -> Any:
    """Execute vendors in order with standard fallback semantics."""
    last_no_data: NoMarketDataError | None = None
    first_error: Exception | None = None
    fallback_attempted: list[str] = []

    for vendor in vendor_chain:
        if vendor not in implementations:
            continue
        impl = implementations[vendor]
        impl_func = impl[0] if isinstance(impl, list) else impl
        fallback_attempted.append(vendor)

        try:
            result = impl_func(*args, **kwargs)
            if _is_empty_result(result):
                last_no_data = NoMarketDataError(
                    symbol=kwargs.get("ticker", kwargs.get("query", method)),
                    detail="empty result",
                )
                continue
            if wrap_metadata:
                if isinstance(result, dict) and "vendor_used" not in result:
                    return {
                        **result,
                        "vendor_used": vendor,
                        "fallback_attempted": list(fallback_attempted),
                    }
                if not isinstance(result, dict):
                    return {
                        "data": result,
                        "vendor_used": vendor,
                        "fallback_attempted": list(fallback_attempted),
                    }
            return result
        except VendorRateLimitError:
            logger.warning("Vendor %r rate-limited for %s; trying next vendor.", vendor, method)
            continue
        except VendorNotConfiguredError as exc:
            logger.warning("Vendor %r not configured for %s; trying next vendor.", vendor, method)
            if first_error is None:
                first_error = exc
            continue
        except NoMarketDataError as exc:
            last_no_data = exc
            continue
        except Exception as exc:
            logger.warning("Vendor %r failed for %s: %s", vendor, method, exc)
            if first_error is None:
                first_error = exc
            continue

    if last_no_data is not None:
        if first_error is not None:
            logger.warning(
                "Returning NO_DATA for %s, but a vendor errored earlier: %s",
                method,
                first_error,
            )
        if no_data_as_string:
            return _format_no_data_message(last_no_data, method)
        if wrap_metadata:
            return {
                "data": None,
                "error": _format_no_data_message(last_no_data, method),
                "fallback_attempted": fallback_attempted,
            }
        raise last_no_data

    if first_error is not None:
        raise first_error

    raise RuntimeError(f"No available vendor for '{method}'")
