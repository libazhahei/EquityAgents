"""SEC EDGAR filing access via edgartools."""

from __future__ import annotations

import json
import logging
import math
import os
import re
from pathlib import Path
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
    "toc",
    "tables",   # NEW: list / render tables beyond the standard 3 statements
]

_SECTION_ACCESSORS: dict[str, tuple[str, ...]] = {
    "income_statement": ("income_statement",),
    "balance_sheet": ("balance_sheet",),
    "cash_flow": ("cash_flow_statement", "cashflow_statement", "cash_flows"),
    "financial_statements": (
        "income_statement",
        "balance_sheet",
        "cash_flow_statement",
        "cashflow_statement",
        "cash_flows",
    ),
    "mda": ("management_discussion", "item_7", "Item 7"),
    "risk_factors": ("risk_factors", "item_1a", "Item 1A"),
    "business": ("business", "item_1", "Item 1"),
}


class SecCacheKey:
    @staticmethod
    def cache_dir(cache_root: Path, ticker: str) -> Path:
        return cache_root / "equity_research" / "sec" / ticker.upper()

    @staticmethod
    def file_path(dir_path: Path, filing: dict[str, Any]) -> Path:
        form = filing.get("form", "filing")
        accession = str(filing.get("accession_number", "")).replace("/", "-")
        suffix = accession or str(filing.get("filing_date", "unknown")).replace("/", "-")
        return dir_path / f"{form}_{suffix}.json"


class EdgarClient:
    CHUNK_CHARS = 30_000
    _EXTERNAL_TO_ITEM: dict[str, str] = {
        "business": "Item 1",
        "risk_factors": "Item 1A",
        "mda": "Item 7",
        "financial_statements": "Item 8",
        "income_statement": "Item 8",
        "balance_sheet": "Item 8",
        "cash_flow": "Item 8",
        "cash_flow_statement": "Item 8",
        "cashflow_statement": "Item 8",
    }
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.user_agent = os.environ.get(
            "SEC_EDGAR_USER_AGENT",
            "TradingAgents EquityResearch research@example.com",
        )
        cache_enabled = self.config.get("enable_edgar_cache")
        cache_dir_cfg = self.config.get("data_cache_dir")
        self._cache_enabled = bool(cache_enabled and cache_dir_cfg)
        self._cache_root = Path(str(cache_dir_cfg)) if cache_dir_cfg else None

    # ------------------------------------------------------------------ cache

    def _get_section_cached(self, accession_number: str) -> dict[str, Any] | None:
        if not self._cache_enabled:
            return None
        try:
            path = Path(self._cache_root) / f".edgar_section_cache_{accession_number}.json"
            raw = path.read_text(encoding="utf-8")
            entry = json.loads(raw)
            logger.debug("EDGAR section cache hit: %s", accession_number)
            return entry
        except Exception:
            return None

    def _put_section_cached(self, accession_number: str, entry: dict[str, Any]) -> None:
        if not self._cache_enabled:
            return
        try:
            path = Path(self._cache_root) / f".edgar_section_cache_{accession_number}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            logger.debug("Failed to cache EDGAR section result: %s", accession_number, exc_info=True)

    # ------------------------------------------------------------------ helpers

    def _set_identity(self) -> None:
        from edgar import set_identity
        set_identity(self.user_agent)

    @staticmethod
    def _full_text(filing: Any) -> str:
        try:
            text = filing.text() if callable(getattr(filing, "text", None)) else str(filing)
            return text or ""
        except Exception:
            return ""

    @staticmethod
    def _safe_text(filing: Any, max_chars: int = 8000) -> str:
        return EdgarClient._full_text(filing)[:max_chars]

    @staticmethod
    def _section_text(obj: Any, section: str) -> str:
        if section == "full" or not section:
            return ""
        keys = EdgarClient._EXTERNAL_TO_ITEM.get(section, ())
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

    # -- loading a filing object -----------------------------------------------

    @staticmethod
    def _extract_year_from_accession(accession_number: str) -> int:
        """Extract 4-digit year from an SEC accession number string.
        
        Format: NNNNNNNNNN-YY-DDDDDD → year = 20YY
        e.g. '0000320193-24-000123' → 2024
        """
        m = re.search(r"-(\d{2})-", str(accession_number))
        if m:
            return 2000 + int(m.group(1))
        return 2026  # fallback current year

    def _load_filing_by_accession(self, accession_number: str) -> Any:
        """Load a Filing object from an accession number (handles edgar 5.x API).
        
        In edgar 5.x, Filing() requires 5 positional args:
        Filing(cik, company, form, filing_date, accession_no)
        
        Instead we use get_filing_by_accession(accession_number, year).
        """
        year = self._extract_year_from_accession(accession_number)
        # Try the exact year first, then ±1
        for try_year in [year, year - 1, year + 1]:
            try:
                from edgar._filings import get_filing_by_accession
                filing = get_filing_by_accession(accession_number, try_year)
                if filing is not None:
                    return filing
            except Exception:
                continue
        raise ValueError(f"Could not load filing by accession {accession_number}")

    def _load_filing_by_url(self, url: str) -> Any:
        """Load a Filing object from a direct SEC URL."""
        acc_match = re.search(r"(\d{10,}-\d{2,}-\d+)", url)
        if acc_match:
            return self._load_filing_by_accession(acc_match.group(1))

        raw_match = re.search(r"(?<!\d)(\d{18})(?!\d)", url)
        if raw_match:
            raw = raw_match.group(1)
            accession = f"{raw[:10]}-{raw[10:12]}-{raw[12:]}"
            return self._load_filing_by_accession(accession)

        raise ValueError(f"Cannot resolve URL to filing: {url}")

    # -- structured financials -----------------------------------------------

    @staticmethod
    def _try_financial_df(doc: Any, accessor: str) -> Any | None:
        """Get a pandas DataFrame from an edgar financial property."""
        val = getattr(doc, accessor, None)
        if val is None and hasattr(doc, "financials") and doc.financials:
            val = getattr(doc.financials, accessor, None)
        if val is None:
            return None
        to_df = getattr(val, "to_dataframe", None)
        if callable(to_df):
            try:
                return to_df()
            except Exception:
                pass
        return val

    # -- section resolution ---------------------------------------------------

    def _resolve_sections(self, requested: str | None) -> list[tuple[str, str]]:
        canonical_map: dict[str, tuple[str, str]] = {
            "income_statement":   ("income_statement", "Income Statement"),
            "balance_sheet":      ("balance_sheet", "Balance Sheet"),
            "cash_flow":          ("cash_flows", "Cash Flow Statement"),
            "cash_flow_statement": ("cash_flows", "Cash Flow Statement"),
            "cashflow_statement":  ("cash_flows", "Cash Flow Statement"),
            "mda":                ("management_discussion", "MD&A"),
            "risk_factors":       ("risk_factors", "Risk Factors"),
            "business":           ("business", "Business"),
        }
        results: list[tuple[str, str]] = []
        seen: set[str] = set()

        targets = [requested] if requested and requested != "full" else ["mda", "risk_factors", "business"]

        for req in targets:
            entry = canonical_map.get(req.lower())
            if isinstance(entry, tuple):
                ckey, dname = entry
                if ckey not in seen:
                    seen.add(ckey)
                    results.append((ckey, dname))
        return results

    # ============================= main entry point ==========================

    def read_filing_section(
        self,
        *,
        filing_url: str | None = None,
        accession_number: str | None = None,
        section: FilingSection | str = "full",
        chunk_index: int = 0,
        table_index: int | None = None,
    ) -> dict[str, Any]:
        section = section or "full"
        try:
            self._set_identity()
            filing = None
            if accession_number:
                filing = self._load_filing_by_accession(accession_number)
            elif filing_url:
                filing = self._load_filing_by_url(filing_url)
            if not filing:
                return {"error": "filing_url or accession_number required", "section": section}

            acc = str(getattr(filing, "accession_number", ""))
            cache_key = acc if (chunk_index == 0 and table_index is None) else f"{acc}::c{chunk_index}::t{table_index}"

            cached = self._get_section_cached(cache_key)
            if cached and cached.get("section") == section:
                return dict(cached)

            obj = filing.obj() if callable(getattr(filing, "obj", None)) else None

            result: dict[str, Any] = {
                "form": str(getattr(filing, "form", "")),
                "filing_date": str(getattr(filing, "filing_date", "")),
                "accession_number": acc,
                "url": str(getattr(filing, "filing_url", getattr(filing, "homepage_url", filing_url or ""))),
                "section": section,
            }

            # ===== 1) TOC mode: items + a lightweight index of ALL tables =====
            if section == "toc":
                available_items: list[str] = []
                has_financials = False
                items_preview: dict[str, dict[str, Any]] = {}

                if obj is not None:
                    avail = getattr(obj, "items", [])
                    if isinstance(avail, (list, tuple)):
                        available_items = [str(i) for i in avail]
                    if hasattr(obj, "financials") and obj.financials is not None:
                        has_financials = True

                    structure = getattr(obj, "structure", None)
                    supports_getitem = hasattr(obj, "__getitem__")
                    for item in available_items:
                        title = ""
                        if structure is not None:
                            try:
                                meta = structure.get_item(item)
                                if meta:
                                    title = meta.get("Title", "")
                            except Exception:
                                pass
                        text = ""
                        if supports_getitem:
                            try:
                                raw = obj[item]
                                text = str(raw) if raw else ""
                            except Exception:
                                text = ""
                        items_preview[item] = {
                            "title": title,
                            "length": len(text),
                            "preview": text[:500] if text else "",
                            "available": bool(text),
                        }

                    # Full table index — not just income/balance/cash flow.
                    # Cheap: obj.document is cached from the item loop above,
                    # so this doesn't re-parse the HTML.
                    all_tables = self._document_tables(obj)
                    tables_index = [
                        self._table_metadata(t, i, item_label)
                        for i, (t, item_label) in enumerate(all_tables)
                    ]
                    by_type: dict[str, int] = {}
                    for t in tables_index:
                        by_type[t["table_type"]] = by_type.get(t["table_type"], 0) + 1

                    result.update({
                        "tables": tables_index,
                        "tables_summary": {"total": len(tables_index), "by_type": by_type},
                    })

                # Dynamic instruction based on actual available_items
                form_type = result.get("form", "")
                items_list = ", ".join(available_items[:5]) if available_items else "none"
                if len(available_items) > 5:
                    items_list += f", ... ({len(available_items)} total)"
                
                instruction_text = (
                    f"This is a {form_type or 'unknown'} form filing. "
                    f"Available items: {items_list}. "
                    "IMPORTANT: Only use items from the 'available_items' list above. "
                    "Do NOT assume standard 10-K/10-Q sections exist - check available_items first. "
                    "Use section='tables' with table_index=N to render tables from the index above."
                )
                
                result.update({
                    "available_items": available_items,
                    "items_preview": items_preview,
                    "has_financials": has_financials,
                    "instruction": instruction_text,
                })
                self._put_section_cached(cache_key, result)
                return result

            # ===== 2) Tables mode: render one table, or paginate through all =====
            if section == "tables":
                all_tables = self._document_tables(obj)

                if not all_tables:
                    result.update({
                        "tables_count": 0,
                        "content": "",
                        "content_format": "markdown_tables",
                        "total_chunks": 0,
                        "chunk_index": 0,
                        "has_more": False,
                        "note": "No tables detected in this filing (or parser could not locate them).",
                    })
                    self._put_section_cached(cache_key, result)
                    return result

                if table_index is not None:
                    if table_index < 0 or table_index >= len(all_tables):
                        return {
                            "error": f"table_index out of range (0-{len(all_tables) - 1})",
                            "section": section,
                        }
                    table, item_label = all_tables[table_index]
                    result.update(self._table_metadata(table, table_index, item_label))
                    result["content"] = self._render_table_markdown(table)
                    result["content_format"] = "markdown_table"
                    result["has_more"] = False
                    self._put_section_cached(cache_key, result)
                    return result

                rendered_parts: list[str] = []
                for i, (table, item_label) in enumerate(all_tables):
                    meta = self._table_metadata(table, i, item_label)
                    header = f"### Table {i}"
                    if meta["item"]:
                        header += f" ({meta['item']})"
                    if meta["caption"]:
                        header += f" — {meta['caption']}"
                    header += f" [{meta['table_type']}, {meta['row_count']}x{meta['col_count']}]"
                    rendered_parts.append(f"{header}\n\n{self._render_table_markdown(table)}")

                full_text = "\n\n---\n\n".join(rendered_parts)
                chunks = self._chunk_text(full_text, "All Tables")
                idx = max(0, min(chunk_index, len(chunks) - 1))
                _, chunk_text, _, _ = chunks[idx]

                result.update({
                    "content": chunk_text,
                    "content_format": "markdown_tables",
                    "tables_count": len(all_tables),
                    "chunk_index": idx,
                    "total_chunks": len(chunks),
                    "has_more": idx < len(chunks) - 1,
                })
                self._put_section_cached(cache_key, result)
                return result

            # ===== 3) Single sub-section: financial statements or narrative item =====
            if section != "full":
                key = section.lower()
                form_type = result.get("form", "")
                
                # For narrative sections (mda, risk_factors, business), check if they're available
                # by looking at available_items from TOC or by attempting to find the section
                narrative_aliases = {
                    "mda": ["Item 7", "Item 2", "management_discussion"],
                    "risk_factors": ["Item 1A", "item_1a"],
                    "business": ["Item 1", "item_1"],
                }
                
                if key in narrative_aliases:
                    # Get available_items if not already loaded
                    if 'available_items' not in locals():
                        available_items = []
                        if obj is not None:
                            avail = getattr(obj, "items", [])
                            if isinstance(avail, (list, tuple)):
                                available_items = [str(i) for i in avail]
                    
                    # Check if any alias for this section is in available_items
                    # Need to handle both "Item 2" and "Part I, Item 2" formats
                    aliases = narrative_aliases[key]
                    has_section = False
                    for alias in aliases:
                        # Exact match
                        if alias in available_items:
                            has_section = True
                            break
                        # Check if alias appears in "Part X, Item Y" format
                        # Must be careful not to match "Item 2" with "Item 2.02" (8-K)
                        for item in available_items:
                            # Check for "Part X, Item Y" format
                            if item.endswith(f", {alias}"):
                                has_section = True
                                break
                            # Check for exact "Item Y" at the end (with word boundary)
                            if item.endswith(alias) and (len(item) == len(alias) or item[-len(alias)-1] in [',', ' ']):
                                has_section = True
                                break
                        if has_section:
                            break
                    
                    if not has_section and available_items:
                        return {
                            "error": f"Section '{section}' is not available in this {form_type} filing. "
                                     f"This filing has: {', '.join(available_items[:10])}. "
                                     f"Call section='toc' first to see all available items.",
                            "section": section,
                            "form": form_type,
                            "available_items": available_items,
                        }
                
                fin_keys = {"income_statement", "balance_sheet", "cash_flow", "cash_flow_statement", "cashflow_statement"}

                # --- 3a) structured financials first (XBRL-backed, most reliable) ---
                if key in fin_keys or key == "financial_statements":
                    accessor_map = {
                        "income_statement": [("income_statement", "Income Statement")],
                        "balance_sheet": [("balance_sheet", "Balance Sheet")],
                        "cash_flow": [("cash_flows", "Cash Flow Statement")],
                        "cash_flow_statement": [("cash_flows", "Cash Flow Statement")],
                        "cashflow_statement": [("cash_flows", "Cash Flow Statement")],
                        "financial_statements": [
                            ("income_statement", "Income Statement"),
                            ("balance_sheet", "Balance Sheet"),
                            ("cash_flows", "Cash Flow Statement"),
                        ],
                    }[key]

                    frames: list[str] = []
                    sections_out: dict[str, str] = {}
                    for ckey, dname in accessor_map:
                        df = self._try_financial_df(obj, ckey)
                        if df is None:
                            continue
                        md = df.to_markdown() if hasattr(df, "to_markdown") else str(df)
                        frames.append(f"### {dname}\n{md}")
                        sections_out[ckey] = f"### {dname}\n{md}"

                    if frames:
                        result.update({
                            "sections": sections_out,
                            "content": "\n\n---\n\n".join(frames),
                            "content_format": "markdown_tables",
                            "has_more": False,
                        })
                        self._put_section_cached(cache_key, result)
                        return result

                    # --- 3b) fallback: pull the matching table out of Item 8 ---
                    item8 = self._find_section_by_item(obj, "Item 8")
                    if item8 is not None:
                        try:
                            item8_tables = item8.tables()
                        except Exception:
                            item8_tables = []

                        targets = [k for k, _ in accessor_map]
                        rendered: list[str] = []
                        for target in targets:
                            table = self._match_financial_table(item8_tables, target)
                            if table is not None:
                                rendered.append(
                                    f"### {target.replace('_', ' ').title()} (extracted from Item 8)\n"
                                    f"{self._render_table_markdown(table)}"
                                )
                        if rendered:
                            result.update({
                                "content": "\n\n---\n\n".join(rendered),
                                "content_format": "markdown_tables",
                                "content_source": "item8_table_match",
                                "has_more": False,
                                "note": (
                                    "Structured XBRL data wasn't available; these tables were "
                                    "matched heuristically by caption inside Item 8 and may need "
                                    "manual verification."
                                ),
                            })
                            self._put_section_cached(cache_key, result)
                            return result

                # --- 3c) narrative sections (business / risk_factors / mda / financial_statements text) ---
                # Check if section is in section key format (e.g., "part_i_item_2")
                import re
                
                # Handle "Part X, Item Y" format (with comma and space) - convert to "part_x_item_y"
                part_comma_item_match = re.match(r'^part\s+([ivx]+),\s*item\s+(.+)$', key, re.IGNORECASE)
                if part_comma_item_match:
                    part = part_comma_item_match.group(1).lower()
                    item = part_comma_item_match.group(2).strip().lower()
                    key = f"part_{part}_item_{item}"
                
                section_key_match = re.match(r'^part_([ivx]+)_item_(.+)$', key, re.IGNORECASE)
                if section_key_match:
                    # Direct lookup by section key
                    sections = getattr(obj, "sections", {})
                    if key in sections:
                        section_obj = sections[key]
                        markdown_text = ""
                        table_count = 0
                        try:
                            markdown_text = section_obj.markdown() or ""
                        except Exception:
                            try:
                                markdown_text = section_obj.text() or ""
                            except Exception:
                                markdown_text = ""
                        try:
                            table_count = len(section_obj.tables())
                        except Exception:
                            table_count = 0
                        
                        if markdown_text:
                            chunks = self._chunk_text(markdown_text, key)
                            idx = max(0, min(chunk_index, len(chunks) - 1))
                            _, chunk_text, _, _ = chunks[idx]
                            
                            result.update({
                                "content": chunk_text,
                                "content_format": "markdown",
                                "item": key,
                                "tables_in_section": table_count,
                                "chunk_index": idx,
                                "total_chunks": len(chunks),
                                "has_more": idx < len(chunks) - 1,
                            })
                            self._put_section_cached(cache_key, result)
                            return result
                
                # Check if section is already in "Item X" format
                item_format_match = re.match(r'^item\s+(.+)$', key, re.IGNORECASE)
                if item_format_match:
                    # Extract the item number/letter (e.g., "2", "1A", "7")
                    item_num = item_format_match.group(1).strip()
                    # Reconstruct as "Item X" (preserve original case for matching)
                    item_label = f"Item {item_num}"
                else:
                    # For narrative aliases, determine the correct Item based on form type
                    # 10-Q uses Item 2 for MDA, 10-K uses Item 7
                    if key == "mda" and form_type == "10-Q":
                        item_label = "Item 2"
                    else:
                        item_label = self._EXTERNAL_TO_ITEM.get(key)
                
                if item_label:
                    section_obj = self._find_section_by_item(obj, item_label)
                    markdown_text = ""
                    table_count = 0

                    if section_obj is not None:
                        try:
                            markdown_text = section_obj.markdown() or ""
                        except Exception:
                            try:
                                markdown_text = section_obj.text() or ""
                            except Exception:
                                markdown_text = ""
                        try:
                            table_count = len(section_obj.tables())
                        except Exception:
                            table_count = 0
                    elif hasattr(obj, "__getitem__"):
                        try:
                            raw = obj[item_label]
                            markdown_text = str(raw) if raw else ""
                        except Exception:
                            markdown_text = ""

                    if markdown_text:
                        dname = item_label
                        chunks = self._chunk_text(markdown_text, dname)
                        idx = max(0, min(chunk_index, len(chunks) - 1))
                        _, chunk_text, _, _ = chunks[idx]

                        result.update({
                            "content": chunk_text,
                            "content_format": "markdown",
                            "item": item_label,
                            "tables_in_section": table_count,
                            "chunk_index": idx,
                            "total_chunks": len(chunks),
                            "has_more": idx < len(chunks) - 1,
                        })
                        self._put_section_cached(cache_key, result)
                        return result
                    else:
                        # Section not found or empty - return error
                        # Get available_items for better error message
                        if 'available_items' not in locals():
                            available_items = []
                            if obj is not None:
                                avail = getattr(obj, "items", [])
                                if isinstance(avail, (list, tuple)):
                                    available_items = [str(i) for i in avail]
                        
                        return {
                            "error": f"Section '{section}' is not available in this {form_type} filing. "
                                     f"This filing has: {', '.join(available_items[:10])}. "
                                     f"Call section='toc' first to see all available items.",
                            "section": section,
                            "form": form_type,
                            "available_items": available_items,
                        }

            # ===== 4) Legacy fallback (unchanged) =====
            if section == "full":
                result["text_excerpt"] = self._safe_text(filing)
            else:
                obj_check = filing.obj() if callable(getattr(filing, "obj", None)) else None
                if obj_check is not None:
                    excerpt = self._section_text(obj_check, section)
                    if excerpt:
                        result["text_excerpt"] = excerpt[:12000]
                else:
                    result["text_excerpt"] = self._safe_text(filing, max_chars=12000)

            self._put_section_cached(cache_key, result)
            return result

        except ImportError:
            logger.warning("edgartools not installed; EDGAR fetch skipped")
            return {"error": "edgartools not installed", "section": section}
        except Exception as exc:
            logger.warning("EDGAR section read failed: %s", exc)
            return {"error": str(exc), "section": section}
    # ========================================================================
    # Chunking helper
    # ========================================================================

    @staticmethod
    def _chunk_text(text: str, section_label: str, offset: int = 0) -> list[tuple[str, str, int, int]]:
        if not text:
            return [(section_label, "", 0, 0)]
        length = len(text)
        n_chunks = math.ceil(length / EdgarClient.CHUNK_CHARS)
        chunks: list[tuple[str, str, int, int]] = []
        for i in range(n_chunks):
            start = i * EdgarClient.CHUNK_CHARS
            end = min(start + EdgarClient.CHUNK_CHARS, length)
            chunk = text[start:end]
            chunks.append((section_label, chunk, start, end))
        return chunks

    # ------------------------------------------------------------------ other API methods --------------------------

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
            ticker_upper = ticker.upper()

            if self._cache_enabled and self._cache_root:
                cache_dir = SecCacheKey.cache_dir(self._cache_root, ticker_upper)
                if cache_dir.is_dir():
                    cached_list: list[dict[str, Any]] = []
                    for path in sorted(cache_dir.glob("*.json")):
                        try:
                            entry = json.loads(path.read_text(encoding="utf-8"))
                            if entry.get("form") in form_types:
                                cached_list.append(entry)
                        except Exception:
                            continue

                    if cached_list:
                        best: dict[str, dict[str, Any]] = {}
                        for c in cached_list:
                            ft = c.get("form", "")
                            d = c.get("filing_date", "")
                            if ft not in best or d >= best[ft].get("filing_date", ""):
                                best[ft] = c
                        cached_result = list(best.values())
                        logger.info(
                            "EDGAR cache hit for %s (%d filings from %d cached)",
                            ticker_upper,
                            len(cached_result),
                            len(cached_list),
                        )
                        return cached_result

            company = Company(ticker_upper)
            filings = []
            for form in form_types:
                try:
                    filing = company.get_filings(form=form).latest(1)
                    if not filing:
                        continue

                    form_label = str(getattr(filing, "form", form))
                    accession = str(getattr(filing, "accession_number", ""))

                    entry: dict[str, Any] = {
                        "form": form_label,
                        "filing_date": str(getattr(filing, "filing_date", "")),
                        "accession_number": accession,
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
                    logger.debug("EDGAR fetch %s for %s failed: %s", form, ticker_upper, exc)

            if self._cache_enabled and self._cache_root:
                cache_dir = SecCacheKey.cache_dir(self._cache_root, ticker_upper)
                cache_dir.mkdir(parents=True, exist_ok=True)
                for entry in filings:
                    fp = SecCacheKey.file_path(cache_dir, entry)
                    txt = entry.get("full_text")
                    if txt and len(txt) > 500_000:
                        acc = str(entry.get("accession_number", "")).replace("/", "-")
                        txt_path = cache_dir / f"{entry.get('form', 'filing')}_{acc}.txt"
                        txt_path.write_text(txt, encoding="utf-8")
                        entry_copy = dict(entry)
                        entry_copy["full_text_path"] = str(txt_path)
                        del entry_copy["full_text"]
                        fp.write_text(json.dumps(entry_copy, ensure_ascii=False, indent=2), encoding="utf-8")
                    else:
                        fp.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")

                indices: list[str] = []
                for entry in filings:
                    idx = SecCacheKey.file_path(cache_dir, entry).name
                    indices.append(idx)
                (cache_dir / "_index.json").write_text(
                    json.dumps({"filings": indices}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

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
        form_types = form_types or ["10-K", "10-Q", "8-K"]

        try:
            from edgar import Company

            self._set_identity()
            ticker_upper = ticker.upper()

            if self._cache_enabled and self._cache_root:
                cache_dir = SecCacheKey.cache_dir(self._cache_root, ticker_upper)
                if cache_dir.is_dir():
                    cached_list: list[dict[str, Any]] = []
                    for path in sorted(cache_dir.glob("*.json")):
                        try:
                            entry = json.loads(path.read_text(encoding="utf-8"))
                            fy = entry.get("fiscal_year")
                            if fy is not None and int(fy) == year:
                                cached_list.append(entry)
                        except Exception:
                            continue
                    if cached_list:
                        cached_list.sort(
                            key=lambda f: (f.get("filing_date", ""), f.get("form", ""))
                        )
                        logger.info(
                            "EDGAR year cache hit for %s %s (%d filings)",
                            ticker_upper,
                            year,
                            len(cached_list),
                        )
                        return cached_list

            company = Company(ticker_upper)
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
                    logger.debug("EDGAR fetch %s for %s year %s failed: %s", form, ticker_upper, year, exc)

            filings.sort(key=lambda f: (f.get("filing_date", ""), f.get("form", "")))

            if self._cache_enabled and self._cache_root:
                cache_dir = SecCacheKey.cache_dir(self._cache_root, ticker_upper)
                cache_dir.mkdir(parents=True, exist_ok=True)
                for entry in filings:
                    fp = SecCacheKey.file_path(cache_dir, entry)
                    txt = entry.get("full_text")
                    if txt and len(txt) > 500_000:
                        acc = str(entry.get("accession_number", "")).replace("/", "-")
                        txt_path = cache_dir / f"{entry.get('form', 'filing')}_{acc}.txt"
                        txt_path.write_text(txt, encoding="utf-8")
                        entry_copy = dict(entry)
                        entry_copy["full_text_path"] = str(txt_path)
                        del entry_copy["full_text"]
                        fp.write_text(json.dumps(entry_copy, ensure_ascii=False, indent=2), encoding="utf-8")
                    else:
                        fp.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
                indices = [SecCacheKey.file_path(cache_dir, e).name for e in filings]
                (cache_dir / "_index.json").write_text(
                    json.dumps({"year": year, "filings": indices}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            return filings

        except ImportError:
            logger.warning("edgartools not installed; EDGAR fetch skipped")
            return []
        except Exception as exc:
            logger.warning("EDGAR year fetch failed for %s %s: %s", ticker, year, exc)
            return []
    # -- table rendering & discovery -----------------------------------------

    @staticmethod
    def _render_table_markdown(table: Any) -> str:
        """Render a TableNode to a markdown pipe table, with graceful fallbacks."""
        # 1) edgar's own renderer — best fidelity (handles merged/multi-row headers)
        try:
            from edgar.documents.renderers.markdown import MarkdownRenderer
            rendered = MarkdownRenderer().render_node(table)
            if rendered and rendered.strip():
                return rendered.strip()
        except Exception:
            pass
        # 2) pandas DataFrame -> markdown (good for clean rectangular tables)
        try:
            df = table.to_dataframe()
            if df is not None and hasattr(df, "to_markdown"):
                return df.to_markdown()
        except Exception:
            pass
        # 3) last resort: plain rendered text (still readable, not tabular)
        try:
            text_fn = getattr(table, "text", None)
            if callable(text_fn):
                return text_fn()
        except Exception:
            pass
        return ""

    @staticmethod
    def _table_metadata(table: Any, index: int, item_label: str | None = None) -> dict[str, Any]:
        table_type = getattr(table, "table_type", None) or getattr(table, "semantic_type", None)
        type_name = getattr(table_type, "name", str(table_type)) if table_type is not None else "GENERAL"
        return {
            "index": index,
            "item": item_label,
            "caption": getattr(table, "caption", None) or "",
            "table_type": type_name,
            "row_count": getattr(table, "row_count", None),
            "col_count": getattr(table, "col_count", None),
            "is_financial": bool(getattr(table, "is_financial_table", False)),
        }

    @staticmethod
    def _document_tables(obj: Any) -> list[tuple[Any, str | None]]:
        """Every TableNode in the filing, paired with the item it belongs to.

        Document.tables() alone misses tables inside TOC-detected sections
        (those sections' content is lazily extracted and NOT part of the
        document root's node tree — see Section.tables()'s own docstring).
        So we aggregate both: the root-level walk (fast, catches anything
        not inside a detected section, e.g. cover/signature pages) AND a
        per-section walk (catches TOC-lazy content), de-duped by identity.
        """
        collected: list[tuple[Any, str | None]] = []
        seen_ids: set[int] = set()

        document = getattr(obj, "document", None)
        if document is not None:
            tables_fn = getattr(document, "tables", None)
            if callable(tables_fn):
                try:
                    for t in (tables_fn() or []):
                        if id(t) not in seen_ids:
                            seen_ids.add(id(t))
                            collected.append((t, None))
                except Exception:
                    pass

        sections = getattr(obj, "sections", None)
        if sections:
            try:
                for sec in sections.values():
                    item_label = f"Item {sec.item}" if getattr(sec, "item", None) else None
                    try:
                        sec_tables = sec.tables() or []
                    except Exception:
                        sec_tables = []
                    for t in sec_tables:
                        if id(t) not in seen_ids:
                            seen_ids.add(id(t))
                            collected.append((t, item_label))
            except Exception:
                pass

        return collected

    @staticmethod
    def _find_section_by_item(obj: Any, item_label: str) -> Any | None:
        """Locate the Section object for an item like 'Item 7' / 'Item 1A'.

        Matches on Section.item (e.g. '7', '1A') rather than dict key, since
        edgartools' internal key naming ('mda' vs 'management_discussion' vs
        'part_ii_item_7') is not stable across versions.
        """
        sections = getattr(obj, "sections", None)
        if not sections:
            return None
        target = item_label.replace("Item", "").strip().upper()
        try:
            for sec in sections.values():
                sec_item = getattr(sec, "item", None)
                if sec_item and str(sec_item).upper() == target:
                    return sec
        except Exception:
            pass
        return None

    _FIN_TABLE_KEYWORDS: dict[str, tuple[str, ...]] = {
        "income_statement": ("income", "operations", "earnings"),
        "balance_sheet": ("balance sheet", "financial position"),
        "cash_flows": ("cash flow",),
    }

    @classmethod
    def _match_financial_table(cls, tables: list[Any], target_key: str) -> Any | None:
        """Best-effort match of a specific statement inside an Item 8 table dump.

        Matches by caption keyword first; falls back to the first table flagged
        is_financial_table if no caption match is found (captions are often
        missing in raw HTML filings, so this is a heuristic, not a guarantee).
        """
        keywords = cls._FIN_TABLE_KEYWORDS.get(target_key, ())
        for t in tables:
            caption = (getattr(t, "caption", None) or "").lower()
            if any(kw in caption for kw in keywords):
                return t
        for t in tables:
            if getattr(t, "is_financial_table", False):
                return t
        return None