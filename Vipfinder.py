from flask import Flask, render_template, request
import paramiko
import re
import csv
import os
import json
import threading
import time

app = Flask(__name__)

# Hardcoded credentials (stored securely in a vault or .env in real production)
USERNAME = "admin"
PASSWORD = "yourStrongPassword"

CSV_FILE = os.path.join(os.path.dirname(__file__), 'ltms.csv')
CACHE_FILE = os.path.join(os.path.dirname(__file__), 'vip_cache.json')
CACHE_UPDATE_INTERVAL = 86400  # 24 hours

vip_cache = []  # Global cache


def get_device_list():
    devices = []
    try:
        with open(CSV_FILE, newline='') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if row:  # skip blank rows
                    devices.append(row[0].strip())
    except Exception as e:
        print(f"Error reading ltms.csv: {e}")
    return devices


def fetch_vips_from_device(address):
    result = []
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(address, username=USERNAME, password=PASSWORD, timeout=10)

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
        print(f"[ERROR] {address}: {e}")
    return result


def update_cache():
    global vip_cache
    new_data = []
    for device in get_device_list():
        new_data.extend(fetch_vips_from_device(device))

    vip_cache = new_data
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(vip_cache, f, indent=2)
        print("✅ Cache updated.")
    except Exception as e:
        print(f"[ERROR] Writing cache: {e}")


def load_cache():
    global vip_cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                vip_cache = json.load(f)
            print("✅ Cache loaded from file.")
        except Exception as e:
            print(f"[ERROR] Loading cache: {e}")
            vip_cache = []
    else:
        print("⚠️ No cache file found. Generating initial cache...")
        update_cache()


def schedule_cache_update():
    def background_updater():
        while True:
            time.sleep(CACHE_UPDATE_INTERVAL)
            print("⏰ Background cache update started...")
            update_cache()

    thread = threading.Thread(target=background_updater, daemon=True)
    thread.start()


@app.route('/', methods=['GET', 'POST'])
def index():
    ip = ''
    results = []
    if request.method == 'POST':
        ip = request.form['ip_address'].strip()
        for entry in vip_cache:
            if ip in entry['destination']:
                results.append(entry)
    return render_template('index.html', results=results, ip=ip)


if __name__ == '__main__':
    load_cache()
    schedule_cache_update()
    app.run(debug=True)