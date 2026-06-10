import hashlib
import os
import duckdb

from pipeline.utils.duckdb import (
    connect_to_db,
    load_config,
    execute,
)
from pipeline.utils.logger import create_logger

logger = create_logger("bronze.log")

_INGESTION_LOG_TABLE = "mappings.ingestion_log"

_CREATE_INGESTION_LOG = f"""
CREATE TABLE IF NOT EXISTS {_INGESTION_LOG_TABLE} (
    file_name     VARCHAR PRIMARY KEY,
    file_hash     VARCHAR(64)  NOT NULL,
    last_modified TIMESTAMP    NOT NULL,
    row_count     INTEGER      NOT NULL,
    loaded_at     TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);
"""


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _log_entry(con: duckdb.DuckDBPyConnection, rel_name: str) -> dict | None:
    row = con.execute(
        f"SELECT file_hash, last_modified FROM {_INGESTION_LOG_TABLE} WHERE file_name = ?",
        [rel_name],
    ).fetchone()
    return {"file_hash": row[0], "last_modified": str(row[1])} if row else None


def _upsert_log(
    con: duckdb.DuckDBPyConnection,
    rel_name: str,
    file_hash: str,
    mtime: float,
    row_count: int,
) -> None:
    con.execute(
        f"""
        INSERT INTO {_INGESTION_LOG_TABLE} (file_name, file_hash, last_modified, row_count, loaded_at)
        VALUES (?, ?, to_timestamp(?), ?, CURRENT_TIMESTAMP)
        ON CONFLICT (file_name) DO UPDATE SET
            file_hash     = excluded.file_hash,
            last_modified = excluded.last_modified,
            row_count     = excluded.row_count,
            loaded_at     = excluded.loaded_at
        """,
        [rel_name, file_hash, mtime, row_count],
    )


def _rel_name(abs_path: str) -> str:
    """Extract the path segment after data/raw/csv/ for use as the stable file key."""
    match = abs_path.split("data/raw/csv/", 1)
    return match[1] if len(match) == 2 else os.path.basename(abs_path)


def load_bronze(con: duckdb.DuckDBPyConnection, source_name: str, config: dict) -> None:
    csv_path = config.get("input_path")
    table_name = config.get("bronze_table")

    if not csv_path or not table_name:
        logger.warning(f"Skipping {source_name}: missing input_path or bronze_table in config")
        return

    execute(con, _CREATE_INGESTION_LOG, logger)

    logger.info(f"Loading bronze layer for {source_name} from {csv_path}...")

    files = con.execute(f"SELECT * FROM glob('{csv_path}/**/*.csv')").fetchall()
    if not files:
        logger.warning(f"No CSV files found at {csv_path}. Skipping.")
        return

    for (abs_path,) in files:
        rel_name = _rel_name(abs_path)
        current_hash = _md5(abs_path)
        current_mtime = os.path.getmtime(abs_path)
        existing = _log_entry(con, rel_name)

        if existing and existing["file_hash"] == current_hash:
            logger.info(f"Skipping unchanged file: {rel_name}")
            continue

        if existing:
            logger.info(f"File changed — replacing bronze rows for: {rel_name}")
            con.execute(
                f"DELETE FROM {table_name} WHERE filename = ?", [rel_name]
            )
        else:
            logger.info(f"New file — inserting into bronze: {rel_name}")

        con.execute(
            f"""
            INSERT INTO {table_name}
            SELECT * EXCLUDE (filename),
                   REGEXP_EXTRACT(filename, 'data/raw/csv/(.*)', 1) AS filename
            FROM read_csv('{abs_path}', all_varchar=false, filename=true, sep=',')
            """
        )

        row_count = con.execute(
            f"SELECT COUNT(*) FROM {table_name} WHERE filename = ?", [rel_name]
        ).fetchone()[0]

        _upsert_log(con, rel_name, current_hash, current_mtime, row_count)
        logger.info(f"Ingested {row_count} rows from {rel_name}")

    logger.info(f"Bronze load complete for {source_name}.")


def main():
    config_path = os.path.join(os.path.dirname(__file__), "../resources/sources.yml")
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
