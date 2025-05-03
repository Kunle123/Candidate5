#!/bin/sh
uvicorn main:app --host :: --port ${PORT:-8000} &
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} 