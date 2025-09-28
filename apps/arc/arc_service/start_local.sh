#!/bin/bash
# Start the Ark service locally with correct PYTHONPATH and working directory

# Move to the service root
cd "$(dirname "$0")"

# Set PYTHONPATH to current directory (so 'app' is a package)
export PYTHONPATH=.

# Start the server with Granian (IPv6 and IPv4)
granian --interface asgi --host :: --port 8000 app.main:app &
granian --interface asgi --host 0.0.0.0 --port 8000 app.main:app
