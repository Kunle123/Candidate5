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

@app.get("/debug-logs")
async def debug_logs():
    print("🔥 ROUTE PRINT TEST")
    logging.info("🔥 ROUTE LOGGER TEST")
    return {"message": "Check logs for debug output"} 