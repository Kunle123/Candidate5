import logging
logging.basicConfig(level=logging.DEBUG)
print("MAIN STARTED")
logging.info("MAIN LOGGER TEST")
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# ... existing code ... 