#!/bin/sh
granian --interface asgi --host :: --port 8000 main:app &
granian --interface asgi --host 0.0.0.0 --port 8000 main:app 