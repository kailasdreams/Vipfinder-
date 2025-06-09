from flask import Flask, render_template, request
import requests
import csv
import os
import json
import threading
import time
import re

app = Flask(__name__)

# Configuration
USERNAME = "admin"
PASSWORD = "yourStrongPassword"  # Change this
CSV_FILE = os.path.join(os.path.dirname(__file__), 'ltms.csv')
CACHE_FILE = os.path.join(os.path.dirname(__file__), 'vip_cache.json')
CACHE_UPDATE_INTERVAL = 86400  # 24 hours

vip_cache = []

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()

def get_device_list():
    devices = []
    try:
        with open(CSV_FILE, newline='') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if row:
                    devices.append(row[0].strip())
    except Exception as e:
        print(f"Error reading ltms.csv: {e}")
    return devices

def extract_ip(destination):
    match = re.search(r'/(\d+\.\d+\.\d+\.\d+):\d+', destination)
    return match.group(1) if match else destination

def get_vips_from_device(ip):
    url = f"https://{ip}/mgmt/tm/ltm/virtual?$select=name,destination,partition"
    vips = []
    try:
        response = requests.get(url, auth=(USERNAME, PASSWORD), verify=False, timeout=10)
        response.raise_for_status()
        data = response.json()

        for item in data.get("items", []):
            vips.append({
                "device": ip,
                "vip_name": item.get("name"),
                "destination": item.get("destination", ""),
                "partition": item.get("partition", "Common")
            })
    except requests.RequestException as e:
        print(f"[ERROR] Failed to fetch from {ip}: {e}")
    return vips

def update_cache():
    global vip_cache
    all_vips = []
    for device in get_device_list():
        print(f"Fetching VIPs from {device}...")
        all_vips.extend(get_vips_from_device(device))

    vip_cache = all_vips
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
        print("⚠️ No cache found, generating...")
        update_cache()

def schedule_cache_update():
    def updater():
        while True:
            time.sleep(CACHE_UPDATE_INTERVAL)
            print("⏰ Updating cache in background...")
            update_cache()
    thread = threading.Thread(target=updater, daemon=True)
    thread.start()

@app.route('/', methods=['GET', 'POST'])
def index():
    ip = ''
    results = []
    if request.method == 'POST':
        ip = request.form['ip_address'].strip()
        for entry in vip_cache:
            if ip in extract_ip(entry['destination']):
                results.append(entry)
    return render_template('index.html', results=results, ip=ip)

if __name__ == '__main__':
    load_cache()
    schedule_cache_update()
    app.run(debug=True)