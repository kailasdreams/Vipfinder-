from flask import Flask, render_template, request
import paramiko
import re
import csv
import os
import json
import threading
import time

app = Flask(__name__)
CACHE_FILE = os.path.join(os.path.dirname(__file__), 'vip_cache.json')
CSV_FILE = os.path.join(os.path.dirname(__file__), 'ltms.csv')
CACHE_UPDATE_INTERVAL = 86400  # 24 hours

vip_cache = []  # global variable for storing VIP data


def get_ltm_list():
    ltms = []
    try:
        with open(CSV_FILE, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                ltms.append({
                    'address': row['address'],
                    'credentials': {
                        'username': row['username'],
                        'password': row['password']
                    }
                })
    except Exception as e:
        print(f"Error reading LTM CSV: {e}")
    return ltms


def fetch_vips_from_device(address, credentials):
    result = []
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(address, username=credentials['username'], password=credentials['password'], timeout=10)

        cmd = "list ltm virtual all-properties"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode()

        virtuals = re.split(r'ltm virtual (\S+) \{', output)
        for i in range(1, len(virtuals), 2):
            name = virtuals[i]
            block = virtuals[i + 1]
            dest_match = re.search(r'destination\s+(\S+)', block)
            destination = dest_match.group(1) if dest_match else 'Unknown'
            result.append({
                'device': address,
                'vip_name': name,
                'destination': destination
            })

        ssh.close()
    except Exception as e:
        print(f"Error from {address}: {e}")
    return result


def update_cache():
    global vip_cache
    new_data = []
    for ltm in get_ltm_list():
        device_vips = fetch_vips_from_device(ltm['address'], ltm['credentials'])
        new_data.extend(device_vips)

    vip_cache = new_data
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(vip_cache, f, indent=2)
        print("Cache updated successfully.")
    except Exception as e:
        print(f"Error writing cache: {e}")


def load_cache():
    global vip_cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                vip_cache = json.load(f)
            print("Cache loaded.")
        except Exception as e:
            print(f"Failed to load cache: {e}")
            vip_cache = []
    else:
        print("No cache file found. Creating initial cache...")
        update_cache()


def schedule_cache_updates():
    def updater():
        while True:
            time.sleep(CACHE_UPDATE_INTERVAL)
            update_cache()

    thread = threading.Thread(target=updater, daemon=True)
    thread.start()


@app.route('/', methods=['GET', 'POST'])
def index():
    ip = ''
    results = []
    if request.method == 'POST':
        ip = request.form['ip_address']
        for entry in vip_cache:
            if ip in entry['destination']:
                results.append(entry)
    return render_template('index.html', results=results, ip=ip)


if __name__ == '__main__':
    load_cache()
    schedule_cache_updates()
    app.run(debug=True)