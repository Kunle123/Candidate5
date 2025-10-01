FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m spacy download en_core_web_sm

COPY . .
COPY prompts ./prompts

EXPOSE 8000
RUN chmod +x /app/start.sh
CMD ["/app/start.sh"] 