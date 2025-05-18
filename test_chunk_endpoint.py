import requests
import json

BASE_URL = "https://api-gw-production.up.railway.app"
LOGIN_ENDPOINT = f"{BASE_URL}/api/auth/login"
KEYWORDS_ENDPOINT = f"{BASE_URL}/api/arc/ai/keywords"

EMAIL = "user@example.com"
PASSWORD = "yourPassword123"

SAMPLE_JOB_DESCRIPTION = "We are seeking a Python developer with experience in FastAPI, cloud platforms (AWS, Azure), and CI/CD pipelines. The ideal candidate will have a background in agile methodologies and strong communication skills."

def login_user():
    data = {"email": EMAIL, "password": PASSWORD}
    try:
        resp = requests.post(LOGIN_ENDPOINT, json=data)
        if resp.status_code == 200:
            token = resp.json().get("access_token") or resp.json().get("token")
            if token:
                print(f"[LOGIN] Success. Token: {token[:20]}...\n")
                return token
            else:
                print(f"[LOGIN] No token in response: {resp.text}")
        else:
            print(f"[LOGIN] Failed: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"[LOGIN] Exception: {e}")
    return None

def test_keywords_endpoint(token):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    data = {"jobDescription": SAMPLE_JOB_DESCRIPTION}
    try:
        resp = requests.post(KEYWORDS_ENDPOINT, headers=headers, data=json.dumps(data))
        print(f"[KEYWORDS TEST] Status: {resp.status_code}")
        try:
            print("[KEYWORDS TEST] Response:", json.dumps(resp.json(), indent=2))
        except Exception:
            print("[KEYWORDS TEST] Raw Response:", resp.text)
    except Exception as e:
        print(f"[KEYWORDS TEST] Exception: {e}")

if __name__ == "__main__":
    print("--- Logging in ---")
    token = login_user()
    if token:
        print("--- Testing /ai/keywords endpoint ---")
        test_keywords_endpoint(token)
    else:
        print("[ERROR] Could not obtain token. Aborting test.") 