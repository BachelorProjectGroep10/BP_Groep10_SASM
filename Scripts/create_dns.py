import ipaddress
import json
import re
import requests
import logging
from api_helper import api_get, api_patch, api_post, api_put, api_delete

# Setup logging
logging.basicConfig(
    filename='Output/Dns_Create_log.txt',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def list_all_zones():
    zones = api_get("/zones")
    logging.info(f"Found {len(zones)} zones")
    return [zone['name'] for zone in zones]

def delete_all_sasm_zones():
    logging.info("Deleting all .sasm.uclllabs.be zones...")
    zones = list_all_zones()
    for zone in zones:
        if zone.endswith(".sasm.uclllabs.be."):
            logging.info(f"Deleting zone {zone}")
            api_delete(f"/zones/{zone}")

def get_zone(zone_name):
    try:
        return api_get(f"/zones/{zone_name}")
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            logging.warning(f"Zone {zone_name} not found")
            return None
        raise

def update_zone_remove_ns_ds(zone_name, exclude_patterns):
    zone = get_zone(zone_name)
    if not zone:
        return
    
    records = zone.get('rrsets', [])
    exclude_regex = re.compile(exclude_patterns)
    new_records = []

    for record in records:
        if record['type'] in ['NS', 'DS']:
            if exclude_regex.search(record['name']):
                new_records.append(record)
            else:
                logging.info(f"Removing {record['type']} record: {record['name']}")
        else:
            new_records.append(record)

    for r in new_records:
        r["changetype"] = "REPLACE"

    logging.info(f"Updating zone {zone_name} to remove unwanted NS/DS records...")
    api_patch(f"/zones/{zone_name}", {"rrsets": new_records})

def verify_zones(zones):
    logging.info("Verifying zones...")
    for zone in zones:
        logging.info(f"Zone: {zone}")
        zone_data = get_zone(zone)
        if zone_data:
            logging.info(json.dumps(zone_data, indent=2))

def create_slave_zone(zone_name, ipv4, ipv6):
    stripped_zone_name = zone_name.rstrip(".")
    normal_zone_name = stripped_zone_name + "."       
    if get_zone(stripped_zone_name):
        logging.info(f"Zone {stripped_zone_name} already exists, skipping creation.")
        return
    data = {
        "name": normal_zone_name,
        "kind": "Slave",
        "masters": [ipv4, ipv6],
        "nameservers": []
    }
    api_post("/zones", data)
    logging.info(f"Creating slave zone {stripped_zone_name} with masters {ipv4}, {ipv6}")

def create_slave_zones_from_students(students):
    for student in students:
        zone_name = student.get("dns_zone")
        ipv4 = student.get("ipv4")
        ipv6 = student.get("ipv6")

        if not zone_name or not ipv4 or not ipv6:
            continue  

        try:
            create_slave_zone(zone_name, ipv4, ipv6)
        except requests.HTTPError as e:
            logging.error(f"Failed creating zone {zone_name}: {e}")

def add_ns_records_parent_zone_from_students(students):
    """Add NS and glue A/AAAA records to sasm.uclllabs.be for each student, skipping if already present."""

    zone_name = "sasm.uclllabs.be"
    zone = get_zone(zone_name)

    if not zone:
        logging.error(f"❌ Parent zone {zone_name} does not exist.")
        return

    logging.info(f"✅ Found parent zone: {zone_name}")
    rrsets = zone.get("rrsets", [])
    rrset_map = {(r["name"], r["type"]): r for r in rrsets}
    updated_rrsets = {}

    for student in students:
        zone_fqdn = student["dns_zone"].rstrip(".") + "."
        ns_name = f"ns.{zone_fqdn}"
        ipv4 = student["ipv4"]
        ipv6 = student["ipv6"]

        # --- NS Records ---
        ns_key = (zone_fqdn, "NS")
        desired_ns_targets = {
            "ns1.uclllabs.be.",
            "ns2.uclllabs.be.",
            ns_name
        }

        existing_ns = rrset_map.get(ns_key, {}).get("records", [])
        existing_ns_contents = {r["content"] for r in existing_ns}

        if not desired_ns_targets.issubset(existing_ns_contents):
            # Add only missing NS records
            new_records = existing_ns + [
                {"content": target, "disabled": False}
                for target in desired_ns_targets
                if target not in existing_ns_contents
            ]
            updated_rrsets[ns_key] = {
                "name": zone_fqdn,
                "type": "NS",
                "ttl": 3600,
                "changetype": "REPLACE",
                "records": new_records
            }
            logging.info(f"✅ Updating NS records for {zone_fqdn} → {', '.join(desired_ns_targets)}")
        else:
            logging.info(f"ℹ️ NS records for {zone_fqdn} already up to date.")

        # --- A Glue Record ---
        a_key = (ns_name, "A")
        existing_a = rrset_map.get(a_key, {}).get("records", [])
        a_exists = any(r["content"] == ipv4 for r in existing_a)

        if not a_exists:
            updated_rrsets[a_key] = {
                "name": ns_name,
                "type": "A",
                "ttl": 3600,
                "changetype": "REPLACE",
                "records": [{"content": ipv4, "disabled": False}]
            }
            logging.info(f"🔧 Added A glue record for {ns_name} → {ipv4}")
        else:
            logging.info(f"ℹ️ A record for {ns_name} already exists with {ipv4}")

        # --- AAAA Glue Record ---
        aaaa_key = (ns_name, "AAAA")
        existing_aaaa = rrset_map.get(aaaa_key, {}).get("records", [])
        aaaa_exists = any(r["content"] == ipv6 for r in existing_aaaa)

        if not aaaa_exists:
            updated_rrsets[aaaa_key] = {
                "name": ns_name,
                "type": "AAAA",
                "ttl": 3600,
                "changetype": "REPLACE",
                "records": [{"content": ipv6, "disabled": False}]
            }
            logging.info(f"🔧 Added AAAA glue record for {ns_name} → {ipv6}")
        else:
            logging.info(f"ℹ️ AAAA record for {ns_name} already exists with {ipv6}")

    if updated_rrsets:
        logging.info(f"🚀 Patching parent zone {zone_name} with {len(updated_rrsets)} updated RRsets...")
        api_patch(f"/zones/{zone_name}", {"rrsets": list(updated_rrsets.values())})
    else:
        logging.info(f"✅ No changes needed. All NS and glue records are already present.")

def ipv4_to_arpa(ipv4):
    """Convert IPv4 address to full reverse PTR name."""
    return ".".join(reversed(ipv4.split("."))) + ".in-addr.arpa"



def create_ptr_record(zone_name, full_ptr_name, ptr_target):
    fqdn = ptr_target if ptr_target.endswith('.') else ptr_target + '.'
    full_ptr_name = full_ptr_name if full_ptr_name.endswith('.') else full_ptr_name + '.'

    rrset = {
        "name": full_ptr_name,
        "type": "PTR",
        "ttl": 3600,
        "changetype": "REPLACE",
        "records": [{"content": fqdn, "disabled": False}]
    }

    logging.info(f"🔁 Adding PTR {full_ptr_name} → {fqdn} in zone {zone_name}")
    api_patch(f"/zones/{zone_name}", {"rrsets": [rrset]})

def ipv6_to_arpa(ipv6):
    """Convert IPv6 address to full reverse PTR name (.ip6.arpa)."""
    ip = ipaddress.IPv6Address(ipv6)
    hex_digits = ip.exploded.replace(":", "")
    reversed_nibbles = ".".join(reversed(hex_digits))
    return reversed_nibbles + ".ip6.arpa"

def create_ipv6_ptr_record(ptr_zone, ipv6_addr, ptr_target):
    full_ptr_name = ipv6_to_arpa(ipv6_addr)
    logging.debug(f"Calculated full_ptr_name: {full_ptr_name}")
    logging.debug(f"Checking if {full_ptr_name} ends with {ptr_zone}")

    if not full_ptr_name.endswith(ptr_zone):
        logging.warning(f"⚠️ Skipping {ipv6_addr}: not in PTR zone {ptr_zone}")
        return

    fqdn = ptr_target if ptr_target.endswith('.') else f"{ptr_target}."
    ptr_rrset = {
        "name": full_ptr_name + ".",
        "type": "PTR",
        "ttl": 3600,
        "changetype": "REPLACE",
        "records": [{"content": fqdn, "disabled": False}]
    }

    logging.info(f"🔁 Adding/updating IPv6 PTR record {full_ptr_name} → {fqdn}")
    api_patch(f"/zones/{ptr_zone}", {"rrsets": [ptr_rrset]})

def create_ptr_records_from_students(students):
    logging.info("Creating PTR records for all students...")
    ipv4_ptr_zone = "176.191.193.in-addr.arpa"
    ipv6_ptr_zone = "a.0.8.8.2.8.a.6.0.1.0.0.2.ip6.arpa"

    for student in students:
        hostname = student.get("hostname")
        dns_zone = student.get("dns_zone")
        ipv4 = student.get("ipv4")
        ipv6 = student.get("ipv6")

        if not hostname or not dns_zone:
            logging.warning(f"⚠️ Skipping student (missing hostname or dns_zone): {student}")
            continue

        # Construct target FQDN
        zone_part = dns_zone.rstrip(".").replace(".uclllabs.be", "")
        ptr_target = f"mx.{hostname}.{zone_part}.uclllabs.be."

        # ---- IPv4 PTR ----
        if ipv4:
            ptr_name = ipv4_to_arpa(ipv4)
            if ptr_name.endswith(ipv4_ptr_zone):
                try:
                    create_ptr_record(ipv4_ptr_zone, ptr_name, ptr_target)
                except requests.HTTPError as e:
                    logging.error(f"❌ Failed to create IPv4 PTR for {ipv4}: {e}")
            else:
                logging.warning(f"⚠️ Skipping IPv4 PTR {ipv4}, doesn't match zone {ipv4_ptr_zone}")

        # ---- IPv6 PTR ----
        if ipv6:
            ptr_name = ipv6_to_arpa(ipv6)
            if ptr_name.endswith(ipv6_ptr_zone):
                try:
                    create_ptr_record(ipv6_ptr_zone, ptr_name, ptr_target)
                except requests.HTTPError as e:
                    logging.error(f"❌ Failed to create IPv6 PTR for {ipv6}: {e}")
            else:
                logging.warning(f"⚠️ Skipping IPv6 PTR {ipv6}, doesn't match zone {ipv6_ptr_zone}")



def execute_dns():
    list_all_zones()
    delete_all_sasm_zones()

    exclude_pattern = r'(.*-.*|pieter|rudi)\.sasm\.uclllabs\.be'
    clean_zones = [
        "sasm.uclllabs.be",
        "176.191.193.in-addr.arpa",
        "a.0.8.8.2.8.a.6.0.1.0.0.2.ip6.arpa"
    ]
    for zone in clean_zones:
        update_zone_remove_ns_ds(zone, exclude_pattern)

    verify_zones(clean_zones)

    try:
        with open('Output/processed_Emails.json', 'r', encoding='utf-8') as f:
            students = json.load(f)
    except FileNotFoundError:
        logging.error("File processed_Emails.json not found.")
        return
    
    logging.info(f"Loaded {len(students)} students from processed_Emails.json")
    create_slave_zones_from_students(students)

    logging.info("Adding NS records and glue A/AAAA to parent zone sasm.uclllabs.be...")
    add_ns_records_parent_zone_from_students(students)

    logging.info("🧠 Creating PTR records for all students...")
    create_ptr_records_from_students(students)

    logging.info("-" * 60)
