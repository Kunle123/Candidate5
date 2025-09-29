import httpx

async def get_user_profile(user_id: str, token: str) -> dict:
    url = f"https://api-gw-production.up.railway.app/api/v1/users/{user_id}/all_sections"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()
