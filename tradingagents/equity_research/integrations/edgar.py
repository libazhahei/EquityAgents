"""SEC EDGAR filing access via edgartools."""

from __future__ import annotations

import logging
import os
from typing import Any, Literal

logger = logging.getLogger(__name__)

FilingSection = Literal[
    "full",
    "financial_statements",
    "income_statement",
    "balance_sheet",
    "cash_flow",
    "mda",
    "risk_factors",
    "business",
]

_SECTION_ACCESSORS: dict[str, tuple[str, ...]] = {
    "income_statement": ("income_statement",),
    "balance_sheet": ("balance_sheet",),
    "cash_flow": ("cash_flow_statement", "cashflow_statement"),
    "financial_statements": ("income_statement", "balance_sheet", "cash_flow_statement", "cashflow_statement"),
    "mda": ("management_discussion",),
    "risk_factors": ("risk_factors",),
    "business": ("business",),
}


class EdgarClient:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.user_agent = os.environ.get(
            "SEC_EDGAR_USER_AGENT",
            "TradingAgents EquityResearch research@example.com",
        )

    def _set_identity(self) -> None:
        from edgar import set_identity

        set_identity(self.user_agent)

    @staticmethod
    def _full_text(filing) -> str:
        try:
            text = filing.text() if callable(getattr(filing, "text", None)) else str(filing)
            return text or ""
        except Exception:
            return ""

    @staticmethod
    def _safe_text(filing, max_chars: int = 8000) -> str:
        text = EdgarClient._full_text(filing)
        return text[:max_chars] if text else ""

    @staticmethod
    def _section_text(obj: Any, section: str) -> str:
        if section == "full" or not section:
            return ""
        keys = _SECTION_ACCESSORS.get(section, ())
        parts: list[str] = []
        for key in keys:
            value = getattr(obj, key, None)
            if value is None and hasattr(obj, "financials") and obj.financials:
                value = getattr(obj.financials, key, None)
            if value is not None:
                parts.append(str(value))
        if not parts and hasattr(obj, "get_section_text"):
            try:
                label = section.replace("_", " ").title()
                parts.append(str(obj.get_section_text(label)))
            except Exception:
                pass
        return "\n\n".join(parts)

    def read_filing_section(
        self,
        *,
        filing_url: str | None = None,
        accession_number: str | None = None,
        section: FilingSection | str = "full",
    ) -> dict[str, Any]:
        section = section or "full"
        try:
            from edgar import Filing

            self._set_identity()
            filing = None
            if accession_number:
                filing = Filing(accession_number)
            elif filing_url:
                filing = Filing(filing_url)
            if not filing:
                return {"error": "filing_url or accession_number required", "section": section}

            result: dict[str, Any] = {
                "form": str(getattr(filing, "form", "")),
                "filing_date": str(getattr(filing, "filing_date", "")),
                "accession_number": str(getattr(filing, "accession_number", "")),
                "url": str(getattr(filing, "filing_url", getattr(filing, "homepage_url", filing_url or ""))),
                "section": section,
            }
            if section == "full":
                result["text_excerpt"] = self._safe_text(filing)
                return result

            obj = filing.obj() if callable(getattr(filing, "obj", None)) else None
            if obj is not None:
                excerpt = self._section_text(obj, section)
                if excerpt:
                    result["text_excerpt"] = excerpt[:12000]
                    return result
            result["text_excerpt"] = self._safe_text(filing, max_chars=12000)
            return result
        except ImportError:
            logger.warning("edgartools not installed; EDGAR fetch skipped")
            return {"error": "edgartools not installed", "section": section}
        except Exception as exc:
            logger.warning("EDGAR section read failed: %s", exc)
            return {"error": str(exc), "section": section}

    def fetch_recent_filings(
        self,
        ticker: str,
        form_types: list[str] | None = None,
        *,
        section: FilingSection | str | None = None,
    ) -> list[dict[str, Any]]:
        form_types = form_types or ["10-K", "10-Q", "8-K"]
        section = section or "full"
        try:
            from edgar import Company

            self._set_identity()
            company = Company(ticker)
            filings = []
            for form in form_types:
                try:
                    filing = company.get_filings(form=form).latest(1)
                    if not filing:
                        continue
                    entry: dict[str, Any] = {
                        "form": form,
                        "filing_date": str(getattr(filing, "filing_date", "")),
                        "accession_number": str(getattr(filing, "accession_number", "")),
                        "url": str(getattr(filing, "filing_url", getattr(filing, "homepage_url", ""))),
                        "section": section,
                    }
                    if section and section != "full":
                        obj = filing.obj() if callable(getattr(filing, "obj", None)) else None
                        excerpt = self._section_text(obj, section) if obj else ""
                        full_text = excerpt or self._full_text(filing)
                        entry["full_text"] = full_text
                        entry["text_excerpt"] = (excerpt[:12000] if excerpt else full_text[:8000]) if full_text else ""
                    else:
                        full_text = self._full_text(filing)
                        entry["full_text"] = full_text
                        entry["text_excerpt"] = full_text[:8000] if full_text else ""
                    filings.append(entry)
                except Exception as exc:
                    logger.debug("EDGAR fetch %s for %s failed: %s", form, ticker, exc)
            return filings
        except ImportError:
            logger.warning("edgartools not installed; EDGAR fetch skipped")
            return []
        except Exception as exc:
            logger.warning("EDGAR fetch failed for %s: %s", ticker, exc)
            return []

    def fetch_filings_by_year(
        self,
        ticker: str,
        year: int,
        form_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch all filings for a ticker in a calendar year (full text)."""
        form_types = form_types or ["10-K", "10-Q", "8-K"]
        try:
            from edgar import Company

            self._set_identity()
            company = Company(ticker)
            filings: list[dict[str, Any]] = []
            seen_accessions: set[str] = set()

            for form in form_types:
                try:
                    entity_filings = company.get_filings(
                        year=year,
                        form=form,
                        trigger_full_load=True,
                    )
                    for filing in entity_filings:
                        accession = str(getattr(filing, "accession_number", ""))
                        if not accession or accession in seen_accessions:
                            continue
                        seen_accessions.add(accession)
                        form_label = str(getattr(filing, "form", form))
                        full_text = self._full_text(filing)
                        filings.append(
                            {
                                "form": form_label,
                                "filing_date": str(getattr(filing, "filing_date", "")),
                                "accession_number": accession,
                                "url": str(
                                    getattr(
                                        filing,
                                        "filing_url",
                                        getattr(filing, "homepage_url", ""),
                                    )
                                ),
                                "section": "full",
                                "full_text": full_text,
                                "text_excerpt": full_text[:8000] if full_text else "",
                                "fiscal_year": year,
                            }
                        )
                except Exception as exc:
                    logger.debug("EDGAR fetch %s for %s year %s failed: %s", form, ticker, year, exc)

            filings.sort(key=lambda f: (f.get("filing_date", ""), f.get("form", "")))
            return filings
        except ImportError:
            logger.warning("edgartools not installed; EDGAR fetch skipped")
            return []
        except Exception as exc:
            logger.warning("EDGAR year fetch failed for %s %s: %s", ticker, year, exc)
            return []
