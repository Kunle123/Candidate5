FROM python:3.9-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create storage directory for CV files
RUN mkdir -p /app/storage

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create and configure start script
RUN echo '#!/bin/bash\n\
PORT="${PORT:-8003}"\n\
echo "Starting server on port $PORT"\n\
# Use host :: to enable IPv6 for Railway internal networking
exec uvicorn app.main:app --host :: --port $PORT --workers ${UVICORN_WORKERS:-1}\n\
' > /app/start.sh && chmod +x /app/start.sh

# Command to run the application
CMD ["/app/start.sh"] 