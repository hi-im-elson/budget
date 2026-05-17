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
            "pipeline/reset_tables.py silver.amex_cobalt",
            "pipeline/table_bootstrap.py",
            "pipeline/bronze.py",
            "pipeline/silver.py"
        ]
        
        for script in scripts:
            # Run from /app so paths resolve correctly
            cmd = f"python3 {script}"
            # Splitting manually since reset_tables takes arguments
            result = subprocess.run(cmd.split(), cwd="/app", capture_output=True, text=True)
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
        result = conn.execute("""
            SELECT "source", "last_transaction_date", "last_updated"
            FROM gold.dim_source
            ORDER BY "last_updated" DESC
        """)
        rows = result.fetchall()

        recent_transactions = []
        last_refresh = None

        for row in rows:
            source_key, last_tx_date, last_updated = row
            if last_refresh is None or (last_updated and last_updated > last_refresh):
                last_refresh = last_updated
            recent_transactions.append({
                "source": display_names.get(source_key, source_key),
                "date": last_tx_date.isoformat() if hasattr(last_tx_date, 'isoformat') else str(last_tx_date),
                "last_updated": last_updated.isoformat() if hasattr(last_updated, 'isoformat') else str(last_updated),
            })

        return {"last_refresh": last_refresh, "recent_transactions": recent_transactions}
    except Exception as e:
        # Might not exist yet
        return {"last_refresh": None, "recent_transactions": []}
    finally:
        if 'conn' in locals():
            conn.close()
            