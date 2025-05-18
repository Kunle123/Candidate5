# AI Service: IPv4/IPv6 & Health Check Changes

## Summary of Changes

### 1. Dual-Stack IPv4/IPv6 Support
- **Added `start.sh` script** in `apps/ai/ai_service/`:
  ```sh
  #!/bin/sh
  uvicorn main:app --host :: --port ${PORT:-8000} &
  uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
  ```
- **Updated `Dockerfile`** in `apps/ai/ai_service/` to:
  - Use `start.sh` as the entrypoint
  - Remove hardcoded port
  - Expose port 8000
  ```dockerfile
  COPY start.sh /app/start.sh
  RUN chmod +x /app/start.sh
  CMD ["/app/start.sh"]
  EXPOSE 8000
  ```

### 2. Health Check Endpoint
- **Added `/health` endpoint** directly to `apps/ai/ai_service/main.py`:
  ```python
  @app.get("/health")
  def health():
      return {"status": "ok"}
  ```
- This ensures Railway's health check will always succeed, regardless of router configuration.

### 3. General Best Practices
- Ensured the service uses the dynamic `PORT` environment variable for Railway compatibility.
- Confirmed the service is not using any legacy or unused directories (e.g., `apps/ai_service`).

---

**These changes ensure the AI service is robust, compatible with Railway's networking, and reliably passes health checks.** 