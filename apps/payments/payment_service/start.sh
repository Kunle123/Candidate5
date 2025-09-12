#!/bin/sh
uvicorn main:app --host :: --port ${PORT:-8000} --log-level debug --access-log &
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level debug --access-log 