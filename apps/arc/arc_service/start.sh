#!/bin/bash
# Debugging info
pwd
ls -l
echo "PYTHONPATH: $PYTHONPATH"
echo "--- Starting Granian ---"

granian --interface asgi --host :: --port ${PORT:-8000} app.main:app &
granian --interface asgi --host 0.0.0.0 --port ${PORT:-8000} app.main:app 