import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from pipeline.utils.duckdb import connect_to_db, load_config, execute
from pipeline.utils.logger import create_logger

logger = create_logger("gold.log")

GOLD_DIR = os.path.join(os.path.dirname(__file__), "gold")

SQL_FILES = [
    "dim_source.sql",
    "dim_category.sql",
    "dim_merchant.sql",
]


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
