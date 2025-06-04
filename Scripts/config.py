from dotenv import load_dotenv
import os

load_dotenv()  # Load variables from .env into environment variables

API_URL = os.getenv("API_URL")
API_KEY = os.getenv("API_KEY")
HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}
