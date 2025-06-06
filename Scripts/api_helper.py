import requests
from config import API_URL, AUTH, HEADERS

def api_get(path):
    url = f"{API_URL}{path}"
    r = requests.get(url, headers=HEADERS, auth=AUTH)
    r.raise_for_status()
    return r.json()

def api_post(path, data):
    url = f"{API_URL}{path}"
    r = requests.post(url, headers=HEADERS, json=data, auth=AUTH)
    r.raise_for_status()
    return r.json()

def api_put(path, data):
    url = f"{API_URL}{path}"
    r = requests.put(url, headers=HEADERS, json=data, auth=AUTH)
    r.raise_for_status()
    return r.json()

def api_patch(path, data):
    url = f"{API_URL}{path}"
    # print(f"🔁data: {data}")
    try:
        r = requests.patch(url, headers=HEADERS, json=data, auth=AUTH)
        r.raise_for_status()
        # print(f"✅ PATCH {url} succeeded with status {r.status_code}")
        if r.content:
            # print("🔁 Response content:", r.text)

            return r.json()
        else:
            # print("ℹ️ No response content.")
            return None
    except requests.exceptions.HTTPError as e:
        # print(f"❌ HTTP error for PATCH {url}: {e}")
        # print("🔁 Response text:", r.text)
        return None
    except Exception as e:
        # print(f"❌ General error during PATCH {url}: {e}")
        return None

def api_delete(path):
    url = f"{API_URL}{path}"
    r = requests.delete(url, headers=HEADERS, auth=AUTH)
    r.raise_for_status()
    return r.status_code == 204