from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
async def health_check_root():
    return {"status": "ok"}