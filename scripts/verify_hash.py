"""
Verify that transaction_key() in pipeline/utils/hash.py produces IDs that
match gold.fact_transactions for sampled rows.

Usage:
    python scripts/verify_hash.py

Expects the app's DuckDB file at data/budget.db (override with --db).
"""

import argparse
import sys
import duckdb

sys.path.insert(0, ".")  # run from project root
from pipeline.utils.hash import transaction_key


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/budget.db")
    parser.add_argument("--n", type=int, default=10, help="Number of rows to sample")
    args = parser.parse_args()

    conn = duckdb.connect(args.db, read_only=True)

    rows = conn.execute(f"""
        SELECT id, source, source_id
        FROM gold.fact_transactions
        USING SAMPLE {args.n}
    """).fetchall()

    if not rows:
        print("No rows found in gold.fact_transactions — run the pipeline first.")
        sys.exit(1)

    # All current sources use nextval() sequence ids (primary_key: [] in sources.yml).
    # gold.source_id stores that UBIGINT; we cast it to VARCHAR to match the SQL expression
    # SHA256(source || CAST(id AS VARCHAR)).

    source_to_silver_table = {
        "amex-cobalt":       "silver.amex_cobalt",
        "rbc-mastercard":    "silver.rbc_mastercard",
        "rbc-chequing":      "silver.rbc_chequing",
        "wealthsimple-cash": "silver.wealthsimple_cash",
    }

    passed = 0
    failed = 0

    for gold_id, source, source_id in rows:
        silver_table = source_to_silver_table.get(source)
        if not silver_table:
            print(f"  SKIP  unknown source '{source}'")
            continue

        silver_row = conn.execute(
            f"SELECT CAST(id AS VARCHAR) FROM {silver_table} WHERE id = ?", [source_id]
        ).fetchone()

        if not silver_row:
            print(f"  SKIP  silver row not found: {silver_table}.id={source_id}")
            continue

        silver_id_str = silver_row[0]
        python_id = transaction_key(source, silver_id_str)

        status = "PASS" if python_id == gold_id else "FAIL"
        print(f"  {status}  source={source} source_id={source_id}")
        if python_id != gold_id:
            print(f"         DuckDB : {gold_id}")
            print(f"         Python : {python_id}")
            failed += 1
        else:
            passed += 1

    conn.close()

    print(f"\n{passed} passed, {failed} failed out of {passed + failed} checked.")

    # -----------------------------------------------------------------------
    # P2-06 migration note
    # -----------------------------------------------------------------------
    print("""
--- P2-06 migration note ---
transaction_key() currently mirrors SHA256(source || CAST(silver.id AS VARCHAR))
where silver.id is a nextval() sequence integer.
In P2-06 the signature will change to hash raw transaction fields directly
(date, description, amount, source) so IDs are independent of silver row order.
When that lands, update the SHA256 expressions in fact_transactions.sql to match,
and re-run this script against the migrated data to confirm alignment.
""")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
