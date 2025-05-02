# Railway Deployment: Dynamic Port Configuration Guide

This guide explains how to ensure your services work reliably on Railway (or any platform that assigns a dynamic port) by using the `$PORT` environment variable correctly.

---

## Problem: Hardcoded Port Numbers
- Hardcoding ports (e.g., `--port 8000`) in your Dockerfile or code will cause Railway health checks and routing to fail, because Railway assigns a random port to each service and sets it in the `$PORT` environment variable.

## Why the Usual Docker CMD Fails
- Using the JSON array form in Dockerfile:
  ```dockerfile
  CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "$PORT"]
  ```
  does **not** expand `$PORT`—it passes the literal string `"$PORT"` to Uvicorn, which is not a valid integer.

---

## Solution: Use a Shell Script Entrypoint

### 1. Create a `start.sh` Script
Place this in your service directory:
```sh
#!/bin/sh
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
```
- Adjust `main:app` if your entrypoint is different.

### 2. Update Your Dockerfile
Add these lines:
```dockerfile
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh
```
Set the entrypoint:
```dockerfile
CMD ["/app/start.sh"]
```

### 3. Remove Hardcoded `PORT` from Environment
- **Do not** set a `PORT` variable manually in Railway or in your `railway.json`.
- Let Railway assign the port and inject it as the `$PORT` environment variable.

---

## Example Dockerfile Section
```dockerfile
FROM python:3.9-slim
WORKDIR /app
# ... other setup ...
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh
CMD ["/app/start.sh"]
```

---

## Why This Works
- The shell script expands `${PORT}` at runtime, so your app always listens on the port Railway expects.
- This ensures health checks and routing work for every deploy.

---

## Summary Table
| Step                | What to Do                                      |
|---------------------|-------------------------------------------------|
| Entrypoint          | Use a shell script (`start.sh`)                 |
| Dockerfile CMD      | `CMD ["/app/start.sh"]`                         |
| Port usage          | Use `${PORT}` in the script, not hardcoded      |
| Railway env         | Do NOT set `PORT` manually                      |

---

## Applying to Other Services
1. Create a `start.sh` script as above in each service directory.
2. Update the Dockerfile to use the script as the entrypoint.
3. Remove any hardcoded `PORT` from Railway or your environment.
4. Redeploy the service.

---

If you need a template or want to automate this for all your services, you can copy this pattern for each one.

---

## Important: Do Not Override the Dockerfile CMD or Hardcode the Port in Railway

- **Do not set a custom start command** (like `uvicorn main:app --host 0.0.0.0 --port 8000`) in the Railway service settings. Leave the start command blank so Railway uses your Dockerfile's `CMD`.
- **Do not set a `PORT` environment variable manually** in Railway or in your `.env` files. Railway will inject the correct port at runtime.
- **Always use the shell script and Dockerfile CMD pattern described above** to ensure your app listens on the correct port.

### Where to Check and Remove Hardcoded Commands

1. **Railway Dashboard:**
   - Go to your service's settings in Railway.
   - Look for any "Start Command" or "Override Command" fields.
   - If you see a hardcoded command (e.g., `uvicorn main:app --host 0.0.0.0 --port 8000`), **clear it** so Railway uses the Dockerfile's CMD.

2. **Dockerfile:**
   - Use:
     ```dockerfile
     CMD ["/app/start.sh"]
     ```

3. **start.sh:**
   - Use:
     ```sh
     uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
     ```

4. **Environment Variables:**
   - Do **not** set a `PORT` variable manually in Railway or your environment.

---

## Why This Matters
- Overriding the start command or hardcoding the port will break Railway's dynamic port assignment and cause health checks to fail.
- Letting Railway and your Dockerfile handle the port ensures reliable deployments and service availability. 