import duckdb
import os
import sys

# Add project root to sys.path so we can import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from pipeline.utils.duckdb import (
    connect_to_db, 
    load_config, 
    execute, 
    parse_value_from_string_sql, 
    generate_primary_key_sql,
    return_current_timestamp
)
from pipeline.utils.logger import create_logger

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

def generate_mapping_dml(csv_path: str, target_table: str, config: dict) -> str:
    """
    Generates INSERT queries for mapping tables based on configuration.
    """
    target_cols = []
    source_cols = []
    
    insert_columns = config.get("insert_columns", [])
    for col in insert_columns:
        target_name = col.get("name")
        source_name = col.get("source")
        target_cols.append(f'"{target_name}"')
        source_cols.append(f'"{source_name}"')
        
    fk_lookup = config.get("foreign_key_lookup")
    
    if fk_lookup:
        insert_col = fk_lookup.get("insert_column")
        source_col = fk_lookup.get("source_column")
        lookup_table = fk_lookup.get("lookup_table")
        lookup_col = fk_lookup.get("lookup_column")
        return_col = fk_lookup.get("return_column")
        
        target_cols.append(f'"{insert_col}"')
        target_cols_str = ", ".join(target_cols)
        
        source_cols_prefixed = [f'raw."{col.get("source")}"' for col in insert_columns]
        source_cols_str = ", ".join(source_cols_prefixed)
        
        query = f"""
            INSERT INTO {target_table} ({target_cols_str})
            SELECT 
                {source_cols_str},
                lookup."{return_col}"
            FROM read_csv_auto('{csv_path}') raw
            LEFT JOIN {lookup_table} lookup ON raw."{source_col}" = lookup."{lookup_col}"
        """
    else:
        target_cols_str = ", ".join(target_cols)
        source_cols_str = ", ".join(source_cols)
        
        query = f"""
            INSERT INTO {target_table} ({target_cols_str})
            SELECT {source_cols_str} FROM read_csv_auto('{csv_path}')
        """
        
    return query

def load_mapping(con: duckdb.DuckDBPyConnection, mapping_name: str, config: dict):
    """
    Populates mapping table from raw CSV file.
    Assumes mapping table already exists.
    """
    target_table = config.get("table")
    csv_filename = config.get("csv_file")
    
    if not target_table or not csv_filename:
        logger.warning(f"Skipping {mapping_name}: Missing table or csv_file in config")
        return
        
    csv_path = f"data/mappings/{csv_filename}"
    
    logger.info(f"Populating {target_table} from {csv_path}...")
    
    try:
        execute(con, f"DELETE FROM {target_table}", logger)
    except Exception as e:
        logger.warning(f"Could not delete from {target_table}, continuing: {e}")
    
    insert_query = generate_mapping_dml(csv_path, target_table, config)
    
    try:
        execute(con, insert_query, logger)
        logger.info(f"Mapping load complete for {mapping_name}.")
    except Exception as e:
        logger.error(f"Error populating {target_table}: {e}")
        raise

def main():
    # Load sources config
    sources_config_path = os.path.join(os.path.dirname(__file__), "../resources/sources.yml")
    sources_config = load_config(sources_config_path)
    
    # Load mappings config
    mappings_config_path = os.path.join(os.path.dirname(__file__), "../resources/mappings.yml")
    mappings_config = load_config(mappings_config_path)
    
    db_path = sources_config.get("db", {}).get("db_path", "data/budget.db")
    con = connect_to_db(db_path, logger)
    
    try:
        # Load Silver tables
        sources = sources_config.get("sources", {})
        for source_name, source_config in sources.items():
            load_silver(con, source_name, source_config)
            
        # Load Mappings tables
        mappings = mappings_config.get("mappings", {})
        for mapping_name, mapping_config in mappings.items():
            load_mapping(con, mapping_name, mapping_config)
    finally:
        con.close()

if __name__ == "__main__":
    main()
