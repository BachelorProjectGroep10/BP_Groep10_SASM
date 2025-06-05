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

    logging.info("-" * 60)

