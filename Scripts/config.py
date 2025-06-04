from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

import os

load_dotenv()  # Load variables from .env into environment variables

API_URL = os.getenv("API_URL")
API_KEY = os.getenv("API_KEY")

API_USER = os.getenv("API_USERNAME") 
API_PASS = os.getenv("API_PASSWORD") 

AUTH = HTTPBasicAuth(API_USER, API_PASS)

HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}
