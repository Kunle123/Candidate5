#!/bin/sh
granian --interface asgi --app main:app --host :: --port ${PORT:-8000} 