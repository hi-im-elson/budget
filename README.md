# Data Pipeline

A configuration-driven data pipeline built with **DuckDB**, **Docker**, and **Python**. This project ingests financial data (currently American Express CSVs) and processes it through a multi-layer architecture (Bronze -> Silver) to ensure data quality and strong typing.

## 🚀 Overview

The pipeline runs in the following stages:
1.  **Table Bootstrap**: Creates necessary schema, tables, and sequences based on configuration.
2.  **Bronze Layer**: Ingests raw CSV files into DuckDB as `VARCHAR` to preserve fidelity.
3.  **Silver Layer**: Transforms, casts, and maps data into strongly-typed tables with defined schemas and primary keys.

Everything is containerized, ensuring a consistent execution environment.

## 🏗 Architecture

### Tech Stack
*   **DuckDB**: Embedded analytical database for fast SQL processing.
*   **Python**: Orchestration and logic layer.
*   **Docker**: Containerization for reproducible builds.
*   **YAML**: Centralized configuration for schemas and transformations.

### Data Flow
1.  **Raw Data**: CSV files placed in `data/raw/<source>/`.
2.  **Bronze (Raw)**: `INSERT` raw text data. No transformations.
3.  **Silver (Refined)**: 
    *   Column Mapping (e.g., "Date Processed" -> `date_processed`).
    *   Type Casting (e.g., String "05 Mar 2024" -> DATE).
    *   Primary Key Generation (e.g., Hash of filename + reference).

## 📂 Project Structure

```
├── data/                   # Local data (mounted to container)
│   ├── raw/                # Source CSVs
│   └── budget.db           # Persistent DuckDB database
├── resources/
│   └── variables.yml       # ⚙️ MAIN CONFIGURATION FILE
├── src/
│   ├── sql/
│   │   ├── table_bootstrap.py  # Creates tables from config
│   │   ├── bronze.py           # Loads raw CSVs
│   │   ├── silver.py           # Transforms to Silver
│   │   └── utils/              # Helper functions
├── scripts/
│   └── entrypoint.sh       # Pipeline runner script
└── docker-compose.yml      # Orchestration
```

## ⚙️ Configuration (`resources/variables.yml`)

This is the brain of the pipeline. You define sources, table names, and schema definitions here.

**Key Features:**
*   **`columns`**: Define schema, types, and constraints.
*   **`source_column`**: Map CSV headers to database columns.
*   **`primary_key`**: Define columns to hash for a unique ID.
*   **`csv_options`**: Configure date formats (e.g., `%d %b %Y`).

Example:
```yaml
sources:
  amex:
    input_path: "data/raw/amex/"
    csv_options:
      dateformat: "%d %b %Y"
    columns:
      - name: "id"
        type: "VARCHAR(255)"
        constraints: "NOT NULL PRIMARY KEY"
      - name: "date"
        type: "DATE"
        source_column: "Date" # Maps 'Date' from CSV to 'date' in DB
    primary_key: ["filename", "reference"] # Generates hash ID
```

## 🏃 Usage

### Prerequisites
*   Docker & Docker Compose

### Run the Pipeline
Simply bring up the container. It will build, run the pipeline, and exit.

```bash
docker-compose up --build
```

### Reset Data
To start fresh, delete the database file (if not persisted elsewhere) or drop tables manually.
```bash
rm data/budget.db
```

### 🔎 Querying Data
You can query the database interactively using the bundled DuckDB CLI:

```bash
docker-compose run --rm cli
```

Once inside the SQL shell:
```sql
-- List tables
SHOW TABLES;

-- Query Silver data
SELECT * FROM silver.amex LIMIT 5;
```

## 🛠 Extending

To add a new data source (e.g., `visa`):
1.  Add a new entry under `sources` in `resources/variables.yml`.
2.  Define `input_path`, tables, and `columns`.
3.  Place CSVs in the input path.
4.  Run `docker-compose up`.

The generic scripts (`bronze.py`, `silver.py`) will automatically pick up the new configuration and process the data.
