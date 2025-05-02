# Dockerfile for FastAPI backend
FROM python:3.11
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh
EXPOSE 8000
CMD ["/app/start.sh"] 