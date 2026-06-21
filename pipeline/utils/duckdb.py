import duckdb
import yaml
import logging


def load_config(config_path: str) -> dict:
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def connect_to_db(db_path: str, logger: logging.Logger) -> duckdb.DuckDBPyConnection:
    logger.info(f"Connecting to DuckDB at {db_path}...")
    try:
        con = duckdb.connect(db_path)
        logger.info(f"Connected to DuckDB at {db_path}")
        return con
    except Exception as e:
        logger.error(f"Failed to connect to DuckDB at {db_path}: {e}")
        raise


def execute(con: duckdb.DuckDBPyConnection, query: str, logger: logging.Logger) -> None:
    logger.info(f"Executing Query: {query}")
    con.execute(query)
    logger.info("Query Executed Successfully")


def parse_value_from_string_sql(source_col: str, target_col: str, target_type: str, date_format: str) -> str:
    if date_format:
        return f"CAST(STRPTIME(CAST({source_col} AS VARCHAR), '{date_format}') AS {target_type}) AS {target_col}"
    return f"CAST({source_col} AS {target_type}) AS {target_col}"


def generate_primary_key_sql(primary_key_columns: list) -> str:
    return f"SHA256({' || '.join(primary_key_columns)})"


def return_current_timestamp(target_col: str, target_type: str) -> str:
    return f"CAST(CURRENT_TIMESTAMP AS {target_type}) AS {target_col}"
