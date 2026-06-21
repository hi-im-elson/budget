from __future__ import annotations

import duckdb

from pipeline.adapters.base import TransactionRow
from pipeline.classification.chain import ClassificationChain
from pipeline.utils.hash import transaction_key
from pipeline.utils.logger import get_logger

logger = get_logger(__name__)

# (source_key, silver_table, amount_col, description_col, date_col)
_SOURCES: list[tuple[str, str, str, str, str]] = [
    ("amex-cobalt",       "amex_cobalt",       "amount", "merchant",    "date"),
    ("rbc-mastercard",    "rbc_mastercard",     "cad",    "description", "transaction_date"),
    ("rbc-chequing",      "rbc_chequing",       "cad",    "description", "transaction_date"),
    ("wealthsimple-cash", "wealthsimple_cash",  "amount", "description", "date"),
]

# Credit card sources: positive amount = refund/credit (inbound), negative = charge (outbound).
# Structural engine always handles these fully; this is a safety fallback for rule-matched rows.
_CC_SOURCES = {"amex-cobalt", "rbc-mastercard"}

# RBC Mastercard: positive cad = credit. Amex: positive amount = refund. Both follow same sign.
# (No inversion needed — both treat positive as inbound for the fallback path.)


def build_fact_transactions(conn: duckdb.DuckDBPyConnection) -> None:
    _ensure_table(conn)
    conn.execute("DELETE FROM gold.fact_transactions")

    chain = ClassificationChain()
    for source_key, silver_table, amount_col, desc_col, date_col in _SOURCES:
        _process_source(conn, chain, source_key, silver_table, amount_col, desc_col, date_col)

    logger.info("build_fact_transactions complete.")


def _ensure_table(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("CREATE SCHEMA IF NOT EXISTS gold")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gold.fact_transactions (
            "id"               VARCHAR        NOT NULL PRIMARY KEY,
            "transaction_date" DATE           NOT NULL,
            "source"           VARCHAR        NOT NULL,
            "description"      VARCHAR,
            "amount"           DECIMAL(10,2)  NOT NULL,
            "direction"        VARCHAR(20)    NOT NULL,
            "type_code"        VARCHAR,
            "category_id"      INTEGER,
            "category_name"    VARCHAR,
            "matched_by"       VARCHAR        NOT NULL DEFAULT 'unknown',
            "confidence"       DECIMAL(5,4)   NOT NULL DEFAULT 1.0,
            "source_id"        UBIGINT,
            "transfer_pair_id" VARCHAR
        )
    """)
    # Migrate tables created by the old SQL schema (DuckDB 0.9+)
    for col_ddl in [
        'ALTER TABLE gold.fact_transactions ADD COLUMN IF NOT EXISTS "category_name" VARCHAR',
        'ALTER TABLE gold.fact_transactions ADD COLUMN IF NOT EXISTS "matched_by" VARCHAR DEFAULT \'unknown\'',
        'ALTER TABLE gold.fact_transactions ADD COLUMN IF NOT EXISTS "confidence" DECIMAL(5,4) DEFAULT 1.0',
    ]:
        try:
            conn.execute(col_ddl)
        except Exception as exc:
            logger.debug("Column migration skipped: %s — %s", col_ddl, exc)


def _process_source(
    conn: duckdb.DuckDBPyConnection,
    chain: ClassificationChain,
    source_key: str,
    silver_table: str,
    amount_col: str,
    desc_col: str,
    date_col: str,
) -> None:
    result = conn.execute(f"SELECT * FROM silver.{silver_table}")
    columns = [d[0] for d in result.description]
    rows = result.fetchall()

    if not rows:
        logger.info("[%s] No rows in silver.%s — skipping.", source_key, silver_table)
        return

    records: list[list] = []
    for raw_row in rows:
        raw = dict(zip(columns, raw_row))

        raw_amount = float(raw.get(amount_col) or 0)
        tx = TransactionRow(
            id=transaction_key(source_key, str(raw["id"])),
            date=str(raw.get(date_col) or ""),
            description=str(raw.get(desc_col) or ""),
            amount=abs(raw_amount),
            direction="",   # resolved below
            source=source_key,
            raw=raw,
        )

        cl = chain.classify(tx)
        direction = _resolve_direction(cl.matched_by, cl.direction, raw_amount, source_key)

        records.append([
            tx.id,
            tx.date,
            tx.source,
            tx.description,
            tx.amount,
            direction,
            cl.type_code,
            cl.category_id,
            cl.category_name,
            cl.matched_by,
            cl.confidence,
            raw["id"],
            None,           # transfer_pair_id — populated later by bridge_transfer_pairs.sql
        ])

    conn.executemany("""
        INSERT INTO gold.fact_transactions
            (id, transaction_date, source, description, amount, direction,
             type_code, category_id, category_name, matched_by, confidence,
             source_id, transfer_pair_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (id) DO NOTHING
    """, records)

    logger.info("[%s] Classified and inserted %d transactions.", source_key, len(records))


def _resolve_direction(matched_by: str, structural_direction: str, signed_amount: float, source_key: str) -> str:
    """
    Structural results carry the correct direction from the engine.
    Rule-matched results don't set direction, so we derive it from the signed amount.

    CC sign convention: negative = charge (outbound), positive = refund/credit (inbound).
    Cash account convention: positive = inbound, negative = outbound.
    Both conventions map the same way, so no per-source branching is needed.
    """
    if matched_by == "structural":
        return structural_direction

    if signed_amount > 0:
        return "inbound"
    if signed_amount < 0:
        return "outbound"
    return "outbound"
