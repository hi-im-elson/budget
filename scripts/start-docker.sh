#!/bin/bash
set -e

if ! docker info > /dev/null 2>&1; then
  echo "Docker Desktop not running. Starting..."
  open -a Docker
  echo "Waiting for Docker to be ready..."
  until docker info > /dev/null 2>&1; do
    sleep 2
  done
  echo "Docker is ready."
fi

echo "Shutting down existing containers and removing orphans..."
docker-compose down -v --remove-orphans

echo "Building and starting fresh containers..."
docker-compose up -d --build --force-recreate

echo "Access the FastAPI backend at:  http://localhost:8000"
echo "Access the React Web App at:    http://localhost:5173"
