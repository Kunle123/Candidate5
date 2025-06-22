import requests

API_BASE = "https://api-gw-production.up.railway.app"
EMAIL = "kunle2000@gmail.com"
PASSWORD = "Andorra09"

def login():
    url = f"{API_BASE}/api/auth/login"
    payload = {"email": EMAIL, "password": PASSWORD}
    resp = requests.post(url, json=payload)
    print("Login response:", resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.json()["token"]

def fetch_ark_profile(token):
    url = f"{API_BASE}/api/career-ark/profiles/me"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    print("Ark profile response:", resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.json()

def generate_cv(token, ark_data, job_description):
    url = f"{API_BASE}/api/career-ark/generate"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "jobAdvert": job_description,
        "arcData": ark_data
    }
    print("Payload to /api/career-ark/generate:", str(payload)[:500], '...')
    resp = requests.post(url, json=payload, headers=headers)
    print("Generate CV response:", resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.json()

def create_cv(token, cv_text, cover_letter):
    url = f"{API_BASE}/api/cv"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"cv": cv_text, "cover_letter": cover_letter}
    print("Payload to /api/cv:", str(payload)[:500], '...')
    resp = requests.post(url, json=payload, headers=headers)
    print("Create CV response:", resp.status_code, resp.headers.get('content-type'), resp.text[:200])
    resp.raise_for_status()
    # Save DOCX if returned
    if resp.headers.get("content-type", "").startswith("application/vnd.openxmlformats-officedocument.wordprocessingml.document"):
        with open("generated_cv.docx", "wb") as f:
            f.write(resp.content)
        print("Saved generated CV as generated_cv.docx")
    else:
        print("Did not receive a DOCX file.")
    return resp

def get_cvs(token):
    url = f"{API_BASE}/api/cv"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    print("Get CVs response:", resp.status_code, resp.text[:200])
    resp.raise_for_status()
    return resp.json()

def download_persisted_cv(token, cv_id):
    url = f"{API_BASE}/api/cv/{cv_id}/download"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    print("Download persisted CV response:", resp.status_code)
    if resp.status_code == 200:
        with open(f"persisted_cv_{cv_id}.docx", "wb") as f:
            f.write(resp.content)
        print(f"Persisted CV downloaded as persisted_cv_{cv_id}.docx")
    else:
        print("Failed to download persisted CV:", resp.text)

if __name__ == "__main__":
    token = login()
    ark_profile = fetch_ark_profile(token)
    job_description = "Software Engineer at ExampleCorp"  # Replace as needed
    generated = generate_cv(token, ark_profile, job_description)
    cv_text = generated.get("cv")
    cover_letter = generated.get("cover_letter")
    create_cv(token, cv_text, cover_letter)

    # Fetch CVs and download the latest persisted DOCX
    cvs = get_cvs(token)
    if cvs:
        latest_cv = cvs[0]  # or filter by name/description if needed
        cv_id = latest_cv.get("id")
        if cv_id:
            download_persisted_cv(token, cv_id)
        else:
            print("No CV ID found in CV list.")
    else:
        print("No CVs found for user.") 