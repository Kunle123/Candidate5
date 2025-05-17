from fastapi import FastAPI

app = FastAPI(title="Career Ark (Arc) Service", description="API for Career Ark data extraction, deduplication, and application material generation.")

@app.get("/health")
async def health():
    return {"status": "ok"} 