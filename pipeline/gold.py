import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from pipeline.utils.duckdb import connect_to_db, load_config, execute
from pipeline.utils.logger import create_logger

logger = create_logger("gold.log")

GOLD_DIR = os.path.join(os.path.dirname(__file__), "gold")

# SQL files executed in order
SQL_FILES = [
    "dim_category.sql",
    "dim_merchant.sql",
    "dim_transaction_type.sql",
    "dim_type_category.sql",
    "fact_transactions.sql",
    "bridge_transfer_pairs.sql",
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

        table_parts = silver_table.split('.')
        schema_name = table_parts[0] if len(table_parts) > 1 else 'main'
        table_name = table_parts[-1]

        table_check = con.execute(
            f"SELECT 1 FROM information_schema.tables "
            f"WHERE table_schema = '{schema_name}' AND table_name = '{table_name}'"
        ).fetchone()

        if not table_check:
            logger.warning(f"Silver table {silver_table} for source {source_key} does not exist. Skipping.")
            continue

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


def silver_table_exists(con, config, source_key):
    """Return True if the silver table for the given source_key exists in DuckDB."""
    sources = config.get("sources", {})
    source_config = sources.get(source_key, {})
    silver_table = source_config.get("silver_table")
    if not silver_table:
        return False
    parts = silver_table.split('.')
    schema_name = parts[0] if len(parts) > 1 else 'main'
    table_name = parts[-1]
    result = con.execute(
        f"SELECT 1 FROM information_schema.tables "
        f"WHERE table_schema = '{schema_name}' AND table_name = '{table_name}'"
    ).fetchone()
    return result is not None


def run_sql_file(con, filename: str):
    """Read and execute a SQL file, skipping blank and comment-only statements."""
    path = os.path.join(GOLD_DIR, filename)
    with open(path, "r") as f:
        sql = f.read()

    statements = []
    for chunk in sql.split(";"):
        stripped = "\n".join(
            line for line in chunk.splitlines()
            if not line.strip().startswith("--")
        ).strip()
        if stripped:
            statements.append(stripped)

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

        # Log which optional sources are present so fact_transactions.sql
        # can be understood in context. The SQL itself guards via LEFT JOIN
        # on silver tables, missing tables result in zero rows, not errors.
        for source in ["rbc-chequing"]:
            present = silver_table_exists(con, config, source)
            logger.info(f"Optional source '{source}': {'present' if present else 'absent — rows will be skipped'}")

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
