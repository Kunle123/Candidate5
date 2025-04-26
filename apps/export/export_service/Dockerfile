FROM python:3.11-slim

WORKDIR /app

# Install core dependencies first
RUN pip install --no-cache-dir fastapi==0.109.0 uvicorn==0.26.0 pydantic==2.6.1 email-validator 

# Install specialized dependencies for PDF generation
RUN pip install --no-cache-dir httpx==0.24.1 PyJWT==2.7.0

# Create exports directory
RUN mkdir -p /app/exports && chmod 777 /app/exports

# Copy app file
COPY ./app.py .

# Set Python path and other environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV EXPORT_DIR=/app/exports

# Create a startup script
RUN echo '#!/bin/bash\n\
PORT="${PORT:-8003}"\n\
echo "Starting export service on port $PORT"\n\
exec uvicorn app:app --host 0.0.0.0 --port $PORT\n\
' > /app/start.sh && chmod +x /app/start.sh

# Use the startup script
CMD ["/app/start.sh"] 