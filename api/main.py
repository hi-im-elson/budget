from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import duckdb
import os
import subprocess

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
            "pipeline/reset_tables.py silver.amex",
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
        conn = duckdb.connect(database=DB_PATH, read_only=True)
        # Assuming silver.amex is the main target table as specified in variables.yml
        result = conn.execute("SELECT MAX(updated_at) FROM silver.amex")
        row = result.fetchone()
        
        timestamp = row[0] if row and row[0] else None
        return {"last_refresh": timestamp}
    except Exception as e:
        # Might not exist yet
        return {"last_refresh": None}
    finally:
        if 'conn' in locals():
            conn.close()
