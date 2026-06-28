"""Document reading tools."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from tradingagents.equity_research.tools.workspace_utils import get_document_root, resolve_safe_path


def list_files(file_path: str = ".") -> dict[str, Any]:
    target = resolve_safe_path(file_path)
    if not target.exists():
        return {"path": str(target), "entries": [], "error": "not found"}
    if target.is_file():
        return {"path": str(target), "entries": [target.name], "type": "file"}
    entries = sorted(p.name for p in target.iterdir())
    return {"path": str(target), "entries": entries, "type": "directory"}


def file_reader(file_path: str) -> dict[str, Any]:
    path = resolve_safe_path(file_path)
    if not path.is_file():
        return {"path": str(path), "content": "", "error": "not a file"}
    suffix = path.suffix.lower()
    if suffix == ".json":
        return {"path": str(path), "content": json.loads(path.read_text(encoding="utf-8"))}
    if suffix == ".csv":
        return {"path": str(path), "content": path.read_text(encoding="utf-8")[:50000]}
    return {"path": str(path), "content": path.read_text(encoding="utf-8", errors="replace")[:50000]}


def pdf_reader(file_path: str) -> dict[str, Any]:
    path = resolve_safe_path(file_path)
    try:
        from pypdf import PdfReader
    except ImportError:
        return {"path": str(path), "pages": [], "error": "pypdf not installed"}
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages[:50]]
    return {"path": str(path), "pages": pages, "text": "\n\n".join(pages)}


def docx_reader(file_path: str) -> dict[str, Any]:
    path = resolve_safe_path(file_path)
    try:
        from docx import Document
    except ImportError:
        return {"path": str(path), "text": "", "error": "python-docx not installed"}
    doc = Document(str(path))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return {"path": str(path), "text": "\n".join(paragraphs), "paragraph_count": len(paragraphs)}


def table_extractor(file_path: str) -> dict[str, Any]:
    path = resolve_safe_path(file_path)
    suffix = path.suffix.lower()
    tables: list[Any] = []
    if suffix in {".html", ".htm"}:
        tables = [df.to_dict(orient="records") for df in pd.read_html(str(path))]
    elif suffix == ".csv":
        tables = [pd.read_csv(path).head(100).to_dict(orient="records")]
    elif suffix == ".pdf":
        pdf = pdf_reader(file_path)
        text = pdf.get("text", "")
        tables = [{"raw_text_block": block} for block in text.split("\n\n") if "|" in block or "\t" in block]
    return {"path": str(path), "tables": tables}


def document_chunker(text: str, strategy: str = "paragraph", chunk_size: int = 1000) -> dict[str, Any]:
    if strategy == "fixed":
        chunks = [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
    else:
        chunks = [c.strip() for c in re.split(r"\n\s*\n", text) if c.strip()]
    return {"strategy": strategy, "chunks": chunks}


def document_outline_extractor(text: str) -> dict[str, Any]:
    outline = []
    for line in text.splitlines():
        m = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
        if m:
            outline.append({"level": len(m.group(1)), "title": m.group(2)})
    return {"outline": outline}


def reference_parser(text: str) -> dict[str, Any]:
    refs = re.findall(r"\[([^\]]+)\]\s*([\d]{4})?[;,\s]*(.+)?", text)
    parsed = [{"key": r[0], "year": r[1] or "", "detail": (r[2] or "").strip()} for r in refs]
    return {"references": parsed}
