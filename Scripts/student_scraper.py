# student_scraper.py

import json
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def fetch_student_data():
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
        return None

    try:
        WebDriverWait(driver, 120).until(
            EC.url_contains("/ultra/")
        )
        print("Ingelogd! Redirect gedetecteerd.")
    except Exception as e:
        print("Timeout: waarschijnlijk niet ingelogd.")
        driver.quit()
        return None

    # 2. Get cookies
    cookies = driver.get_cookies()
    driver.quit()

    # 3. Use requests session with cookies
    session = requests.Session()
    for cookie in cookies:
        session.cookies.set(cookie['name'], cookie['value'])

    # 4. Get course users
    course_users_url = "https://ultra.edu.kuleuven.cloud/learn/api/public/v1/courses/_86740_1/users"
    response = session.get(course_users_url)
    if response.status_code != 200:
        print("Kon gebruikerslijst niet ophalen.")
        return None

    users_data = response.json()
    student_ids = [
        user["userId"]
        for user in users_data.get("results", [])
        if user.get("courseRoleId") == "Instructor" or user.get("courseRoleId") == "Student"
    ]

    print(f"{len(student_ids)} studenten gevonden.")

    # 5. Get detailed user info
    filtered_student_info = []
    for user_id in student_ids:
        user_url = f"https://ultra.edu.kuleuven.cloud/learn/api/public/v1/users/{user_id}"
        user_resp = session.get(user_url)
        if user_resp.status_code == 200:
            data = user_resp.json()
            filtered_student_info.append({
                "userName": data.get("userName"),
                "email": data.get("contact", {}).get("email", ""),
                "givenName": data.get("name", {}).get("given", ""),
                "familyName": data.get("name", {}).get("family", "")
            })
        else:
            print(f"Kon student {user_id} niet ophalen (status {user_resp.status_code})")

    return {"students": filtered_student_info}

if __name__ == "__main__":
    result = fetch_student_data()
    if result:
        print(json.dumps(result, indent=2, ensure_ascii=False))
