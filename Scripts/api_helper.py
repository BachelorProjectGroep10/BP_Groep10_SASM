import requests
from config import API_URL, HEADERS

def api_get(path):
    url = f"{API_URL}{path}"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()

def api_post(path, data):
    url = f"{API_URL}{path}"
    r = requests.post(url, headers=HEADERS, json=data)
    r.raise_for_status()
    return r.json()

def api_put(path, data):
    url = f"{API_URL}{path}"
    r = requests.put(url, headers=HEADERS, json=data)
    r.raise_for_status()
    return r.json()

def api_delete(path):
    url = f"{API_URL}{path}"
    r = requests.delete(url, headers=HEADERS)
    r.raise_for_status()
    return r.status_code == 204