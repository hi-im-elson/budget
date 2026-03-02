#!/bin/bash
set -e

echo "Shutting down existing containers and removing orphans..."
docker-compose down -v --remove-orphans

echo "Building and starting fresh containers..."
docker-compose up -d --build --force-recreate

echo "Access the FastAPI backend at:  http://localhost:8000"
echo "Access the React Web App at:    http://localhost:5173"
