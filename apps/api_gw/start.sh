#!/bin/sh
uvicorn main:app --host :: --port ${PORT:-8000} 