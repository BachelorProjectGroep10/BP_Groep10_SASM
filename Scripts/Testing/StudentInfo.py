#Install nodig voor script te laten werken
#pip install selenium requests

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import requests
import json

# 1. Start the browser and authenticate
driver = webdriver.Chrome()
driver.get("https://ultra.edu.kuleuven.cloud/")

try:
    WebDriverWait(driver, 15).until(
        EC.element_to_be_clickable((By.ID, "btnnextauthlogin"))
    ).click()
    print("Authenticator-knop aangeklikt.")
except Exception as e:
    print("Klikken mislukt:", e)
    driver.quit()
    exit()

try:
    WebDriverWait(driver, 120).until(
        EC.url_contains("/ultra/")
    )
    print("Ingelogd! Redirect gedetecteerd.")
except Exception as e:
    print("Timeout: waarschijnlijk niet ingelogd.")
    driver.quit()
    exit()

# 2. Get cookies from the authenticated browser session
cookies = driver.get_cookies()
driver.quit()  # Close the browser early now

# 3. Set up requests session with cookies
session = requests.Session()
for cookie in cookies:
    session.cookies.set(cookie['name'], cookie['value'])

# 4. Fetch course users
course_users_url = "https://ultra.edu.kuleuven.cloud/learn/api/public/v1/courses/_86740_1/users"
response = session.get(course_users_url)
print("Gebruikerslijst status:", response.status_code)

if response.status_code != 200:
    print("Kon gebruikerslijst niet ophalen.")
    exit()

users_data = response.json()

# 5. Filter users with role 'Student'
student_ids = [
    user["userId"]
    for user in users_data.get("results", [])
    if user.get("courseRoleId") == "Student"
]

print(f"{len(student_ids)} studenten gevonden.")

# 6. Fetch full user info
all_student_details = []
filtered_student_info = []

for user_id in student_ids:
    user_url = f"https://ultra.edu.kuleuven.cloud/learn/api/public/v1/users/{user_id}"
    user_resp = session.get(user_url)
    if user_resp.status_code == 200:
        data = user_resp.json()
        all_student_details.append(data)

        # Extract specific fields
        filtered_student_info.append({
            "userName": data.get("userName"),
            "email": data.get("contact", {}).get("email", ""),
            "givenName": data.get("name", {}).get("given", ""),
            "familyName": data.get("name", {}).get("family", "")
        })
    else:
        print(f"Kon student {user_id} niet ophalen (status {user_resp.status_code})")

# 7. Save full student data
with open("students_data.json", "w", encoding="utf-8") as f:
    json.dump(all_student_details, f, ensure_ascii=False, indent=2)

# 8. Save filtered student data
with open("students_short_data.json", "w", encoding="utf-8") as f:
    json.dump(filtered_student_info, f, ensure_ascii=False, indent=2)

print("Volledige studentengegevens opgeslagen in students_data.json")
print("Samenvatting opgeslagen in students_short_data.json")