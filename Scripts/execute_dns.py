import json
import re
import requests
from api_helper import api_get, api_post, api_put, api_delete

def list_all_zones():
    zones = api_get("/zones")
    return [zone['name'] for zone in zones]

def delete_all_sasm_zones():
    print("Deleting all .sasm.uclllabs.be zones...")
    zones = list_all_zones()
    for zone in zones:
        if zone.endswith(".sasm.uclllabs.be"):
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
    
    records = zone['records']
    new_records = []
    exclude_regex = re.compile(exclude_patterns)

    for record in records:
        # Keep all except NS/DS that match exclude pattern
        if record['type'] in ['NS', 'DS']:
            # record['name'] is FQDN
            if exclude_regex.search(record['name']):
                new_records.append(record)  # keep if excluded
            else:
                # skipping record (deleting)
                continue
        else:
            new_records.append(record)

    # Prepare data for PUT (replace records)
    zone_data = {
        "rrsets": []
    }
    # Group by name & type
    grouped = {}
    for r in new_records:
        key = (r['name'], r['type'], r['ttl'])
        if key not in grouped:
            grouped[key] = {
                "name": r['name'],
                "type": r['type'],
                "ttl": r['ttl'],
                "changetype": "REPLACE",
                "records": []
            }
        grouped[key]["records"].append({
            "content": r['records'][0]['content'],
            "disabled": r['records'][0].get('disabled', False)
        })
    zone_data["rrsets"] = list(grouped.values())

    print(f"Updating zone {zone_name} to remove NS/DS records except exclude pattern...")
    api_put(f"/zones/{zone_name}", zone_data)

def verify_zones(zones):
    print("Verifying zones...")
    for zone in zones:
        print(f"Zone: {zone}")
        zone_data = get_zone(zone)
        if zone_data:
            print(json.dumps(zone_data, indent=2))

def create_slave_zone(zone_name, master_ipv4, master_ipv6):
    data = {
        "name": zone_name,
        "kind": "Slave",
        "masters": [master_ipv4, master_ipv6],
        "nameservers": []
    }
    print(f"Creating slave zone {zone_name}")
    api_post("/zones", data)

def create_slave_zones_from_students(filename):
    print("Creating slave zones from students file...")
    with open(filename) as f:
        students = f.readlines()
    
    # Parse students to extract zone names, IPv4 and IPv6 (simplified example)
    zones_to_create = set()
    for line in students:
        if "@" in line and not line.startswith("#"):
            parts = line.split()
            if len(parts) < 4:
                continue
            name, surname, email, ip = parts[0], parts[1], parts[2], parts[3]
            zone_name = f"{surname}-{name}.sasm.uclllabs.be"
            zones_to_create.add((zone_name, ip, "2001:6a8:2880:a020::1"))  # IPv6 static for demo
    
    for zone_name, ipv4, ipv6 in zones_to_create:
        try:
            create_slave_zone(zone_name, ipv4, ipv6)
        except requests.HTTPError as e:
            print(f"Failed creating zone {zone_name}: {e}")

def add_ns_records_parent_zone():
    """Add NS and glue A/AAAA records to parent zone."""
    zone_name = "sasm.uclllabs.be"
    zone = get_zone(zone_name)
    if not zone:
        print(f"Parent zone {zone_name} does not exist.")
        return
    
    # Add NS record for slimme-rik
    ns_rrset = {
        "name": zone_name,
        "type": "NS",
        "ttl": 3600,
        "changetype": "REPLACE",
        "records": [
            {"content": "ns1.uclllabs.be", "disabled": False},
            {"content": "ns2.uclllabs.be", "disabled": False},
            {"content": "ns.slimme-rik.sasm.uclllabs.be", "disabled": False}
        ]
    }
    # Add A record for ns.slimme-rik (glue)
    a_rrset = {
        "name": "ns.slimme-rik." + zone_name,
        "type": "A",
        "ttl": 3600,
        "changetype": "REPLACE",
        "records": [{"content": "193.191.176.1", "disabled": False}]
    }
    # Add AAAA record for ns.slimme-rik (glue)
    aaaa_rrset = {
        "name": "ns.slimme-rik." + zone_name,
        "type": "AAAA",
        "ttl": 3600,
        "changetype": "REPLACE",
        "records": [{"content": "2001:6a8:2880:a020::1", "disabled": False}]
    }
    rrsets = [ns_rrset, a_rrset, aaaa_rrset]

    # We must merge with existing rrsets or send a PUT with all records. For simplicity, replace/add these rrsets.
    data = {
        "rrsets": rrsets
    }

    print(f"Adding NS and glue records to parent zone {zone_name}")
    api_put(f"/zones/{zone_name}", data)

def create_ptr_record(ipv4_ptr_zone, ptr_name, ptr_target):
    """
    Add a PTR record to a reverse zone.
    ipv4_ptr_zone: e.g. '176.191.193.in-addr.arpa'
    ptr_name: e.g. '1.176.191.193.in-addr.arpa'
    ptr_target: FQDN the PTR points to
    """
    rrset = {
        "name": ptr_name,
        "type": "PTR",
        "ttl": 3600,
        "changetype": "REPLACE",
        "records": [{"content": ptr_target, "disabled": False}]
    }
    print(f"Adding PTR record {ptr_name} -> {ptr_target}")
    api_put(f"/zones/{ipv4_ptr_zone}", {"rrsets": [rrset]})

def main():
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
    create_slave_zones_from_students("students")

    # Create one specific slave zone
    create_slave_zone("slimme-rik.sasm.uclllabs.be", "193.191.176.1", "2001:6a8:2880:a020::1")

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
    main()