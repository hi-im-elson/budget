#!/usr/bin/env python3
"""
Identify recurring e-transfer patterns from the WealthSimple Cash silver table.

Usage:
    python3 scripts/analyze_etransfers.py

Outputs a summary of outbound/inbound e-transfers grouped by amount with
frequency and average interval, followed by a full chronological listing.
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from pipeline.utils.duckdb import connect_to_db, load_config
from pipeline.utils.logger import create_logger

logger = create_logger("analyze_etransfers.log")


def main():
    config_path = os.path.join(os.path.dirname(__file__), "../resources/sources.yml")
    config = load_config(config_path)
    db_path = config.get("db", {}).get("db_path", "data/budget.db")
    con = connect_to_db(db_path, logger)

    try:
        # --- Outbound summary ---
        print("=" * 70)
        print("  OUTBOUND E-TRANSFERS BY AMOUNT  (sorted by frequency)")
        print("=" * 70)
        print(f"{'Amount':>10}  {'Count':>5}  {'First':>12}  {'Last':>12}  {'Avg Days':>8}")
        print("-" * 60)

        rows = con.execute("""
            SELECT
                ABS(amount)          AS amt,
                COUNT(*)             AS cnt,
                MIN(date)            AS first_date,
                MAX(date)            AS last_date,
                CASE WHEN COUNT(*) > 1
                    THEN ROUND((MAX(date) - MIN(date))::INT / (COUNT(*) - 1.0), 1)
                    ELSE NULL
                END                  AS avg_days
            FROM silver.wealthsimple_cash
            WHERE transaction IN ('E_TRFOUT', 'P2P_SENT')
            GROUP BY ABS(amount)
            ORDER BY cnt DESC, amt DESC
        """).fetchall()

        for r in rows:
            avg = f"{r[4]:.0f}" if r[4] else "N/A"
            print(f"{r[0]:>10}  {r[1]:>5}  {r[2]}  {r[3]}  {avg:>8}")

        # --- Outbound chronological ---
        print()
        print("=" * 70)
        print("  ALL OUTBOUND E-TRANSFERS  (chronological)")
        print("=" * 70)
        print(f"{'Date':>12}  {'Amount':>10}  {'Type':>10}  Description")
        print("-" * 60)

        rows = con.execute("""
            SELECT date, amount, transaction, description
            FROM silver.wealthsimple_cash
            WHERE transaction IN ('E_TRFOUT', 'P2P_SENT')
            ORDER BY date
        """).fetchall()
        for r in rows:
            print(f"{r[0]}  {r[1]:>10}  {r[2]:>10}  {r[3]}")

        # --- Inbound summary ---
        print()
        print("=" * 70)
        print("  INBOUND E-TRANSFERS BY AMOUNT")
        print("=" * 70)
        print(f"{'Amount':>10}  {'Count':>5}  {'First':>12}  {'Last':>12}")
        print("-" * 50)

        rows = con.execute("""
            SELECT
                amount    AS amt,
                COUNT(*)  AS cnt,
                MIN(date) AS first_date,
                MAX(date) AS last_date
            FROM silver.wealthsimple_cash
            WHERE transaction = 'E_TRFIN'
            GROUP BY amount
            ORDER BY cnt DESC, amt DESC
        """).fetchall()
        for r in rows:
            print(f"{r[0]:>10}  {r[1]:>5}  {r[2]}  {r[3]}")

        # --- Inbound chronological ---
        print()
        print("=" * 70)
        print("  ALL INBOUND E-TRANSFERS  (chronological)")
        print("=" * 70)
        print(f"{'Date':>12}  {'Amount':>10}  Description")
        print("-" * 50)

        rows = con.execute("""
            SELECT date, amount, description
            FROM silver.wealthsimple_cash
            WHERE transaction = 'E_TRFIN'
            ORDER BY date
        """).fetchall()
        for r in rows:
            print(f"{r[0]}  {r[1]:>10}  {r[2]}")

    finally:
        con.close()


if __name__ == "__main__":
    main()
