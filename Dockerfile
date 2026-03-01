FROM python:3.13-slim

WORKDIR /app

RUN pip install duckdb PyYAML

COPY data /app/data
COPY src /app/src
COPY scripts /app/scripts
COPY resources /app/resources

CMD ["/app/scripts/entrypoint.sh"]
