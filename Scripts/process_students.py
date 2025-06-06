import json
import os

def process_emails(new_email_list, output_file="Output/processed_Emails.json"):
    # Load existing data if exists
    if os.path.exists(output_file):
        with open(output_file, "r") as f:
            existing_data = json.load(f)
    else:
        existing_data = []

    # Get set of emails already processed for quick lookup
    processed_emails = {entry["original_email"] for entry in existing_data}

    # Filter new emails that are not in existing data
    unique_new_emails = [email for email in new_email_list if email not in processed_emails]

    # Sort new emails by last name (first word after dot)
    sorted_new_emails = sorted(unique_new_emails, key=lambda email: email.split('@')[0].split('.')[1])

    # Find the next available IP index (starting at 5)
    if existing_data:
        last_ipv4 = existing_data[-1]["ipv4"]
        last_index = int(last_ipv4.split('.')[-1])
        start_index = last_index + 1
    else:
        start_index = 5

    if start_index + len(sorted_new_emails) - 1 > 253:
        raise ValueError("Too many emails; not enough IP addresses in range 5-253")

    # Process new emails
    new_entries = []
    for i, email in enumerate(sorted_new_emails):
        name_part = email.split('@')[0]
        first_name, last_name = name_part.split('.')

        dns_zone_name = f"{first_name}-{last_name}.sasm.uclllabs.be"
        ipv4 = f"193.191.176.{start_index + i}"
        ipv6 = f"2001:6a8:2880:a020::{start_index + i}"
        hostname = f"{first_name}-{last_name}"

        new_entries.append({
            "original_email": email,
            "hostname": hostname,
            "dns_zone": dns_zone_name,
            "ipv4": ipv4,
            "ipv6": ipv6
        })

    # Combine old and new data
    updated_data = existing_data + new_entries

    # Ensure output folder exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Write back to file
    with open(output_file, "w") as f:
        json.dump(updated_data, f, indent=4)

    return updated_data
