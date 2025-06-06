import json
import re
import requests
from api_helper import api_get, api_patch, api_post, api_put, api_delete

def list_all_zones():
    zones = api_get("/zones")
    print(f"Found {len(zones)} zones")
    if not zones:
        print("No zones found.")
        return []
    for zone in zones:
        print(f"Found zone: {zone['name']}")
    
    return [zone['name'] for zone in zones]

def delete_all_sasm_zones():
    print("Deleting all .sasm.uclllabs.be zones...")
    zones = list_all_zones()
    for zone in zones:
        if zone.endswith(".sasm.uclllabs.be."):
            print(f"Deleting zone {zone}")
            api_delete(f"/zones/{zone}")

def get_zone(zone_name):
    try:
        return api_get(f"/zones/{zone_name}")
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Zone {zone_name} not found")
            return None
        raise

def update_zone_remove_ns_ds(zone_name, exclude_patterns):
    """
    Remove NS and DS records in zone except those matching exclude_patterns.
    """
    zone = get_zone(zone_name)
    if not zone:
        return
    
    records = zone.get('rrsets', [])
    exclude_regex = re.compile(exclude_patterns)
    new_records = []

    for record in records:
        if record['type'] in ['NS', 'DS']:
            # Keep only if name matches exclude pattern
            if exclude_regex.search(record['name']):
                new_records.append(record)
            else:
                # Delete by not adding
                continue
        else:
            new_records.append(record)

    # Mark all kept records changetype REPLACE so API applies them properly
    for r in new_records:
        r["changetype"] = "REPLACE"

    print(f"Updating zone {zone_name} to remove unwanted NS/DS records...")
    api_patch(f"/zones/{zone_name}", {"rrsets": new_records})

def verify_zones(zones):
    print("Verifying zones...")
    for zone in zones:
        print(f"Zone: {zone}")
        zone_data = get_zone(zone)
        if zone_data:
            print(json.dumps(zone_data, indent=2))

def create_slave_zone(zone_name, master_ipv4, master_ipv6):
    # Do NOT append trailing dot unless API explicitly needs it
    zone_name = zone_name.rstrip(".")
    fqdn = zone_name + "."       
    if get_zone(zone_name):
        print(f"Zone {zone_name} already exists, skipping creation.")
        return
    data = {
        "name": fqdn,
        "kind": "Slave",
        "masters": [master_ipv4, master_ipv6],
        "nameservers": []
    }
    print(f"Creating slave zone {zone_name}")
    api_post("/zones", data)

def create_slave_zones_from_students(emails):
    print("Creating slave zones from emails list...")
    zones_to_create = set()
    for email in emails:
        email = email.strip()
        if not email or "@" not in email or email.startswith("#"):
            continue
        user, domain = email.split("@", 1)
        zone_name = f"{user.replace('.', '-')}.sasm.uclllabs.be"
        default_ipv4 = "193.191.176.1"
        default_ipv6 = "2001:6a8:2880:a020::1"
        zones_to_create.add((zone_name, default_ipv4, default_ipv6))

    for zone_name, ipv4, ipv6 in zones_to_create:
        try:
            create_slave_zone(zone_name, ipv4, ipv6)
        except requests.HTTPError as e:
            print(f"Failed creating zone {zone_name}: {e}")

import json  # make sure this is at the top

def add_ns_records_parent_zone():
    """Add NS and glue A/AAAA records to parent zone."""
    zone_name = "sasm.uclllabs.be"
    zone = get_zone(zone_name)

    if not zone:
        print(f"❌ Parent zone {zone_name} does not exist.")
        return

    print(f"✅ Found parent zone: {zone_name}")
    print(f"🔍 Current rrsets in zone:")
    print(json.dumps(zone.get("rrsets", []), indent=2))

    rrsets = zone.get("rrsets", [])
    wanted_rrsets = {
        ("sasm.uclllabs.be.", "NS"): [
            "ns1.uclllabs.be.",
            "ns2.uclllabs.be.",
        ],
        ("ns.slimme-rik.sasm.uclllabs.be.", "A"): ["193.191.176.1"],
        ("ns.slimme-rik.sasm.uclllabs.be.", "AAAA"): ["2001:6a8:2880:a020::1"]
    }

    rrset_map = {(r["name"], r["type"]): r for r in rrsets}

    for (name, rtype), contents in wanted_rrsets.items():
        records = [{"content": c, "disabled": False} for c in contents]
        if (name, rtype) in rrset_map:
            rrset_map[(name, rtype)]["records"] = records
            rrset_map[(name, rtype)]["changetype"] = "REPLACE"
            rrset_map[(name, rtype)]["ttl"] = 3600
        else:
            rrset_map[(name, rtype)] = {
                "name": name,
                "type": rtype,
                "ttl": 3600,
                "changetype": "REPLACE",
                "records": records
            }

    new_rrsets = list(rrset_map.values())

    print(f"🚀 Adding/updating NS records in parent zone {zone_name}")
    api_patch(f"/zones/{zone_name}", {"rrsets": new_rrsets})


def create_ptr_record(ipv4_ptr_zone, ptr_name, ptr_target):
    """
    Add a PTR record to a reverse zone.
    ipv4_ptr_zone: e.g. '176.191.193.in-addr.arpa'
    ptr_name: e.g. '1.176.191.193.in-addr.arpa'
    ptr_target: FQDN the PTR points to
    """
    zone = get_zone(ipv4_ptr_zone)
    if not zone:
        print(f"PTR zone {ipv4_ptr_zone} does not exist.")
        return

    rrsets = zone.get("rrsets", [])
    rrset_map = {(r["name"], r["type"]): r for r in rrsets}

    ptr_name = ptr_name if ptr_name.endswith('.') else f"{ptr_name}."
    ptr_target = ptr_target if ptr_target.endswith('.') else f"{ptr_target}."

    # Build or replace PTR rrset
    ptr_rrset = {
        "name": ptr_name,
        "type": "PTR",
        "ttl": 3600,
        "changetype": "REPLACE",
        "records": [{"content": ptr_target, "disabled": False}]
    }

    rrset_map[(ptr_name, "PTR")] = ptr_rrset

    new_rrsets = list(rrset_map.values())

    print(f"Adding/updating PTR record {ptr_name} -> {ptr_target}")
    api_patch(f"/zones/{ipv4_ptr_zone}", {"rrsets": new_rrsets})

def execute_dns(students):
    list_all_zones()
    print("Starting DNS zone management...")
    delete_all_sasm_zones()

    # Remove NS/DS records except for '.*-.*|pieter|rudi' pattern
    exclude_pattern = r'(.*-.*|pieter|rudi)\.sasm\.uclllabs\.be'
    clean_zones = [
        "sasm.uclllabs.be",
        "176.191.193.in-addr.arpa",
        "a.0.8.8.2.8.a.6.0.1.0.0.2.ip6.arpa"
    ]
    for zone in clean_zones:
        update_zone_remove_ns_ds(zone, exclude_pattern)

    verify_zones(clean_zones)

    # Create slave zones from students file (adjust filename/path)
    create_slave_zones_from_students(students)

    # Create one specific slave zone
    create_slave_zone("slimme-rik.sasm.uclllabs.be.", "193.191.176.1", "2001:6a8:2880:a020::1")

    add_ns_records_parent_zone()

    # Add PTR record for IPv4 example
    create_ptr_record(
        "176.191.193.in-addr.arpa",
        "1.176.191.193.in-addr.arpa",
        "mx.slimme-rik.sasm.uclllabs.be"
    )

    # Note: IPv6 PTR creation requires reverse nibble zone calculation,
    # which is complex and usually done by ipv6calc or custom logic.
    print("IPv6 PTR record creation must be done manually or extended with ipv6calc integration.")

    # Note: ALLOW-AXFR-FROM domainmetadata can only be set directly in DB
    print("Allow AXFR permission must be inserted directly in PowerDNS database.")

if __name__ == "__main__":
    execute_dns()
