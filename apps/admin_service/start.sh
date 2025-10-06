#!/bin/bash
# Bind to both IPv6 and IPv4 for Railway health checks
# Start on both address families like other services
PORT=${PORT:-8080}
echo "Starting admin service on port $PORT (IPv6 and IPv4)"
uvicorn app.main:app --host :: --port $PORT &
uvicorn app.main:app --host 0.0.0.0 --port $PORT

