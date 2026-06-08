import os
import duckdb
import sys
import csv
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from pipeline.utils.duckdb import (
    connect_to_db,
    load_config,
    execute,
    execute_multiple,
)
from pipeline.utils.logger import create_logger

logger = create_logger("table_bootstrap.log")


def get_sources(config: dict) -> dict:
    return config.get("sources", {})


def create_bronze_tables(con: duckdb.DuckDBPyConnection, config: dict):
    sources = get_sources(config)

    for source_name, source_config in sources.items():
        logger.info(f"Setting up tables for source: {source_name}")

        csv_path = source_config.get("input_path")
        bronze_table = source_config.get("bronze_table")
        csv_file = os.listdir(csv_path)[0]

        if csv_path and bronze_table:
            logger.info(f"Creating bronze table {bronze_table} (if not exists)...")
            create_query = f"""
                CREATE TABLE IF NOT EXISTS {bronze_table} AS
                SELECT * FROM read_csv('{csv_path}/{csv_file}', auto_detect=true, filename=true) LIMIT 0
            """
            execute(con, create_query, logger)


def generate_ddl(table_name: str, source_config: dict) -> str:
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
    sources = config.get("sources", {})

    for source_name, source_config in sources.items():
        silver_table = source_config.get("silver_table")
        columns_config: list[dict] = source_config.get("columns")

        if silver_table and columns_config:
            logger.info(f"Creating silver table {silver_table} (if not exists)...")
            try:
                create_query = generate_ddl(silver_table, source_config)
                execute(con, create_query, logger)
            except Exception as e:
                logger.error(f"Failed to create silver table for {source_name}: {e}")
                raise


def generate_mappings_ddl(table_name: str, table_config: dict) -> str:
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
    CREATE TABLE IF NOT EXISTS {table_name} (
        {",\n".join(columns_definitions)}
    );"""
    return ddl


def load_mappings_csv(
    con: duckdb.DuckDBPyConnection,
    table_name: str,
    table_config: dict,
    csv_path: str,
) -> None:
    """
    Inserts CSV rows that don't already exist, keyed on `unique_key` from config.
    Safe to re-run: rows present in the table are skipped, not duplicated.
    """
    insert_cols = table_config.get("insert_columns", [])
    fk_lookup = table_config.get("foreign_key_lookup")
    unique_key: list[str] = table_config.get("unique_key", [])

    if not unique_key:
        logger.warning(
            f"{table_name}: no unique_key defined — skipping load to avoid duplicates. "
            "Add unique_key to mappings.yml to enable idempotent seeding."
        )
        return

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [h.strip() for h in reader.fieldnames]
        for row in reader:
            row = {k.strip(): v for k, v in row.items()}
            values: list = []
            col_names: list[str] = []

            for col in insert_cols:
                col_names.append(col.get("insert_column", col["name"]))
                raw = row.get(col["source"], "")
                val = raw.strip() if raw else None
                if col.get("nullable") and not val:
                    val = None
                values.append(val)

            if fk_lookup:
                source_val = row.get(fk_lookup["source_column"], "").strip()
                result = con.execute(
                    f"SELECT {fk_lookup['return_column']} FROM {fk_lookup['lookup_table']} "
                    f"WHERE {fk_lookup['lookup_column']} = ?",
                    [source_val],
                ).fetchone()
                col_names.append(fk_lookup["insert_column"])
                values.append(result[0] if result else None)

            # Build WHERE NOT EXISTS guard using the declared natural key columns.
            # Only the key columns that are part of insert_cols are compared;
            # fk_lookup column is intentionally excluded from the key check.
            key_conditions = " AND ".join(
                f"{col} = ?" for col in unique_key
            )
            key_values = [
                values[col_names.index(col)]
                for col in unique_key
                if col in col_names
            ]

            placeholders = ", ".join(["?"] * len(values))
            cols_str = ", ".join(col_names)

            con.execute(
                f"""
                INSERT INTO {table_name} ({cols_str})
                SELECT {placeholders}
                WHERE NOT EXISTS (
                    SELECT 1 FROM {table_name} WHERE {key_conditions}
                )
                """,
                values + key_values,
            )


def create_mappings_tables(con: duckdb.DuckDBPyConnection, mappings_config: dict):
    project_root = os.path.join(os.path.dirname(__file__), "..")
    mappings_dir = os.path.join(project_root, "data", "mappings")

    for table_key, table_config in mappings_config.get("mappings", {}).items():
        table_name = table_config.get("table")
        csv_file = table_config.get("csv_file")
        csv_path = os.path.join(mappings_dir, csv_file)

        logger.info(f"Creating mappings table {table_name} (if not exists)...")
        ddl = generate_mappings_ddl(table_name, table_config)
        execute(con, ddl, logger)

        logger.info(f"Loading {csv_file} into {table_name} (skipping existing rows)...")
        load_mappings_csv(con, table_name, table_config, csv_path)
        logger.info(f"{table_name} load complete.")


def bootstrap_postgres() -> None:
    schema_path = Path(__file__).parent / "db" / "schema.sql"
    sql = schema_path.read_text()
    from pipeline.utils.postgres import execute as pg_execute
    pg_execute(sql)
    logger.info("Postgres schema bootstrapped (IF NOT EXISTS — safe to re-run)")


def check_postgres() -> None:
    """Verify Postgres is reachable before any work begins. Fails fast and loud."""
    from pipeline.utils.postgres import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
    logger.info("Postgres preflight check passed.")


def main():
    sources_config_path = os.path.join(os.path.dirname(__file__), "../resources/sources.yml")
    config = load_config(sources_config_path)

    mappings_config_path = os.path.join(os.path.dirname(__file__), "../resources/mappings.yml")
    mappings_config = load_config(mappings_config_path)

    # Validate Postgres connectivity before touching DuckDB — fail fast, no partial state.
    check_postgres()

    db_path = config.get("db", {}).get("db_path", "data/budget.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    con = connect_to_db(db_path, logger)

    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS bronze;")
        con.execute("CREATE SCHEMA IF NOT EXISTS silver;")
        con.execute("CREATE SCHEMA IF NOT EXISTS gold;")
        con.execute("CREATE SCHEMA IF NOT EXISTS mappings;")

        create_bronze_tables(con, config)
        create_silver_tables(con, config)
        create_mappings_tables(con, mappings_config)
        logger.info("DuckDB bootstrap complete.")
    finally:
        con.close()

    bootstrap_postgres()
    logger.info("Table bootstrap complete.")


if __name__ == "__main__":
    main()
