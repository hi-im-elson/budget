#!/bin/bash
set -e

export PYTHONPATH=/app

echo "Starting data pipeline..."

echo "Running Table Bootstrap..."
python3 src/sql/table_bootstrap.py

echo "Running Bronze Layer..."
python3 src/sql/bronze.py

echo "Running Silver Layer..."
python3 src/sql/silver.py

echo "Data pipeline completed successfully."
