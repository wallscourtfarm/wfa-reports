import json, base64, requests, streamlit as st

REPO   = "wallscourtfarm/wfa-reports"
BRANCH = "main"
API    = "https://api.github.com"


def _headers():
    return {
        "Authorization": f"token {st.secrets['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github.v3+json",
    }


def _get(path):
    r = requests.get(f"{API}/repos/{REPO}/contents/{path}", headers=_headers(), timeout=10)
    return r.json() if r.status_code == 200 else None


def _put(path, content_bytes, message, sha=None):
    payload = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode(),
        "branch": BRANCH,
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(f"{API}/repos/{REPO}/contents/{path}",
                     headers=_headers(), json=payload, timeout=15)
    return r.status_code in (200, 201)


def list_classes():
    data = _get("data/classes")
    if isinstance(data, list):
        return [f["name"].replace(".json", "") for f in data if f["name"].endswith(".json")]
    return []


def load_class(class_id):
    data = _get(f"data/classes/{class_id}.json")
    if data and "content" in data:
        return json.loads(base64.b64decode(data["content"]))
    return None


def save_class(class_id, class_data):
    path = f"data/classes/{class_id}.json"
    existing = _get(path)
    sha = existing["sha"] if existing and "sha" in existing else None
    content = json.dumps(class_data, indent=2, ensure_ascii=False).encode()
    return _put(path, content, f"Update {class_id}", sha)


def save_photo(class_id, filename, image_bytes):
    path = f"data/photos/{class_id}/{filename}"
    existing = _get(path)
    sha = existing["sha"] if existing and "sha" in existing else None
    return _put(path, image_bytes, f"Upload photo {filename}", sha)


def photo_raw_url(class_id, filename):
    return (f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
            f"/data/photos/{class_id}/{filename}")


def load_settings():
    data = _get("data/settings.json")
    if data and "content" in data:
        return json.loads(base64.b64decode(data["content"]))
    return {
        "academic_year": "2025-26",
        "class_display": "",
        "principals_letter": "Dear Families,\n\n",
    }


def save_settings(settings):
    path = "data/settings.json"
    existing = _get(path)
    sha = existing["sha"] if existing and "sha" in existing else None
    content = json.dumps(settings, indent=2, ensure_ascii=False).encode()
    return _put(path, content, "Update settings", sha)
