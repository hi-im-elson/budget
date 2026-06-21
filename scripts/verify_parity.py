#!/usr/bin/env python3
"""
verify_parity.py — P2-06 parity verification script.

Compares gold.fact_transactions output from the old SQL run (parity_old.parquet)
against the new Python run (parity_new.parquet).

Usage:
    # Step 1: Run pipeline with old SQL to capture baseline
    #   (temporarily restore fact_transactions.sql.bak and run gold.py,
    #    then export the result)
    #   duckdb data/budget.db -c "COPY gold.fact_transactions TO 'parity_old.parquet' (FORMAT PARQUET)"

    # Step 2: Run pipeline with new Python module
    #   python -m pipeline.gold
    #   duckdb data/budget.db -c "COPY gold.fact_transactions TO 'parity_new.parquet' (FORMAT PARQUET)"

    # Step 3: Run this script
    #   python scripts/verify_parity.py

Exit code: 0 if parity passes, 1 if mismatches found.
"""
import sys

import duckdb

OLD_PARQUET = "parity_old.parquet"
NEW_PARQUET = "parity_new.parquet"


def main() -> int:
    conn = duckdb.connect()

    old_count = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{OLD_PARQUET}')").fetchone()[0]
    new_count = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{NEW_PARQUET}')").fetchone()[0]
    print(f"Row counts — old: {old_count:,}  new: {new_count:,}")

    if old_count != new_count:
        print(f"  ⚠️  Row count mismatch: {old_count - new_count:+,} rows")
    else:
        print("  ✅ Row counts match.")

    dropped = conn.execute(f"""
        SELECT o.id, o.description, o.amount
        FROM read_parquet('{OLD_PARQUET}') o
        WHERE o.id NOT IN (
            SELECT id FROM read_parquet('{NEW_PARQUET}')
        )
    """).df()

    if len(dropped) > 0:
        print(f"\n  ❌ Dropped transactions (in old, missing in new): {len(dropped)}")
        print(dropped.head(20).to_string(index=False))
    else:
        print("  ✅ All old IDs present in new output.")

    added = conn.execute(f"""
        SELECT n.id, n.description, n.amount
        FROM read_parquet('{NEW_PARQUET}') n
        WHERE n.id NOT IN (
            SELECT id FROM read_parquet('{OLD_PARQUET}')
        )
    """).df()

    if len(added) > 0:
        print(f"\n  ⚠️  New transactions (in new, not in old): {len(added)}")
        print(added.head(20).to_string(index=False))
    else:
        print("  ✅ No extra transactions in new output.")

    category_diff = conn.execute(f"""
        SELECT
            o.id,
            o.source,
            o.description,
            o.amount,
            o.category_id   AS old_category_id,
            n.category_id   AS new_category_id,
            n.category_name AS new_category_name,
            n.matched_by
        FROM read_parquet('{OLD_PARQUET}') o
        JOIN read_parquet('{NEW_PARQUET}') n USING (id)
        WHERE o.category_id IS DISTINCT FROM n.category_id
        ORDER BY o.source, o.description
    """).df()

    print(f"\nCategory ID mismatches: {len(category_diff)}")
    if len(category_diff) > 0:
        print(category_diff.head(20).to_string(index=False))
    else:
        print("  ✅ category_id matches for all shared IDs.")

    direction_diff = conn.execute(f"""
        SELECT
            o.id,
            o.source,
            o.description,
            o.amount,
            o.direction AS old_direction,
            n.direction AS new_direction,
            n.matched_by
        FROM read_parquet('{OLD_PARQUET}') o
        JOIN read_parquet('{NEW_PARQUET}') n USING (id)
        WHERE o.direction != n.direction
        ORDER BY o.source, o.description
    """).df()

    print(f"\nDirection mismatches: {len(direction_diff)}")
    if len(direction_diff) > 0:
        print(direction_diff.head(20).to_string(index=False))
    else:
        print("  ✅ direction matches for all shared IDs.")

    amount_diff = conn.execute(f"""
        SELECT
            o.id,
            o.source,
            o.description,
            o.amount    AS old_amount,
            n.amount    AS new_amount
        FROM read_parquet('{OLD_PARQUET}') o
        JOIN read_parquet('{NEW_PARQUET}') n USING (id)
        WHERE ROUND(o.amount, 2) != ROUND(n.amount, 2)
        ORDER BY o.source
    """).df()

    print(f"\nAmount mismatches: {len(amount_diff)}")
    if len(amount_diff) > 0:
        print(amount_diff.head(20).to_string(index=False))
    else:
        print("  ✅ amount matches for all shared IDs.")

    print("\nmatched_by breakdown (new output):")
    breakdown = conn.execute(f"""
        SELECT matched_by, COUNT(*) AS count
        FROM read_parquet('{NEW_PARQUET}')
        GROUP BY matched_by
        ORDER BY count DESC
    """).df()
    print(breakdown.to_string(index=False))

    total_issues = len(dropped) + len(category_diff) + len(direction_diff) + len(amount_diff)
    print(f"\n{'='*60}")
    if total_issues == 0 and old_count == new_count:
        print("✅  PARITY PASSED — safe to merge.")
        return 0
    else:
        print(f"❌  PARITY FAILED — {total_issues} mismatches + {abs(old_count - new_count)} row count diff.")
        print("   Do not merge until all mismatches are 0 or intentionally explained.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
