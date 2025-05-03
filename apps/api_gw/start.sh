#!/bin/sh
# Start Uvicorn on both IPv6 and IPv4 for maximum compatibility
uvicorn main:app --host :: --port ${PORT} 