#!/usr/bin/env python3
"""
Migration script: Add v2 chunking columns to filing_chunk table.

This adds the new columns required by the table-aware chunker v2:
- chunk_type: "text" or "table"
- table_title: Title extracted for table chunks
- table_section: Section context for table chunks
- parent_labels: JSON array of hierarchical parent labels

Usage:
    python scripts/migrate_filing_chunk_v2.py [--config path/to/config.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from tradingagents.equity_research.storage.db import get_engine


MIGRATION_SQL = [
    # Add chunk_type column
    """
    ALTER TABLE filing_chunk
    ADD COLUMN IF NOT EXISTS chunk_type VARCHAR(50) DEFAULT 'text'
    """,
    # Add table_title column
    """
    ALTER TABLE filing_chunk
    ADD COLUMN IF NOT EXISTS table_title VARCHAR(500)
    """,
    # Add table_section column
    """
    ALTER TABLE filing_chunk
    ADD COLUMN IF NOT EXISTS table_section VARCHAR(100)
    """,
    # Add parent_labels column (JSON array)
    """
    ALTER TABLE filing_chunk
    ADD COLUMN IF NOT EXISTS parent_labels JSONB
    """,
    # Add index for chunk_type filtering
    """
    CREATE INDEX IF NOT EXISTS idx_filing_chunk_type
    ON filing_chunk (chunk_type)
    """,
]


def migrate(config_path: str | None = None) -> int:
    """Run migration and return number of successful operations."""
    # Load config if provided
    config = None
    if config_path:
        with open(config_path) as f:
            config = json.load(f)
    
    engine = get_engine(config)
    
    success_count = 0
    with engine.connect() as conn:
        for sql in MIGRATION_SQL:
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"✅ {sql.strip().split()[0:3]}")
                success_count += 1
            except Exception as e:
                print(f"⚠️  Skipped (already exists): {sql.strip()[:60]}...")
                conn.rollback()
    
    return success_count


def main():
    parser = argparse.ArgumentParser(
        description="Migrate filing_chunk table to v2 schema"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to config JSON file (optional)",
    )
    
    args = parser.parse_args()
    
    print("🔄 Migrating filing_chunk table to v2 schema...")
    print("   Adding columns: chunk_type, table_title, table_section, parent_labels")
    print()
    
    success = migrate(args.config)
    
    print()
    print(f"✅ Migration complete! {success} operations succeeded.")
    print()
    print("📝 Next steps:")
    print("   1. Re-ingest your SEC filings to populate the new columns")
    print("   2. Run: python scripts/ingest_sec_filings.py NVDA 2022 --force")


if __name__ == "__main__":
    main()
