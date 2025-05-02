FROM python:3.9-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN echo '#!/bin/bash\n\
PORT="${PORT:-8000}"\n\
echo "Starting API Gateway on port $PORT (IPv6)"\n\
# Bind to IPv6 for Railway private networking\n\
exec uvicorn main:app --host :: --port $PORT --workers ${UVICORN_WORKERS:-1}\n\
' > /app/start.sh && chmod +x /app/start.sh

CMD ["/app/start.sh"] 