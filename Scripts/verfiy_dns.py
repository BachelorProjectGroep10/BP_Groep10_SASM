import re
from api_helper import api_get
import json

def verify_zone_exists(zone_name):
    try:
        zone = api_get(f"/zones/{zone_name}")
        print(f"[OK] Zone exists: {zone_name}")
        return zone
    except:
        print(f"[FAIL] Zone missing: {zone_name}")
        return None

def verify_no_sasm_zones():
    print("Verifying no stray .sasm.uclllabs.be zones remain...")
    zones = api_get("/zones")
    errors = 0
    for zone in zones:
        name = zone["name"]
        if name.endswith(".sasm.uclllabs.be") and not re.search(r"(.*-.*|pieter|rudi)\.sasm\.uclllabs\.be.", name):
            print(f"[FAIL] Unexpected .sasm zone still exists: {name}")
            errors += 1
    if errors == 0:
        print("[OK] No unwanted .sasm.uclllabs.be zones found.")

def verify_ns_records(zone_name, expected_ns):
    zone = verify_zone_exists(zone_name)
    if not zone:
        return

    fqdn = zone_name if zone_name.endswith('.') else f"{zone_name}."

    ns_records = [
        rr for rr in zone.get("rrsets", [])
        if rr["type"] == "NS" and rr["name"] == fqdn
    ]

    if not ns_records:
        print(f"[FAIL] No NS records found in {zone_name}")
        return

    # Strip trailing dots from actual records before comparison
    actual_ns = sorted([rec["content"].rstrip('.') for rec in ns_records[0]["records"]])
    expected_ns_normalized = sorted([ns.rstrip('.') for ns in expected_ns])

    if actual_ns == expected_ns_normalized:
        print(f"[OK] NS records correct in {zone_name}")
    else:
        print(f"[FAIL] NS records mismatch in {zone_name}")
        print(f"Expected: {expected_ns_normalized}")
        print(f"Found:    {actual_ns}")


def verify_glue_records(name, expected_a, expected_aaaa, zone_name):
    zone = verify_zone_exists(zone_name)
    if not zone:
        return

    fqdn = name if name.endswith('.') else f"{name}."

    def get_record(type_):
        for rr in zone.get("rrsets", []):
            if rr["name"] == fqdn and rr["type"] == type_:
                return sorted([rec["content"] for rec in rr["records"]])
        return []

    actual_a = get_record("A")
    actual_aaaa = get_record("AAAA")

    if actual_a == sorted(expected_a):
        print(f"[OK] A record for {name} is correct.")
    else:
        print(f"[FAIL] A record mismatch for {name}. Expected {expected_a}, got {actual_a}")

    if actual_aaaa == sorted(expected_aaaa):
        print(f"[OK] AAAA record for {name} is correct.")
    else:
        print(f"[FAIL] AAAA record mismatch for {name}. Expected {expected_aaaa}, got {actual_aaaa}")

def verify_slave_zones_created(emails):
    expected_zones = [
        f"{email.split('@')[0].replace('.', '-')}.sasm.uclllabs.be."
        for email in emails
        if email and "@" in email and not email.startswith("#")
    ]
    zones = api_get("/zones")
    existing_zone_names = {z["name"] for z in zones}
    for zone in expected_zones:
        if zone in existing_zone_names:
            print(f"[OK] Slave zone exists: {zone}")
        else:
            print(f"[FAIL] Missing slave zone: {zone}")

def verify_ptr_record(zone_name, ptr_name, expected_target):
    zone = verify_zone_exists(zone_name)
    if not zone:
        return

    ptr_fqdn = ptr_name if ptr_name.endswith('.') else f"{ptr_name}."
    expected_fqdn = expected_target if expected_target.endswith('.') else f"{expected_target}."

    for rr in zone.get("rrsets", []):
        if rr["name"] == ptr_fqdn and rr["type"] == "PTR":
            if any(rec["content"].rstrip('.') == expected_fqdn.rstrip('.') for rec in rr["records"]):
                print(f"[OK] PTR record correct: {ptr_name} -> {expected_target}")
            else:
                print(f"[FAIL] PTR record incorrect for {ptr_name}")
                print(f"Expected: {expected_target}")
                print(f"Found: {[rec['content'] for rec in rr['records']]}")
            return

    print(f"[FAIL] PTR record not found: {ptr_name}")

def verify_dns_changes(emails):
    verify_no_sasm_zones()

    # Verify NS records and glue records in parent zone
    verify_ns_records("sasm.uclllabs.be", [
        "ns1.uclllabs.be",
        "ns2.uclllabs.be",
        "ns.slimme-rik.sasm.uclllabs.be"
    ])
    verify_glue_records("ns.slimme-rik.sasm.uclllabs.be",
                        expected_a=["193.191.176.1"],
                        expected_aaaa=["2001:6a8:2880:a020::1"],
                        zone_name="sasm.uclllabs.be")

    # Verify slimme-rik zone exists
    verify_zone_exists("slimme-rik.sasm.uclllabs.be")

    # Verify slave zones for students
    verify_slave_zones_created(emails)

    # Verify PTR record
    verify_ptr_record(
        "176.191.193.in-addr.arpa",
        "1.176.191.193.in-addr.arpa",
        "mx.slimme-rik.sasm.uclllabs.be"
    )

if __name__ == "__main__":
    # Sample call with email list
    verify_dns_changes()
