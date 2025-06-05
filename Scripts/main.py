from student_scraper import fetch_student_data
from execute_dns import execute_dns
from verfiy_dns import verify_dns_changes

data = fetch_student_data()

emails = []

for student in data['students']:
    if student['email'] != "pieter.geens@ucll.be":
        emails.append(student['email'])

execute_dns(emails)

verify_dns_changes(emails)