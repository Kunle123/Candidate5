FROM python:3.11

WORKDIR /app

# Set environment variables ch
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
RUN chmod +x /app/start.sh
CMD ["/app/start.sh"] 