import os
import sys
import argparse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from pipeline.utils.duckdb import (
    connect_to_db, 
    load_config
)
from pipeline.utils.logger import create_logger

logger = create_logger("reset_tables.log")


def get_tables_to_drop() -> list[tuple[str, str]]:

    parser = argparse.ArgumentParser(description="Drop specified DuckDB tables.")
    parser.add_argument('tables', type=str, nargs='*', help='tables to drop (e.g., bronze.tbl1 silver.tbl1)')
    args = parser.parse_args()

    if not args.tables:
        logger.warning("No tables were specified. Usage: python3 src/sql/reset_tables.py [schema.table_name]")
        return

    tables = []

    for tbl in args.tables:
        parts = tbl.split('.')
        if len(parts) == 2:
            schema_name, table_name = parts
            tables.append((schema_name, table_name))
        else:
            raise ValueError(f"Invalid table format: {tbl}. Expected format: schema.table_name")

    return tables


def main():

    # load config to get db_path
    config_path = os.path.join(os.path.dirname(__file__), "../resources/variables.yml")
    config = load_config(config_path)

    # connect to db
    db_path = config.get("db", {}).get("db_path", "data/budget.db")
    con = connect_to_db(db_path, logger)

    tables = get_tables_to_drop()
    
    for table in tables:
        # Parse schema and table name
        schema_name, table_name = table
        query = f"SELECT count(*) FROM information_schema.tables WHERE table_schema='{schema_name}' AND table_name='{table_name}'"
            
        res = con.execute(query).fetchone()
        if res and res[0] > 0:
            try:
                con.sql(f"DROP TABLE IF EXISTS {schema_name}.{table_name}")
                logger.info(f"Successfully dropped table: {schema_name}.{table_name}")
            except Exception as e:
                logger.error(f"Error dropping table {schema_name}.{table_name}: {e}")
        else:
            logger.warning(f"Table does not exist: {schema_name}.{table_name}")

    con.close()

if __name__ == "__main__":
    main()
