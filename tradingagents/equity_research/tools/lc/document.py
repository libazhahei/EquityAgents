"""LangChain document tools."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.tools import tool

from tradingagents.equity_research.tools import document_tools


@tool
def list_files(file_path: Annotated[str, "Directory path relative to workspace root"] = ".") -> dict[str, Any]:
    """List files in a workspace directory."""
    return document_tools.list_files(file_path)


@tool
def file_reader(file_path: Annotated[str, "Path to text/markdown/json/csv file"]) -> dict[str, Any]:
    """Read a local text, markdown, JSON, or CSV file."""
    return document_tools.file_reader(file_path)


@tool
def pdf_reader(file_path: Annotated[str, "Path to PDF file"]) -> dict[str, Any]:
    """Read text content from a PDF file."""
    return document_tools.pdf_reader(file_path)


@tool
def docx_reader(file_path: Annotated[str, "Path to Word .docx file"]) -> dict[str, Any]:
    """Read text from a Word document."""
    return document_tools.docx_reader(file_path)


@tool
def table_extractor(file_path: Annotated[str, "Path to file containing tables"]) -> dict[str, Any]:
    """Extract tables from HTML, CSV, or PDF files."""
    return document_tools.table_extractor(file_path)


@tool
def document_chunker(
    text: Annotated[str, "Document text to chunk"],
    strategy: Annotated[str, "Chunking strategy: paragraph or fixed"] = "paragraph",
    chunk_size: Annotated[int, "Chunk size when strategy is fixed"] = 1000,
) -> dict[str, Any]:
    """Split document text into chunks."""
    return document_tools.document_chunker(text, strategy=strategy, chunk_size=chunk_size)


@tool
def document_outline_extractor(text: Annotated[str, "Markdown or structured text"]) -> dict[str, Any]:
    """Extract document outline from markdown headings."""
    return document_tools.document_outline_extractor(text)


@tool
def reference_parser(text: Annotated[str, "Text containing bibliographic references"]) -> dict[str, Any]:
    """Parse bibliographic references from text."""
    return document_tools.reference_parser(text)
