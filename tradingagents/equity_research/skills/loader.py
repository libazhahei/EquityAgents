"""Load and parse .skill.md definition files."""

from __future__ import annotations

import os
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from tradingagents.equity_research.skills.base import LoadedSkill, ManifestSummary, SkillCatalogEntry

REQUIRED_SECTIONS = ("Constraints", "Prompt Template")
OPTIONAL_SECTIONS = ("Query Guidance",)
ALLOWED_SECTIONS = set(REQUIRED_SECTIONS + OPTIONAL_SECTIONS)

DEFAULT_DEFINITIONS_DIR = Path(__file__).resolve().parent / "definitions"


@dataclass
class ParsedSkillFile:
    path: Path
    manifest: ManifestSummary
    constraints: str
    prompt_template: str
    query_guidance: str
    handler: str | None
    output_schema: dict
    raw_frontmatter: dict
    tools: list[str] = field(default_factory=list)
    compatible_with: list[str] = field(default_factory=list)
    composable: bool = False
    version: int = 1


@dataclass
class SkillLoader:
    definitions_dir: Path = field(default_factory=lambda: _resolve_definitions_dir())
    known_tools: set[str] | None = None
    _cache: dict[str, tuple[float, ParsedSkillFile]] = field(default_factory=dict, init=False)
    _catalog_cache: dict[str, tuple[float, SkillCatalogEntry]] = field(default_factory=dict, init=False)
    load_errors: list[str] = field(default_factory=list, init=False)
    load_warnings: list[str] = field(default_factory=list, init=False)

    def reload(self) -> None:
        self._cache.clear()
        self._catalog_cache.clear()
        self.load_errors.clear()
        self.load_warnings.clear()

    def scan_definitions(self) -> list[Path]:
        if not self.definitions_dir.exists():
            return []
        return sorted(self.definitions_dir.glob("*.skill.md"))

    def scan_catalog(self) -> dict[str, SkillCatalogEntry]:
        catalog: dict[str, SkillCatalogEntry] = {}
        self.load_errors.clear()
        self.load_warnings.clear()
        for path in self.scan_definitions():
            try:
                entry = self.scan_catalog_entry(path)
                if entry.name in catalog:
                    self.load_errors.append(f"Duplicate skill name '{entry.name}' in {path}")
                    continue
                catalog[entry.name] = entry
            except Exception as exc:
                self.load_errors.append(f"{path.name}: {exc}")
        return catalog

    def scan_catalog_entry(self, path: Path) -> SkillCatalogEntry:
        mtime = path.stat().st_mtime
        cached = self._catalog_cache.get(str(path))
        if cached and cached[0] == mtime:
            return cached[1]

        text = path.read_text(encoding="utf-8")
        data = _parse_frontmatter_dict(text)
        name = str(data.get("name", "")).strip()
        if not name:
            raise ValueError("frontmatter 'name' is required")
        expected_stem = f"{name}.skill.md"
        if path.name != expected_stem:
            raise ValueError(f"filename must be {expected_stem}, got {path.name}")

        description = str(data.get("description", "")).strip()
        when_to_use = str(data.get("when_to_use", "")).strip()
        if not description:
            raise ValueError("frontmatter 'description' is required")
        if not when_to_use:
            raise ValueError("frontmatter 'when_to_use' is required")

        tools = list(data.get("tools") or [])
        if self.known_tools is not None:
            for tool in tools:
                if tool not in self.known_tools:
                    self.load_warnings.append(f"{name}: unknown tool '{tool}'")

        entry = SkillCatalogEntry(
            name=name,
            description=description,
            when_to_use=when_to_use,
            tags=list(data.get("tags") or []),
            source_path=str(path),
            tools=tools,
            handler=data.get("handler"),
            compatible_with=list(data.get("compatible_with") or []),
            composable=bool(data.get("composable", False)),
            version=int(data.get("version", 1)),
        )
        self._catalog_cache[str(path)] = (mtime, entry)
        return entry

    def read_skill_file(self, path: Path) -> ParsedSkillFile:
        return self.parse_skill_file(path)

    def load_all(self) -> dict[str, ParsedSkillFile]:
        warnings.warn("load_all() is deprecated; use scan_catalog() + read_skill_file()", DeprecationWarning, stacklevel=2)
        parsed: dict[str, ParsedSkillFile] = {}
        self.load_errors.clear()
        self.load_warnings.clear()
        for path in self.scan_definitions():
            try:
                item = self.parse_skill_file(path)
                if item.manifest.name in parsed:
                    self.load_errors.append(f"Duplicate skill name '{item.manifest.name}' in {path}")
                    continue
                parsed[item.manifest.name] = item
            except Exception as exc:
                self.load_errors.append(f"{path.name}: {exc}")
        return parsed

    def parse_skill_file(self, path: Path) -> ParsedSkillFile:
        mtime = path.stat().st_mtime
        cached = self._cache.get(str(path))
        if cached and cached[0] == mtime:
            return cached[1]

        text = path.read_text(encoding="utf-8")
        frontmatter, body = _split_frontmatter(text)
        if frontmatter is None:
            raise ValueError("missing YAML frontmatter")

        data = yaml.safe_load(frontmatter) or {}
        if not isinstance(data, dict):
            raise ValueError("frontmatter must be a mapping")

        name = str(data.get("name", "")).strip()
        if not name:
            raise ValueError("frontmatter 'name' is required")
        expected_stem = f"{name}.skill.md"
        if path.name != expected_stem:
            raise ValueError(f"filename must be {expected_stem}, got {path.name}")

        description = str(data.get("description", "")).strip()
        when_to_use = str(data.get("when_to_use", "")).strip()
        if not description:
            raise ValueError("frontmatter 'description' is required")
        if not when_to_use:
            raise ValueError("frontmatter 'when_to_use' is required")

        sections = split_markdown_sections(body)
        for required in REQUIRED_SECTIONS:
            if not sections.get(required, "").strip():
                raise ValueError(f"missing required section '## {required}'")

        unknown = set(sections) - ALLOWED_SECTIONS
        if unknown:
            raise ValueError(f"unknown sections: {', '.join(sorted(unknown))}")

        tools = list(data.get("tools") or [])
        if self.known_tools is not None:
            for tool in tools:
                if tool not in self.known_tools:
                    self.load_warnings.append(f"{name}: unknown tool '{tool}'")

        parsed = ParsedSkillFile(
            path=path,
            manifest=ManifestSummary(
                name=name,
                description=description,
                when_to_use=when_to_use,
                tags=list(data.get("tags") or []),
            ),
            constraints=sections.get("Constraints", "").strip(),
            prompt_template=sections.get("Prompt Template", "").strip(),
            query_guidance=sections.get("Query Guidance", "").strip(),
            handler=data.get("handler"),
            output_schema=dict(data.get("output_schema") or {}),
            raw_frontmatter=data,
            tools=tools,
            compatible_with=list(data.get("compatible_with") or []),
            composable=bool(data.get("composable", False)),
            version=int(data.get("version", 1)),
        )
        self._cache[str(path)] = (mtime, parsed)
        return parsed

    def to_loaded_skill(self, parsed: ParsedSkillFile) -> LoadedSkill:
        return LoadedSkill(
            manifest=parsed.manifest,
            constraints=parsed.constraints,
            prompt_template=parsed.prompt_template,
            query_guidance=parsed.query_guidance,
            tools=parsed.tools,
            compatible_with=parsed.compatible_with,
            composable=parsed.composable,
            handler=parsed.handler,
            output_schema=parsed.output_schema,
            source_path=str(parsed.path),
            version=parsed.version,
        )

    def catalog_entry_to_loaded_skill(self, entry: SkillCatalogEntry) -> LoadedSkill:
        path = Path(entry.source_path)
        parsed = self.read_skill_file(path)
        return self.to_loaded_skill(parsed)


def _parse_frontmatter_dict(text: str) -> dict:
    frontmatter, _ = _split_frontmatter(text)
    if frontmatter is None:
        raise ValueError("missing YAML frontmatter")
    data = yaml.safe_load(frontmatter) or {}
    if not isinstance(data, dict):
        raise ValueError("frontmatter must be a mapping")
    return data


def _resolve_definitions_dir() -> Path:
    override = os.environ.get("EQUITY_RESEARCH_SKILLS_DIR")
    if override:
        return Path(override)
    return DEFAULT_DEFINITIONS_DIR


def _split_frontmatter(text: str) -> tuple[str | None, str]:
    stripped = text.lstrip("\ufeff")
    if not stripped.startswith("---"):
        return None, stripped
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", stripped, re.DOTALL)
    if not match:
        return None, stripped
    return match.group(1), stripped[match.end():]


def split_markdown_sections(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(buffer).strip()
            current = line[3:].strip()
            buffer = []
        else:
            buffer.append(line)
    if current is not None:
        sections[current] = "\n".join(buffer).strip()
    return sections


def format_skill_prompt(template: str, state: dict) -> str:
    values = {
        "ticker": state.get("ticker", ""),
        "sector": state.get("sector", ""),
        "report_type": state.get("report_type", ""),
        "instrument_context": state.get("instrument_context", ""),
        "industry": state.get("industry", ""),
        "objective": state.get("active_objective", ""),
    }
    try:
        return template.format(**values)
    except KeyError:
        return template
