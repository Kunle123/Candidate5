import logging
logging.basicConfig(level=logging.DEBUG)
print("MAIN STARTED")
logging.info("MAIN LOGGER TEST")
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
async def health_check():
    print("HEALTH ENDPOINT CALLED")
    logging.info("HEALTH LOGGER TEST")
    return {"status": "ok"}

# ... existing code ... 