FROM python:3.11

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CACHE_BUST=20251007_v2

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create storage directory for CV files
RUN mkdir -p /app/storage

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .
COPY start.sh /app/start.sh
EXPOSE 8000
RUN chmod +x /app/start.sh

# Command to run the application
CMD ["/app/start.sh"] 