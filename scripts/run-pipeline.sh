#!/bin/bash
echo "Starting data pipeline..."

echo "Running Table Bootstrap..."
python3 pipeline/table_bootstrap.py

echo "Running Bronze Layer..."
python3 pipeline/bronze.py

echo "Running Silver Layer..."
python3 pipeline/silver.py

echo "Data pipeline completed successfully."
