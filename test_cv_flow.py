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

def download_docx_by_id(token, cv_id, label=None):
    url = f"{API_BASE}/api/cv/{cv_id}/download"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    print(f"Download DOCX for {label or cv_id} response:", resp.status_code)
    if resp.status_code == 200:
        data = resp.json()
        filedata = data.get("filedata")
        filename = data.get("filename", f"persisted_cv_{cv_id}.docx")
        if filedata:
            import base64
            with open(filename, "wb") as f:
                f.write(base64.b64decode(filedata))
            print(f"Persisted DOCX downloaded as {filename}")
        else:
            print("No filedata found in download response.")
    else:
        print("Failed to download persisted DOCX:", resp.text)

def create_cv(token, cv_text, cover_letter):
    url = f"{API_BASE}/api/cv"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"cv": cv_text, "cover_letter": cover_letter}
    print("Payload to /api/cv:", str(payload)[:500], '...')
    resp = requests.post(url, json=payload, headers=headers)
    print("Create CV response:", resp.status_code, resp.headers.get('content-type'), resp.text[:200])
    resp.raise_for_status()
    data = resp.json()
    filedata = data.get("filedata")
    filename = data.get("filename", "generated_cv.docx")
    cv_id = data.get("cv_id")
    if filedata:
        import base64
        with open(filename, "wb") as f:
            f.write(base64.b64decode(filedata))
        print(f"Saved generated CV as {filename}")
    else:
        print("No filedata found in response.")
    if cv_id:
        download_docx_by_id(token, cv_id, label="combined CV")
    return resp

def create_cv_only(token, cv_text):
    url = f"{API_BASE}/api/cv"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"cv": cv_text}
    print("Payload to /api/cv (CV only):", str(payload)[:500], '...')
    resp = requests.post(url, json=payload, headers=headers)
    print("Create CV (CV only) response:", resp.status_code, resp.headers.get('content-type'), resp.text[:200])
    resp.raise_for_status()
    data = resp.json()
    filedata = data.get("filedata")
    filename = data.get("filename", "generated_cv_only.docx")
    cv_id = data.get("cv_id")
    if filedata:
        import base64
        with open(filename, "wb") as f:
            f.write(base64.b64decode(filedata))
        print(f"Saved generated CV (CV only) as {filename}")
    else:
        print("No filedata found in response.")
    if cv_id:
        download_docx_by_id(token, cv_id, label="CV only")
    return resp

def create_cover_letter_only(token, cover_letter):
    url = f"{API_BASE}/api/cover-letter"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"cover_letter": cover_letter}
    print("Payload to /api/cover-letter (Cover Letter only):", str(payload)[:500], '...')
    resp = requests.post(url, json=payload, headers=headers)
    print("Create Cover Letter response:", resp.status_code, resp.headers.get('content-type'), resp.text[:200])
    resp.raise_for_status()
    data = resp.json()
    filedata = data.get("filedata")
    filename = data.get("filename", "generated_cover_letter.docx")
    cv_id = data.get("cv_id")
    if filedata:
        import base64
        with open(filename, "wb") as f:
            f.write(base64.b64decode(filedata))
        print(f"Saved generated Cover Letter as {filename}")
    else:
        print("No filedata found in response.")
    if cv_id:
        download_docx_by_id(token, cv_id, label="cover letter")
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
        data = resp.json()
        filedata = data.get("filedata")
        filename = data.get("filename", f"persisted_cv_{cv_id}.docx")
        if filedata:
            import base64
            with open(filename, "wb") as f:
                f.write(base64.b64decode(filedata))
            print(f"Persisted CV downloaded as {filename}")
        else:
            print("No filedata found in response.")
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

    # Test new separate endpoints
    create_cv_only(token, cv_text)
    create_cover_letter_only(token, cover_letter)

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