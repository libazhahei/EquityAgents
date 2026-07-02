#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS_DIR="$ROOT_DIR/tradingagents/equity_research/tools"

CATALOG_FILE="$TOOLS_DIR/tool_catalog.py"
STATIC_FILE="$TOOLS_DIR/lc/__init__.py"
STUB_FILE="$TOOLS_DIR/lc/stubs.py"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

KNOWN_CATEGORIES='^(system|search|document|finance|code|data|artifact|quality|human|academic|browser|memory)$'

extract_catalog_tools() {
  awk '
    BEGIN { in_equity=0; in_tools=0; depth=0 }
    /EQUITY_TOOLS_CATEGORIES[[:space:]]*:[[:space:]]*dict/ { in_equity=1; next }
    in_equity {
      open_count = gsub(/\{/, "{")
      close_count = gsub(/\}/, "}")

      if ($0 ~ /"tools"[[:space:]]*:[[:space:]]*\{/) {
        in_tools=1
        depth=1
        next
      }

      if (in_tools) {
        if (match($0, /^[[:space:]]*"([a-z][a-z0-9_]*)"[[:space:]]*:[[:space:]]*\{/ , m)) {
          print m[1]
        }
        depth += open_count - close_count
        if (depth <= 0) {
          in_tools=0
          depth=0
        }
      }

      if (!in_tools && $0 ~ /^SKILL_DOMAINS[[:space:]]*:/) {
        in_equity=0
      }
    }
  ' "$CATALOG_FILE" | sort -u
}

extract_implemented_false_tools() {
  awk '
    BEGIN { in_equity=0; in_tools=0; depth=0 }
    /EQUITY_TOOLS_CATEGORIES[[:space:]]*:[[:space:]]*dict/ { in_equity=1; next }
    in_equity {
      open_count = gsub(/\{/, "{")
      close_count = gsub(/\}/, "}")

      if ($0 ~ /"tools"[[:space:]]*:[[:space:]]*\{/) {
        in_tools=1
        depth=1
        next
      }

      if (in_tools) {
        if ($0 ~ /"implemented"[[:space:]]*:[[:space:]]*False/ && match($0, /^[[:space:]]*"([a-z][a-z0-9_]*)"[[:space:]]*:/, m)) {
          print m[1]
        }
        depth += open_count - close_count
        if (depth <= 0) {
          in_tools=0
          depth=0
        }
      }

      if (!in_tools && $0 ~ /^SKILL_DOMAINS[[:space:]]*:/) {
        in_equity=0
      }
    }
  ' "$CATALOG_FILE" | sort -u
}

extract_map_keys() {
  local file="$1"
  local map_name="$2"

  awk -v map_name="$map_name" '
    $0 ~ map_name"[[:space:]]*:[[:space:]]*dict" { in_map=1; next }
    in_map && $0 ~ /^}/ { in_map=0; next }
    in_map {
      if (match($0, /"[a-z][a-z0-9_]*"[[:space:]]*:/)) {
        key = substr($0, RSTART + 1, RLENGTH - 3)
        print key
      }
    }
  ' "$file" | sort -u
}

extract_catalog_tools > "$TMP_DIR/catalog.txt"
extract_implemented_false_tools > "$TMP_DIR/implemented_false.txt"
extract_map_keys "$STATIC_FILE" 'STATIC_LANGCHAIN_TOOLS' > "$TMP_DIR/static.txt"
extract_map_keys "$STUB_FILE" 'STUB_LANGCHAIN_TOOLS' > "$TMP_DIR/stub.txt"
cat "$TMP_DIR/static.txt" "$TMP_DIR/stub.txt" | sort -u > "$TMP_DIR/registered_or_stubbed.txt"

printf '\n=== Tool Registry Audit ===\n'
printf 'Catalog tools: %s\n' "$(wc -l < "$TMP_DIR/catalog.txt")"
printf 'Static registered tools: %s\n' "$(wc -l < "$TMP_DIR/static.txt")"
printf 'Stub tools: %s\n' "$(wc -l < "$TMP_DIR/stub.txt")"
printf 'Static+Stub unique: %s\n\n' "$(wc -l < "$TMP_DIR/registered_or_stubbed.txt")"

printf -- '--- Catalog but neither static nor stub ---\n'
comm -23 "$TMP_DIR/catalog.txt" "$TMP_DIR/registered_or_stubbed.txt" || true

printf -- '\n--- Static/Stub but not in catalog ---\n'
comm -13 "$TMP_DIR/catalog.txt" "$TMP_DIR/registered_or_stubbed.txt" || true

printf -- '\n--- Overlap between static and stub (should be empty) ---\n'
comm -12 "$TMP_DIR/static.txt" "$TMP_DIR/stub.txt" || true

printf -- '\n--- implemented=False but present in static (risk) ---\n'
comm -12 "$TMP_DIR/implemented_false.txt" "$TMP_DIR/static.txt" || true

printf -- '\n--- implemented=False but present in stub (expected) ---\n'
comm -12 "$TMP_DIR/implemented_false.txt" "$TMP_DIR/stub.txt" || true

printf -- '\n--- Legacy/New likely semantic overlaps ---\n'
for pair in \
  'perplexity_search batch_light_grounding_search'; do
  old_name="$(echo "$pair" | awk '{print $1}')"
  new_name="$(echo "$pair" | awk '{print $2}')"
  old_in_catalog='no'
  new_in_catalog='no'
  if grep -qx "$old_name" "$TMP_DIR/catalog.txt"; then old_in_catalog='yes'; fi
  if grep -qx "$new_name" "$TMP_DIR/catalog.txt"; then new_in_catalog='yes'; fi
  printf '%s <-> %s | catalog: %s/%s\n' "$old_name" "$new_name" "$old_in_catalog" "$new_in_catalog"
done
