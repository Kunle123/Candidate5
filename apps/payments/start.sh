#!/bin/sh
uvicorn app.main:app --host :: --port ${PORT:-8005} 