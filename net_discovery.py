import yaml
from netmiko import ConnectHandler
from netmiko.ssh_autodetect import SSHDetect
import os
import sys
import logging
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import re
from tabulate import tabulate

# VENDOR_COMMANDS and PLATFORM_MAPPING same as before
VENDOR_COMMANDS = {
    'cisco_ios': {
        'cdp': 'show cdp neighbors detail',
        'lldp': 'show lldp neighbors detail',
    },
    'arista_eos': {
        'cdp': None,
        'lldp': 'show lldp neighbors detail',
    },
    'juniper': {
        'cdp': None,
        'lldp': 'show lldp neighbors detail',
    },
    'paloalto_panos': {
        'cdp': None,
        'lldp': 'show lldp neighbors',
    },
    'ubiquiti_edge': {
        'cdp': None,
        'lldp': 'show lldp neighbors',
    },
}

PLATFORM_MAPPING = {
    # Cisco
    'cisco_ios': 'cisco_ios',
    'cisco_xe': 'cisco_ios',  # Same commands
    'cisco_xr': 'cisco_ios',  # CDP/LLDP supported

    # Arista
    'arista_eos': 'arista_eos',

    # Juniper
    'juniper': 'juniper',
    'juniper_junos': 'juniper',

    # Palo Alto
    'paloalto_panos': 'paloalto_panos',

    # Ubiquiti
    'ubiquiti_edgerouter': 'ubiquiti_edge',
    'ubiquiti_edgeswitch': 'ubiquiti_edge',
}


def setup_logger(debug=False):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        format='%(asctime)s %(levelname)s: %(message)s',
        level=level
    )

def load_credentials(yaml_file):
    try:
        with open(yaml_file) as f:
            creds = yaml.safe_load(f)
        logging.debug(f"Loaded credentials from {yaml_file}")
        return creds
    except Exception as e:
        logging.error(f"Error loading credentials file '{yaml_file}': {e}")
        sys.exit(1)

def get_device_cred(ip, creds):
    return creds.get('devices', {}).get(ip, creds.get('default', {}))

def ssh_connect(ip, creds, device_type):
    device_cred = get_device_cred(ip, creds)
    if not device_cred:
        logging.error(f"No credentials found for device {ip}")
        return None

    device_params = {
        'device_type': device_type,
        'host': ip,
        'username': device_cred.get('username', ''),
        'port': device_cred.get('optional_args', {}).get('port', 22),
        'secret': device_cred.get('secret', ''),
        'timeout': 10,
        'banner_timeout': 200,
        'auth_timeout': 30,
    }
    auth_method = device_cred.get('auth_method', 'password')

    if auth_method == 'password':
        device_params['password'] = device_cred.get('password', '')
    elif auth_method == 'ssh_key':
        device_params['use_keys'] = True
        device_params['key_file'] = device_cred.get('ssh_key_file')
    else:
        logging.error(f"Unknown auth_method '{auth_method}' for {ip}")
        return None

    try:
        net_connect = ConnectHandler(**device_params)
        if device_params['secret']:
            net_connect.enable()
        logging.debug(f"SSH connection established to {ip} ({device_type})")
        return net_connect
    except Exception as e:
        logging.error(f"Failed to connect to {ip} ({device_type}): {e}")
        return None

def detect_device_type(ip, creds):
    device_cred = get_device_cred(ip, creds)
    if not device_cred:
        logging.error(f"No credentials found for device {ip}")
        return None

    base_params = {
        'device_type': 'autodetect',
        'host': ip,
        'username': device_cred.get('username', ''),
        'password': device_cred.get('password', ''),
        'port': device_cred.get('optional_args', {}).get('port', 22),
        'timeout': 10,
    }
    try:
        guesser = SSHDetect(**base_params)
        best_match = guesser.autodetect()
        logging.info(f"Detected device type for {ip}: {best_match}")
        return best_match
    except Exception as e:
        logging.error(f"Failed to autodetect device type for {ip}: {e}")
        return None

# Extract all IP addresses from LLDP command output
def extract_all_ips(output):
    return set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', output))

# Thread-safe shared state
visited_lock = threading.Lock()
results_lock = threading.Lock()
visited_global = set()
results_global = []

def discover_single(ip, creds, templates_path):
    with visited_lock:
        if ip in visited_global:
            logging.debug(f"{ip} already visited, skipping")
            return set(), []

    logging.info(f"Discovering {ip}")

    device_type = detect_device_type(ip, creds)
    if not device_type or device_type not in VENDOR_COMMANDS:
        logging.warning(f"Skipping {ip}: unsupported or undetected device type '{device_type}'")
        with visited_lock:
            visited_global.add(ip)
        return set(), []

    net_connect = ssh_connect(ip, creds, device_type)
    if not net_connect:
        with visited_lock:
            visited_global.add(ip)
        return set(), []

    hostname = net_connect.find_prompt().strip("#>").strip()

    with visited_lock:
        visited_global.add(ip)
    with results_lock:
        results_global.append({
            'ip': ip,
            'device_type': device_type,
            'hostname': hostname,
        })

    commands = VENDOR_COMMANDS[device_type]
    neighbor_ips = set()

    for proto in ['cdp', 'lldp']:
        cmd = commands.get(proto)
        if not cmd:
            continue

        if device_type == 'juniper' and proto == 'lldp':
            try:
                output = net_connect.send_command('show lldp neighbors')
                ips = extract_all_ips(output)
                neighbor_ips.update(ips)
            except Exception as e:
                # Check if it was a syntax error, fall back
                if "syntax error" in str(e).lower():
                    logging.warning(f"Falling back to per-interface LLDP for {ip}")
                    try:
                        summary_output = net_connect.send_command("show lldp neighbors")
                        interfaces = parse_juniper_lldp_interfaces(summary_output)
                        for iface in interfaces:
                            detail_output = net_connect.send_command(f"show lldp neighbors interface {iface}")
                            ips = extract_all_ips(detail_output)
                            neighbor_ips.update(ips)
                    except Exception as inner_e:
                        logging.error(f"Fallback LLDP per-interface also failed on {ip}: {inner_e}")
                else:
                    logging.error(f"LLDP detail failed on {ip}: {e}")
            continue  # skip default logic below for this proto

    # Default for all other cases
        try:
            output = net_connect.send_command(cmd)
            ips = extract_all_ips(output)
            neighbor_ips.update(ips)
        except Exception as e:
            logging.error(f"Failed to run '{cmd}' on {ip}: {e}")
            continue

    return neighbor_ips, [(ip, device_type)]

def parse_juniper_lldp_interfaces(output):
    interfaces = set()
    for line in output.strip().splitlines():
        # Skip header or blank lines
        if line.startswith("Local Interface") or not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 1:
            interfaces.add(parts[0])
    return interfaces

def concurrent_discover(seed_ip, creds, templates_path, max_depth, max_workers=10):
    to_visit = set([seed_ip])
    current_depth = 0

    while current_depth <= max_depth and to_visit:
        logging.info(f"Starting discovery depth {current_depth} with {len(to_visit)} device(s)")
        futures = []
        next_to_visit = set()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for ip in to_visit:
                futures.append(executor.submit(discover_single, ip, creds, templates_path))

            for future in as_completed(futures):
                try:
                    neighbor_ips, _ = future.result()
                    new_ips = neighbor_ips - visited_global
                    next_to_visit.update(new_ips)
                except Exception as e:
                    logging.error(f"Error in thread during discovery: {e}")

        to_visit = next_to_visit
        current_depth += 1

    return visited_global, results_global

def save_to_csv(results, filename="discovered_devices.csv"):
    if not results:
        logging.warning("No devices discovered, skipping CSV export")
        return

    keys = results[0].keys()
    try:
        with open(filename, 'w', newline='') as f:
            dict_writer = csv.DictWriter(f, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(results)
        logging.info(f"Exported discovered devices to {filename}")
    except Exception as e:
        logging.error(f"Failed to write CSV file '{filename}': {e}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python net_discover.py <seed_ip> <credentials.yaml> <depth> [--debug]")
        sys.exit(1)

    seed_ip = sys.argv[1]
    cred_file = sys.argv[2]
    max_depth = int(sys.argv[3])
    debug = '--debug' in sys.argv

    setup_logger(debug)

    ntc_templates_path = os.path.expanduser("~/ntc-templates/ntc_templates/templates")
    if not os.path.isdir(ntc_templates_path):
        logging.warning(f"ntc-templates folder not found at {ntc_templates_path}. Proceeding without TextFSM.")

    creds = load_credentials(cred_file)

    visited_ips, results = concurrent_discover(seed_ip, creds, ntc_templates_path, max_depth)

    print("\nDiscovered devices:")
    print(tabulate(results, headers="keys", tablefmt="pretty"))

    save_to_csv(results)
