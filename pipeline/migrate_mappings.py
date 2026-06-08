"""
Migrates data/mappings/*.csv into Postgres classification tables.
Safe to re-run: all inserts use ON CONFLICT DO NOTHING.
Run from repo root: python pipeline/migrate_mappings.py
"""

import csv
import json
import sys
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.utils.postgres import fetchall, get_connection
from pipeline.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Expected CSV not found: {path}")
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        return [{k.strip(): v.strip() for k, v in row.items()} for row in reader]


def _require_category(category_name: str, category_map: dict, csv_file: str) -> int:
    """Resolve category name → id, raising loudly if missing."""
    cat_id = category_map.get(category_name)
    if cat_id is None:
        raise ValueError(
            f"[{csv_file}] Unknown category '{category_name}'. "
            f"Add it to categories.csv and re-run migrate_categories first."
        )
    return cat_id


def build_category_map() -> dict[str, int]:
    rows = fetchall("SELECT id, name FROM categories")
    return {r["name"]: r["id"] for r in rows}


# ---------------------------------------------------------------------------
# Migration functions
# ---------------------------------------------------------------------------

def migrate_categories(mappings_dir: Path) -> None:
    rows = _read_csv(mappings_dir / "categories.csv")
    logger.info(f"categories.csv: {len(rows)} rows read")

    params = [(r["category"], r.get("subcategory") or None) for r in rows]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO categories (name, group_name)
                VALUES (%s, %s)
                ON CONFLICT (name) DO NOTHING
                """,
                params,
            )
            inserted = cur.rowcount

    # executemany rowcount is unreliable across drivers; log conservatively
    logger.info(f"categories: {len(params)} attempted, {inserted} inserted (rest skipped)")


def migrate_merchant_to_category(mappings_dir: Path, category_map: dict[str, int]) -> None:
    rows = _read_csv(mappings_dir / "merchant_to_category.csv")
    logger.info(f"merchant_to_category.csv: {len(rows)} rows read")

    params = []
    for r in rows:
        cat_id = _require_category(r["category_name"], category_map, "merchant_to_category.csv")
        params.append(("merchant_exact", r["merchant_name"], None, cat_id, 100))

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO user_rules (rule_type, match_value, source, category_id, priority)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (rule_type, match_value, source) DO NOTHING
                """,
                params,
            )
            inserted = cur.rowcount

    logger.info(f"user_rules (merchant_exact): {len(params)} attempted, {inserted} inserted")


def migrate_system_rules(mappings_dir: Path, category_map: dict[str, int]) -> None:
    """
    Loads all remaining CSVs into system_rules.
    Each source defines how its columns map to (rule_type, keyword, source,
    type_code, category_id, priority, meta).
    """
    sources: list[tuple[str, str, callable]] = [
        ("classification_rules.csv",    "keyword_classification", _map_classification_rule),
        ("etransfer_rules.csv",          "etransfer_pattern",      _map_etransfer_rule),
        ("etransfer_recipients.csv",     "etransfer_recipient",    _map_etransfer_recipient),
        ("recurring_vendor_rules.csv",   "keyword_subscription",   _map_recurring_vendor_rule),
        ("merchant_to_parent_merchant.csv", "merchant_parent",     _map_merchant_parent),
    ]

    for csv_file, rule_type, mapper in sources:
        rows = _read_csv(mappings_dir / csv_file)
        logger.info(f"{csv_file}: {len(rows)} rows read")

        params = []
        for r in rows:
            cat_id = None
            if "category_name" in r and r["category_name"]:
                cat_id = _require_category(r["category_name"], category_map, csv_file)
            params.append(mapper(r, rule_type, cat_id))

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO system_rules
                        (rule_type, keyword, source, type_code, category_id, priority, meta)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (rule_type, keyword) DO NOTHING
                    """,
                    params,
                )
                inserted = cur.rowcount

        logger.info(f"system_rules ({rule_type}): {len(params)} attempted, {inserted} inserted")


# ---------------------------------------------------------------------------
# Row mappers — each returns a 7-tuple matching system_rules INSERT columns:
# (rule_type, keyword, source, type_code, category_id, priority, meta)
# ---------------------------------------------------------------------------

def _map_classification_rule(r: dict, rule_type: str, cat_id: int | None) -> tuple:
    return (
        rule_type,
        r["keyword"],
        r.get("source"),
        r.get("type_code"),
        cat_id,
        int(r.get("priority", 50)),
        json.dumps({"match_field": r.get("match_field")}) if r.get("match_field") else None,
    )


def _map_etransfer_rule(r: dict, rule_type: str, cat_id: int | None) -> tuple:
    return (
        rule_type,
        r["name_pattern"],
        None,
        r.get("type_code"),
        cat_id,
        50,
        json.dumps({"direction": r.get("direction"), "notes": r.get("notes") or None}),
    )


def _map_etransfer_recipient(r: dict, rule_type: str, cat_id: int | None) -> tuple:
    # Stored as keyword = recipient_name; date+amount captured in meta for auditability.
    return (
        rule_type,
        r["recipient_name"],
        None,
        None,
        cat_id,
        100,
        json.dumps({"date": r.get("date"), "amount": r.get("amount")}),
    )


def _map_recurring_vendor_rule(r: dict, rule_type: str, cat_id: int | None) -> tuple:
    return (
        rule_type,
        r["keyword"],
        None,
        r.get("type_code") or None,
        cat_id,
        50,
        json.dumps({"subcategory": r.get("subcategory") or None, "notes": r.get("notes") or None}),
    )


def _map_merchant_parent(r: dict, rule_type: str, cat_id: int | None) -> tuple:
    return (
        rule_type,
        r["merchant_name"],
        None,
        None,
        cat_id,
        50,
        json.dumps({"parent_merchant_name": r.get("parent_merchant_name")}),
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mappings_dir = Path("data/mappings")

    logger.info("=== migrate_mappings: start ===")

    migrate_categories(mappings_dir)

    category_map = build_category_map()
    logger.info(f"Category map loaded: {len(category_map)} entries")

    migrate_merchant_to_category(mappings_dir, category_map)
    migrate_system_rules(mappings_dir, category_map)

    logger.info("=== migrate_mappings: complete ===")
