import requests
import json

# --- CONFIGURATION ---
BASE_URL = "https://api-gw-production.up.railway.app"
REGISTER_ENDPOINT = f"{BASE_URL}/api/auth/register"
LOGIN_ENDPOINT = f"{BASE_URL}/api/auth/login"
UPLOAD_ENDPOINT = f"{BASE_URL}/api/arc/cv"  # Career Ark parsing endpoint

# User credentials (edit as needed)
NAME = "John Doe"
EMAIL = "user@example.com"
PASSWORD = "yourPassword123"

# Path to the CV file to upload (edit as needed)
CV_FILE_PATH = "Kunle Ibidun -  Integration and App CV - Jan 25.docx"

# --- REGISTER USER ---
def register_user():
    data = {"name": NAME, "email": EMAIL, "password": PASSWORD}
    try:
        resp = requests.post(REGISTER_ENDPOINT, json=data)
        if resp.status_code == 201 or resp.status_code == 200:
            print("[REGISTER] Success.")
        elif resp.status_code == 409:
            print("[REGISTER] User already exists. Proceeding to login...")
        else:
            print(f"[REGISTER] Failed: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"[REGISTER] Exception: {e}")

# --- LOGIN USER ---
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

# --- UPLOAD CV ---
def upload_cv(token):
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": open(CV_FILE_PATH, "rb")}
    try:
        resp = requests.post(UPLOAD_ENDPOINT, headers=headers, files=files)
        print(f"[UPLOAD] Status: {resp.status_code}")
        try:
            print("[UPLOAD] Response:", json.dumps(resp.json(), indent=2))
        except Exception:
            print("[UPLOAD] Raw Response:", resp.text)
    except Exception as e:
        print(f"[UPLOAD] Exception: {e}")

if __name__ == "__main__":
    print("--- Registering user ---")
    register_user()
    print("--- Logging in ---")
    token = login_user()
    if token:
        print("--- Uploading CV ---")
        upload_cv(token)
    else:
        print("[ERROR] Could not obtain token. Aborting upload.") 