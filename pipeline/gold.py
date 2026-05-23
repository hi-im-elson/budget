import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from pipeline.utils.duckdb import connect_to_db, load_config, execute
from pipeline.utils.logger import create_logger

logger = create_logger("gold.log")

GOLD_DIR = os.path.join(os.path.dirname(__file__), "gold")

SQL_FILES = [
    "dim_category.sql",
    "dim_merchant.sql",
    "dim_transaction_type.sql",
    "fact_transactions.sql",
]


def populate_dim_source(con, config, logger):
    """Dynamically populate gold.dim_source from configured sources."""
    con.execute("CREATE SCHEMA IF NOT EXISTS gold;")
    
    execute(con, """
        CREATE TABLE IF NOT EXISTS gold.dim_source (
            "source" VARCHAR(255) NOT NULL PRIMARY KEY,
            "last_transaction_date" DATE NOT NULL,
            "last_updated" TIMESTAMP NOT NULL
        );
    """, logger)

    execute(con, "DELETE FROM gold.dim_source;", logger)

    sources = config.get("sources", {})
    for source_key, source_config in sources.items():
        silver_table = source_config.get("silver_table")
        tx_date_col = source_config.get("transaction_date")
        if not silver_table or not tx_date_col:
            continue

        # Check if table exists in duckdb
        table_parts = silver_table.split('.')
        schema_name = table_parts[0] if len(table_parts) > 1 else 'main'
        table_name = table_parts[-1]
        
        table_check = con.execute(
            f"SELECT 1 FROM information_schema.tables WHERE table_schema = '{schema_name}' AND table_name = '{table_name}'"
        ).fetchone()
        
        if not table_check:
            logger.warning(f"Silver table {silver_table} for source {source_key} does not exist. Skipping.")
            continue

        # Insert or replace from silver table
        query = f"""
            INSERT OR REPLACE INTO gold.dim_source ("source", "last_transaction_date", "last_updated")
            SELECT
                '{source_key}' AS "source",
                MAX("{tx_date_col}") AS last_transaction_date,
                MAX(updated_at) AS "last_updated"
            FROM {silver_table}
            HAVING MAX("{tx_date_col}") IS NOT NULL;
        """
        try:
            execute(con, query, logger)
        except Exception as e:
            logger.error(f"Failed to populate dim_source for {source_key}: {e}")


def run_sql_file(con, filename: str):
    """Read and execute a SQL file, skipping blank and comment-only statements."""
    path = os.path.join(GOLD_DIR, filename)
    with open(path, "r") as f:
        sql = f.read()

    statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("--")]
    for stmt in statements:
        execute(con, stmt, logger)
    logger.info(f"{filename} complete.")


def main():
    config_path = os.path.join(os.path.dirname(__file__), "../resources/sources.yml")
    config = load_config(config_path)
    db_path = config.get("db", {}).get("db_path", "data/budget.db")

    con = connect_to_db(db_path, logger)
    try:
        logger.info("Starting Gold Pipeline...")
        logger.info("Dynamically populating gold.dim_source...")
        populate_dim_source(con, config, logger)
        
        for sql_file in SQL_FILES:
            logger.info(f"Loading {sql_file}...")
            run_sql_file(con, sql_file)
        logger.info("Gold Pipeline completed successfully.")
    except Exception as e:
        logger.error(f"Gold Pipeline failed: {e}")
        raise
    finally:
        con.close()



if __name__ == "__main__":
    main()
