"""
Central source of truth for all SHA256 key generation in the pipeline.

All current sources declare primary_key: [] in sources.yml, so silver.id is always
a nextval() UBIGINT sequence. The gold key is therefore:

  Gold id:  SHA256(source || CAST(silver.id AS VARCHAR))   — integer cast to string

P2-06 will replace this with a hash over raw transaction fields (date, description,
amount, source) so IDs are independent of silver row order. Until then, this module
mirrors the SQL — any change here must be reflected in fact_transactions.sql and vice versa.
"""

import hashlib
import re


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def normalise_description(description: str) -> str:
    """
    Normalise a transaction description for stable merchant cache lookups.
    - Lowercase + strip whitespace
    - Collapse internal whitespace to single spaces
    - Strip trailing reference numbers (e.g. "TIM HORTONS #1234" → "TIM HORTONS")
    """
    s = description.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s*#\d+$", "", s)
    return s


# ---------------------------------------------------------------------------
# Silver-layer key  (mirrors generate_primary_key_sql in utils/duckdb.py)
# ---------------------------------------------------------------------------

def silver_key(*column_values: str) -> str:
    """
    Replicate: SHA256(col1 || col2 || ...)
    Pass column values in the same order declared in sources.yml primary_key.

    Not used by any current source (all have primary_key: []). Reserved for
    future sources that declare a natural key instead of a sequence id.
    """
    raw = "".join(str(v) for v in column_values)
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Gold-layer key  (mirrors SHA256(source || CAST(id AS VARCHAR)) in fact_transactions.sql)
# ---------------------------------------------------------------------------

def transaction_key(source: str, silver_id: str) -> str:
    """
    Replicate: SHA256(source || CAST(silver.id AS VARCHAR))

    Args:
        source:    Source key exactly as used in SQL, e.g. 'amex-cobalt'
        silver_id: silver.<table>.id cast to string — a sequence integer, e.g. '42'

    Returns:
        64-character hex SHA256 digest — must match gold.fact_transactions.id
    """
    raw = source + silver_id
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# LLM cache key
# ---------------------------------------------------------------------------

def merchant_key(description: str) -> str:
    """
    Stable cache key for LLM classification lookups.
    Keyed on normalised description only so the same merchant is always a hit
    regardless of transaction amount or date.
    """
    normalised = normalise_description(description)
    return hashlib.sha256(normalised.encode()).hexdigest()
