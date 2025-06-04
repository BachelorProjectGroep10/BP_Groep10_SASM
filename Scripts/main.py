from student_scraper import fetch_student_data

data = fetch_student_data()

if data:
    # Now you can use `data` as a Python dict
    print(f"{len(data['students'])} studenten geladen.")
    for student in data['students']:
        print(f"{student['email']}")