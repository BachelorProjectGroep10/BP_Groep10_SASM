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
    """Add NS and glue A/AAAA records to sasm.uclllabs.be for each student."""

    zone_name = "sasm.uclllabs.be"
    zone = get_zone(zone_name)

    if not zone:
        logging.error(f"❌ Parent zone {zone_name} does not exist.")
        return

    logging.info(f"✅ Found parent zone: {zone_name}")
    rrsets = zone.get("rrsets", [])
    rrset_map = {(r["name"], r["type"]): r for r in rrsets}

    for student in students:
        zone_fqdn = student["dns_zone"].rstrip(".") + "."
        ns_name = f"ns.{zone_fqdn}"
        ipv4 = student["ipv4"]
        ipv6 = student["ipv6"]

        # NS record for the student's zone pointing to 3 nameservers
        ns_key = (zone_fqdn, "NS")
        ns_targets = [
            "ns1.uclllabs.be.",
            "ns2.uclllabs.be.",
            ns_name
        ]

        existing_records = rrset_map.get(ns_key, {}).get("records", [])
        existing_contents = {r["content"] for r in existing_records}

        new_ns_records = [
            {"content": target, "disabled": False}
            for target in ns_targets
            if target not in existing_contents
        ]

        combined_ns_records = existing_records + new_ns_records

        rrset_map[ns_key] = {
            "name": zone_fqdn,
            "type": "NS",
            "ttl": 3600,
            "changetype": "REPLACE",
            "records": combined_ns_records
        }

        logging.info(f"✅ NS records for {zone_fqdn} → {', '.join(ns_targets)}")

        # Glue A record
        rrset_map[(ns_name, "A")] = {
            "name": ns_name,
            "type": "A",
            "ttl": 3600,
            "changetype": "REPLACE",
            "records": [{"content": ipv4, "disabled": False}]
        }

        logging.info(f"🔧 A glue record for {ns_name} → {ipv4}")

        # Glue AAAA record
        rrset_map[(ns_name, "AAAA")] = {
            "name": ns_name,
            "type": "AAAA",
            "ttl": 3600,
            "changetype": "REPLACE",
            "records": [{"content": ipv6, "disabled": False}]
        }

        logging.info(f"🔧 AAAA glue record for {ns_name} → {ipv6}")

    new_rrsets = []
    for rr in rrset_map.values():
        rr["changetype"] = rr.get("changetype", "REPLACE")
        new_rrsets.append(rr)

    logging.info(f"🚀 Patching parent zone {zone_name} with full NS + glue records...")
    api_patch(f"/zones/{zone_name}", {"rrsets": new_rrsets})

def create_ptr_record(ipv4_ptr_zone, ptr_name, ptr_target):
    zone = get_zone(ipv4_ptr_zone)
    if not zone:
        logging.error(f"❌ PTR zone {ipv4_ptr_zone} does not exist.")
        return

    ptr_name = ptr_name if ptr_name.endswith('.') else f"{ptr_name}."
    ptr_target = ptr_target if ptr_target.endswith('.') else f"{ptr_target}."

    ptr_rrset = {
        "name": ptr_name,
        "type": "PTR",
        "ttl": 3600,
        "changetype": "REPLACE",
        "records": [{"content": ptr_target, "disabled": False}]
    }

    logging.info(f"🔁 Adding/updating PTR record {ptr_name} → {ptr_target}")
    api_patch(f"/zones/{ipv4_ptr_zone}", {"rrsets": [ptr_rrset]})

def ipv6_to_arpa(ipv6):
    """
    Convert an IPv6 address to its full PTR-compatible .ip6.arpa name.
    """
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

        ptr_target = f"mx.{hostname}.{dns_zone}.uclllabs.be"

        if ipv4:
            try:
                create_ptr_record(ipv4_ptr_zone, ipv4, ptr_target)
            except requests.HTTPError as e:
                logging.error(f"❌ Failed to create IPv4 PTR for {ipv4}: {e}")

        if ipv6:
            try:
                create_ipv6_ptr_record(ipv6_ptr_zone, ipv6, ptr_target)
            except requests.HTTPError as e:
                logging.error(f"❌ Failed to create IPv6 PTR for {ipv6}: {e}")

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
