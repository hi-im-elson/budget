import os
import duckdb
import sys
import csv

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
    CREATE OR REPLACE TABLE {table_name} (
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

def generate_mappings_ddl(table_name: str, table_config: dict) -> str:
    """
    Generates CREATE SEQUENCE and CREATE TABLE statements for a mappings table.
    """
    seq_name = f"{table_name}_id_seq"
    ddl = f"CREATE SEQUENCE IF NOT EXISTS {seq_name} START 1;"

    columns_definitions: list[str] = []
    for col in table_config.get("columns", []):
        name: str = col.get("name")
        col_type: str = col.get("type")
        constraints: str = col.get("constraints", "")
        definition = f'"{name}" {col_type}'
        if constraints:
            definition += f" {constraints}"
        if col.get("auto_increment"):
            definition += f" DEFAULT nextval('{seq_name}')"
        columns_definitions.append(definition)

    ddl += f"""
    CREATE OR REPLACE TABLE {table_name} (
        {",\n".join(columns_definitions)}
    );"""
    return ddl


def load_mappings_csv(
    con: duckdb.DuckDBPyConnection, 
    table_name: str, 
    table_config: dict, 
    csv_path: str
    ):
    """
    Loads a single mappings CSV into its table, resolving any foreign key lookups.
    """
    insert_cols = table_config.get("insert_columns", [])
    fk_lookup = table_config.get("foreign_key_lookup")

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        # Normalise header keys (strip leading/trailing whitespace)
        reader.fieldnames = [h.strip() for h in reader.fieldnames]
        for row in reader:
            row = {k.strip(): v for k, v in row.items()}
            values = []
            col_names = []

            for col in insert_cols:
                col_names.append(col["insert_column"] if "insert_column" in col else col["name"])
                raw = row.get(col["source"], "")
                val = raw.strip() if raw else None
                if col.get("nullable") and not val:
                    val = None
                values.append(val)

            if fk_lookup:
                source_val = row.get(fk_lookup["source_column"], "").strip()
                result = con.execute(
                    f"SELECT {fk_lookup['return_column']} FROM {fk_lookup['lookup_table']} WHERE {fk_lookup['lookup_column']} = ?",
                    [source_val],
                ).fetchone()
                col_names.append(fk_lookup["insert_column"])
                values.append(result[0] if result else None)

            placeholders = ", ".join(["?"] * len(values))
            cols_str = ", ".join(col_names)
            con.execute(
                f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})",
                values,
            )


def create_mappings_tables(con: duckdb.DuckDBPyConnection, mappings_config: dict):
    """
    Creates the mappings schema tables and loads data from CSV files.
    Configuration is driven by resources/mappings.yml.
    """
    project_root = os.path.join(os.path.dirname(__file__), "..")
    mappings_dir = os.path.join(project_root, "data", "mappings")

    for table_key, table_config in mappings_config.get("mappings", {}).items():
        table_name = table_config.get("table")
        csv_file = table_config.get("csv_file")
        csv_path = os.path.join(mappings_dir, csv_file)

        logger.info(f"Creating mappings table {table_name}...")
        ddl = generate_mappings_ddl(table_name, table_config)
        execute(con, ddl, logger)

        logger.info(f"Loading {csv_file} into {table_name}...")
        load_mappings_csv(con, table_name, table_config, csv_path)
        logger.info(f"{table_name} loaded.")


def main():

    sources_config_path = os.path.join(os.path.dirname(__file__), "../resources/sources.yml")
    config = load_config(sources_config_path)

    mappings_config_path = os.path.join(os.path.dirname(__file__), "../resources/mappings.yml")
    mappings_config = load_config(mappings_config_path)

    db_path = config.get("db", {}).get("db_path", "data/budget.db")

    # Ensure DB directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    con = connect_to_db(db_path, logger)

    try:
        # Create schemas (ensure they exist first)
        con.execute("CREATE SCHEMA IF NOT EXISTS bronze;")
        con.execute("CREATE SCHEMA IF NOT EXISTS silver;")
        con.execute("CREATE SCHEMA IF NOT EXISTS gold;")
        con.execute("CREATE SCHEMA IF NOT EXISTS mappings;")

        create_bronze_tables(con, config)
        create_silver_tables(con, config)
        create_mappings_tables(con, mappings_config)
        logger.info("Table bootstrap complete.")
    finally:
        con.close()

if __name__ == "__main__":
    main()
