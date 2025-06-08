# API Gateway Update: Exposing /search_jobs for Job Agent

This document explains how to update your API Gateway to expose and route the `/search_jobs` endpoint for the job_agent service.

---

## 1. Routing Configuration

Add a new route for `/search_jobs` in your API Gateway configuration. The route should forward requests to your deployed job_agent service (e.g., on Railway or another platform).

### Example (YAML, Kong, KrakenD, or Express Gateway):
```yaml
routes:
  - name: jobagent-search-jobs
    paths:
      - /search_jobs
    methods: [POST]
    service: jobagent-service
    strip_path: false
```

### Example (NGINX):
```nginx
location /search_jobs {
    proxy_pass http://jobagent-service:8000/search_jobs;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

### Example (FastAPI Gateway):
```python
from fastapi import APIRouter, Request
import httpx

router = APIRouter()

@router.post("/search_jobs")
async def search_jobs_proxy(request: Request):
    body = await request.body()
    headers = dict(request.headers)
    async with httpx.AsyncClient() as client:
        resp = await client.post("http://jobagent-service:8000/search_jobs", content=body, headers=headers)
    return resp.json()
```

---

## 2. (Optional) API Documentation
If your gateway aggregates OpenAPI specs, add the `/search_jobs` endpoint to the docs.

---

## 3. (Optional) Auth Rules
Ensure the route requires the `Authorization: Bearer <token>` header, if your gateway handles authentication.

---

## 4. Testing
After updating the gateway, test the endpoint:
```sh
curl -X POST https://<your-api-gateway-domain>/search_jobs \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"search_params": {"keywords": "python", "location": "London"}}'
```

---

For further questions, contact the backend or DevOps team. 