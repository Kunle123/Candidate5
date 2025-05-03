#!/bin/sh
granian --interface asgi --app main:app --host :: --port ${PORT:-8000} &
granian --interface asgi --app main:app --host 0.0.0.0 --port ${PORT:-8000} 