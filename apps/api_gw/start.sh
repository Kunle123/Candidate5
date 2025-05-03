#!/bin/sh
# Start Uvicorn on both IPv6 and IPv4 for maximum compatibility
uvicorn main:app --host :: --port ${PORT:-8000} &
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} 