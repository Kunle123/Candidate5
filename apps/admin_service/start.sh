#!/bin/bash
# Bind to both IPv4 and IPv6 for Railway health checks
# Use PORT environment variable if set, otherwise default to 8080
PORT=${PORT:-8080}
echo "Starting admin service on port $PORT"
exec uvicorn app.main:app --host :: --port $PORT

