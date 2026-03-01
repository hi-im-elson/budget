import duckdb
import os
import sys

# Add project root to sys.path so we can import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.sql.utils.duckdb import (
    connect_to_db, 
    load_config, 
    execute, 
    parse_value_from_string_sql, 
    generate_primary_key_sql,
    return_current_timestamp
)
from src.utils.logger import create_logger

logger = create_logger("silver.log")

def generate_dml(source_table: str, target_table: str, source_config: dict) -> str:
    """
    Generates INSERT queries based on column configuration and source mapping.
    """
    target_cols = []
    source_cols = []
    primary_key = source_config.get("primary_key", [])
    columns_config = source_config.get("columns", [])
    
    for col in columns_config:
        name = col.get("name")
        source_col = col.get("source_column")
        target_type = col.get("type", "VARCHAR") # default type
        date_format = source_config.get("csv_options", {}).get("dateformat", "")
        target_cols.append(f'"{name}"')
        
        if name == "id":
            if primary_key:
                # Generate hash from primary key columns
                source_cols.append(generate_primary_key_sql(primary_key))
            else:
                # remove id from target_cols; use default auto increment
                target_cols.remove(f'"{name}"') 

        elif col.get("default") == "CURRENT_TIMESTAMP":
             source_cols.append(return_current_timestamp(name, target_type))

        elif source_col:
            
            # Apply transformation
            fmt = date_format if target_type == "DATE" else ""
            
            # Use utility function
            val_expr = parse_value_from_string_sql(f'"{source_col}"', f'"{name}"', target_type, fmt)
            source_cols.append(val_expr)
             
    # Construct Query
    target_cols_str = ", ".join(target_cols)
    source_cols_str = ", ".join(source_cols)
    
    query = f"""
        INSERT INTO {target_table} ({target_cols_str})
        SELECT {source_cols_str} FROM {source_table}
    """
    return query

def load_silver(con: duckdb.DuckDBPyConnection, source_name: str, config: dict):
    """
    Populates silver table from bronze table.
    Assumes silver table already exists.
    """
    source_table = config.get("bronze_table")
    target_table = config.get("silver_table")

    logger.info(f"Populating {target_table} from {source_table}...")
    
    insert_query = generate_dml(source_table, target_table, config)
    
    try:
        execute(con, insert_query, logger)
        logger.info(f"Silver load complete for {source_name}.")
    except Exception as e:
        logger.error(f"Error populating {target_table}: {e}")
        raise

def main():
    # Load config
    config_path = os.path.join(os.path.dirname(__file__), "../../resources/variables.yml")
    config = load_config(config_path)
    
    db_path = config.get("db", {}).get("db_path", "data/budget.db")
    con = connect_to_db(db_path, logger)
    
    try:
        sources = config.get("sources", {})
        for source_name, source_config in sources.items():
            load_silver(con, source_name, source_config)
    finally:
        con.close()

if __name__ == "__main__":
    main()
