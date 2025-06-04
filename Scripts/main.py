from student_scraper import fetch_student_data
from execute_dns import execute_dns

data = fetch_student_data()

emails = []

for student in data['students']:
    if student['email'] != "pieter.geens@ucll.be":
        emails.append(student['email'])

execute_dns(emails)