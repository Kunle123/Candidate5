#!/bin/sh
# Start Uvicorn on both IPv6 and IPv4 for maximum compatibility
uvicorn main:app --host :: --port ${PORT:-8000} --log-level debug --access-log &
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level debug --access-log 