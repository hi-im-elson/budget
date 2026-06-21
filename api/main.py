from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import duckdb
import os
import subprocess
import yaml

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.environ.get("DUCKDB_DATABASE", "/data/budget.db")

class QueryRequest(BaseModel):
    query: str

@app.post("/api/query")
def execute_query(request: QueryRequest):
    try:
        # We open a read_only connection to avoid blocking the pipeline writes
        conn = duckdb.connect(database=DB_PATH, read_only=True)

        result = conn.execute(request.query)

        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        
        # Format as list of dicts for the frontend table
        formatted_rows = [dict(zip(columns, row)) for row in rows]
        
        return {"columns": columns, "data": formatted_rows}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()

@app.post("/api/refresh")
def refresh_pipeline():
    try:
        scripts = [
            "pipeline/table_bootstrap.py",
            "pipeline/migrate_mappings.py",
            "pipeline/bronze.py",
            "pipeline/silver.py",
            "pipeline/gold.py"
        ]

        env = {**os.environ, "PYTHONPATH": "/app"}
        for script in scripts:
            result = subprocess.run(
                ["python3", script],
                cwd="/app",
                capture_output=True,
                text=True,
                env=env,
            )
            if result.returncode != 0:
                raise Exception(f"Script {script} failed: {result.stderr}")

        return {"status": "success", "message": "Pipeline refreshed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/last-refresh")
def get_last_refresh():
    try:
        # Load display_name mapping from config
        config_path = os.path.join(os.path.dirname(__file__), "../resources/sources.yml")
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        sources_config = config.get("sources", {})
        display_names = {
            key: src.get("display_name", key)
            for key, src in sources_config.items()
        }

        conn = duckdb.connect(database=DB_PATH, read_only=True)
        
        recent_transactions = []
        last_refresh = None

        for source_key, src in sources_config.items():
            silver_table = src.get("silver_table")
            tx_date_col = src.get("transaction_date")
            if not silver_table or not tx_date_col:
                continue

            # Parse schema and table name to check existence
            table_parts = silver_table.split('.')
            schema_name = table_parts[0] if len(table_parts) > 1 else 'main'
            table_name = table_parts[-1]

            try:
                table_check = conn.execute(
                    f"SELECT 1 FROM information_schema.tables WHERE table_schema = '{schema_name}' AND table_name = '{table_name}'"
                ).fetchone()
            except Exception:
                table_check = False

            if not table_check:
                continue

            try:
                res = conn.execute(f"""
                    SELECT MAX("{tx_date_col}") AS last_tx_date, MAX(updated_at) AS last_updated
                    FROM {silver_table}
                    HAVING MAX("{tx_date_col}") IS NOT NULL
                """).fetchone()
                if res and res[0] is not None:
                    last_tx_date, last_updated = res
                    recent_transactions.append({
                        "source": display_names.get(source_key, source_key),
                        "date": last_tx_date.isoformat() if hasattr(last_tx_date, 'isoformat') else str(last_tx_date),
                        "last_updated": last_updated.isoformat() if hasattr(last_updated, 'isoformat') else str(last_updated),
                    })
            except Exception:
                pass

        if recent_transactions:
            # Sort by last_updated descending
            recent_transactions.sort(key=lambda x: x["last_updated"], reverse=True)
            last_refresh = recent_transactions[0]["last_updated"]

        return {"last_refresh": last_refresh, "recent_transactions": recent_transactions}
    except Exception as e:
        return {"last_refresh": None, "recent_transactions": []}
    finally:
        if 'conn' in locals():
            conn.close()

            