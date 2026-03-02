import os
import duckdb
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))


from pipeline.utils.duckdb import (
    connect_to_db, 
    load_config, 
    execute
)

from pipeline.utils.logger import create_logger

logger = create_logger("bronze.log")

def load_bronze(con: duckdb.DuckDBPyConnection, source_name: str, config: dict):
    """
    Loads raw CSV data into bronze table.
    """
    csv_path = config.get("input_path") # path to raw csv files
    table_name = config.get("bronze_table") # name of bronze
    date_format = config.get("csv_options", {}).get("dateformat", "") # format of dates in csv
    
    if not csv_path or not table_name:
        logger.warning(f"Skipping {source_name}: Missing input_path or bronze_table in config")
        return

    logger.info(f"Loading bronze layer for {source_name} from {csv_path}...")
    
    # Check if files exist
    files = con.execute(f"SELECT * FROM glob('{csv_path}/*.csv')").fetchall()
    if not files:
        logger.warning(f"No files found matching {csv_path}. Skipping bronze load.")
        return

    # Insert data
    for f in files:
        f = f[0]
        logger.info(f"Processing file: {f}")
        
        insert_query = f"""
            INSERT INTO {table_name} 
            SELECT * FROM read_csv('{f}', all_varchar=true, filename=true, sep=',')
        """

        execute(con, insert_query, logger)

    logger.info(f"Bronze load complete for {source_name}.")


def main():
    # Load config
    # Using relative path for robustness when run from project root
    config_path = os.path.join(os.path.dirname(__file__), "../resources/variables.yml")
    config = load_config(config_path)
    
    db_path = config.get("db", {}).get("db_path", "data/budget.db")
    con = connect_to_db(db_path, logger)
    
    try:
        sources = config.get("sources", {})
        for source_name, source_config in sources.items():
            load_bronze(con, source_name, source_config)
    finally:
        con.close()

if __name__ == "__main__":
    main()
