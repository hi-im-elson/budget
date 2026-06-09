FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y tzdata && rm -rf /var/lib/apt/lists/*
RUN pip install duckdb PyYAML fastapi uvicorn pydantic pytz

COPY pyproject.toml .
COPY pipeline/ ./pipeline/
RUN pip install -e .

COPY data /app/data
COPY scripts /app/scripts
COPY resources /app/resources

CMD ["/app/scripts/entrypoint.sh"]
