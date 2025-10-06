#!/bin/bash
# Bind to both IPv4 and IPv6 for Railway health checks
exec uvicorn app.main:app --host :: --port 8080

