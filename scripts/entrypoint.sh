#!/bin/bash
set -e

export PYTHONPATH=/app

if [ -f "/app/data/budget.db" ]; then
    echo "Database /app/data/budget.db already exists. Skipping initial pipeline run."
    echo "Use the Refresh Pipeline feature to reload data."
else
    echo "Starting data pipeline..."

    echo "Running Table Bootstrap..."
    python3 pipeline/table_bootstrap.py

    echo "Running Migrate Mappings..."
    python3 pipeline/migrate_mappings.py

    echo "Running Bronze Layer..."
    python3 pipeline/bronze.py

    echo "Running Silver Layer..."
    python3 pipeline/silver.py

    echo "Running Gold Layer..."
    python3 pipeline/gold.py

    echo "Data pipeline completed successfully."
fi
