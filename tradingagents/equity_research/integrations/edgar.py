"""SEC EDGAR filing access via edgartools."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class EdgarClient:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.user_agent = os.environ.get(
            "SEC_EDGAR_USER_AGENT",
            "TradingAgents EquityResearch research@example.com",
        )

    def fetch_recent_filings(self, ticker: str, form_types: list[str] | None = None) -> list[dict[str, Any]]:
        form_types = form_types or ["10-K", "10-Q", "8-K"]
        try:
            from edgar import Company, set_identity

            set_identity(self.user_agent)
            company = Company(ticker)
            filings = []
            for form in form_types:
                try:
                    filing = company.get_filings(form=form).latest(1)
                    if filing:
                        filings.append({
                            "form": form,
                            "filing_date": str(getattr(filing, "filing_date", "")),
                            "accession_number": str(getattr(filing, "accession_number", "")),
                            "url": str(getattr(filing, "filing_url", getattr(filing, "homepage_url", ""))),
                            "text_excerpt": self._safe_text(filing, max_chars=8000),
                        })
                except Exception as exc:
                    logger.debug("EDGAR fetch %s for %s failed: %s", form, ticker, exc)
            return filings
        except ImportError:
            logger.warning("edgartools not installed; EDGAR fetch skipped")
            return []
        except Exception as exc:
            logger.warning("EDGAR fetch failed for %s: %s", ticker, exc)
            return []

    @staticmethod
    def _safe_text(filing, max_chars: int = 8000) -> str:
        try:
            text = filing.text() if callable(getattr(filing, "text", None)) else str(filing)
            return text[:max_chars] if text else ""
        except Exception:
            return ""
