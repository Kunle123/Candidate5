FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./

# Force uninstall any old openai version before installing requirements
RUN pip uninstall -y openai || true

# Force install correct OpenAI version and compatible dependencies
RUN pip install --no-cache-dir --force-reinstall openai==1.52.0
RUN pip install --no-cache-dir --force-reinstall httpx==0.25.0

# Then install other requirements
RUN pip install --no-cache-dir -r requirements.txt

RUN python -m spacy download en_core_web_sm

COPY . .
COPY prompts ./prompts

EXPOSE 8000
RUN chmod +x /app/start.sh
CMD ["/app/start.sh"]
