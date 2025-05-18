import requests
import json

# --- CONFIGURATION ---
BASE_URL = "https://api-gw-production.up.railway.app"
LOGIN_ENDPOINT = f"{BASE_URL}/api/auth/login"
ARC_DATA_ENDPOINT = f"{BASE_URL}/api/arc/data"

EMAIL = "user@example.com"
PASSWORD = "yourPassword123"

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

def fetch_arc_data(token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(ARC_DATA_ENDPOINT, headers=headers)
        print(f"[ARC DATA] Status: {resp.status_code}")
        try:
            print("[ARC DATA] Response:", json.dumps(resp.json(), indent=2))
        except Exception:
            print("[ARC DATA] Raw Response:", resp.text)
    except Exception as e:
        print(f"[ARC DATA] Exception: {e}")

if __name__ == "__main__":
    print("--- Logging in ---")
    token = login_user()
    if token:
        print("--- Fetching Arc Data ---")
        fetch_arc_data(token)
    else:
        print("[ERROR] Could not obtain token. Aborting fetch.") 