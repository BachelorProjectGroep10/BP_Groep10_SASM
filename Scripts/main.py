from student_scraper import fetch_student_data
from process_students import process_emails
from create_dns import execute_dns

data = fetch_student_data()

emails = []

for student in data['students']:
    if student['email'] != "pieter.geens@ucll.be":
        emails.append(student['email'])

test = process_emails(emails)

execute_dns()
# verify_dns_changes(emails)