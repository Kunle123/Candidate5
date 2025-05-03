# Dockerfile for FastAPI backend
FROM python:3.11
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
RUN chmod +x /app/start.sh
CMD ["/app/start.sh"] 