import os
import duckdb
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from pipeline.utils.duckdb import (
    connect_to_db, 
    load_config, 
    execute, 
    execute_multiple
)

from pipeline.utils.logger import create_logger

logger = create_logger("table_bootstrap.log")


def get_sources(config: dict) -> dict:
    
    return config.get("sources", {})


def create_bronze_tables(con: duckdb.DuckDBPyConnection, config: dict):
    """
    Creates bronze and silver tables based on configuration.
    """
    sources = get_sources(config)
    
    for source_name, source_config in sources.items():
        logger.info(f"Setting up tables for source: {source_name}")
        
        # Bronze Table Creation
        csv_path = source_config.get("input_path")
        bronze_table = source_config.get("bronze_table")
        csv_file = os.listdir(csv_path)[0]
        
        if csv_path and bronze_table:
            logger.info(f"Creating bronze table {bronze_table}...")
            # Create table if not exists (infer schema from CSV)
            create_query = f"""
                CREATE OR REPLACE TABLE {bronze_table} AS 
                SELECT * FROM read_csv('{csv_path}/{csv_file}', auto_detect=true, filename=true) LIMIT 0
            """
            execute(con, create_query, logger)


def generate_ddl(table_name: str, source_config: dict) -> str:
    """
    Generates CREATE TABLE statement from columns configuration for silver tables.
    """

    primary_key: list[str] = source_config.get("primary_key", [])

    ddl: str = f"CREATE SEQUENCE IF NOT EXISTS {table_name}_id_seq START 1;" if not primary_key else ""

    columns_definitions: list[str] = []

    columns_config: list[dict] = source_config.get("columns", [])
    
    for col in columns_config:
        name: str = col.get("name")
        col_type: str = col.get("type")
        constraints: str = col.get("constraints", "")
        default: str = col.get("default")
        
        definition: str = f'"{name}" {col_type}'
            
        if constraints:
            definition += f" {constraints}"

        if name == "id" and not primary_key:
            default = f"nextval('{table_name}_id_seq')"

        if default:
            definition += f" DEFAULT {default}"
            
        columns_definitions.append(definition)
    
    ddl += f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        {",\n".join(columns_definitions)}
    );"""

    return ddl

def create_silver_tables(con: duckdb.DuckDBPyConnection, config: dict):
    """
    Creates silver tables based on configuration.
    """
    sources = config.get("sources", {})
    
    for source_name, source_config in sources.items():
        silver_table = source_config.get("silver_table")
        columns_config: list[dict] = source_config.get("columns")
        
        if silver_table and columns_config:
            logger.info(f"Creating silver table {silver_table} from config...")
            try:
                create_query = generate_ddl(silver_table, source_config)
                execute(con, create_query, logger)
            except Exception as e:
                logger.error(f"Failed to create silver table for {source_name}: {e}")
                raise

def main():
    
    config_path = os.path.join(os.path.dirname(__file__), "../resources/variables.yml")
    config = load_config(config_path)
    
    db_path = config.get("db", {}).get("db_path", "data/budget.db")
    
    # Ensure DB directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    con = connect_to_db(db_path, logger)
    
    try:
        # Create schemas (ensure they exist first)
        con.execute("CREATE SCHEMA IF NOT EXISTS bronze;")
        con.execute("CREATE SCHEMA IF NOT EXISTS silver;")
        con.execute("CREATE SCHEMA IF NOT EXISTS gold;")
        
        create_bronze_tables(con, config)
        create_silver_tables(con, config)
        logger.info("Table bootstrap complete.")
    finally:
        con.close()

if __name__ == "__main__":
    main()
