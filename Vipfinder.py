# app.py
from flask import Flask, jsonify, render_template
import requests
import urllib3
from requests.auth import HTTPBasicAuth

app = Flask(__name__)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

f5_host = "https://10.1.1.11"
username = "admin"
password = "kailas@123"
auth = HTTPBasicAuth(username, password)

def fetch_json(url):
    try:
        resp = requests.get(url, auth=auth, verify=False)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from {url}: {e}")
        return None

def get_asm_policies():
    policies_url = f"{f5_host}/mgmt/tm/asm/policies?$select=name,id,enforcementMode"
    all_policies_data = fetch_json(policies_url)
    all_policies = all_policies_data.get("items", []) if all_policies_data else []

    result = []

    for policy in all_policies:
        policy_name = policy.get("name", "N/A")
        policy_id = policy.get("id")
        enforcement_mode = policy.get("enforcementMode", "N/A")
        direct_vips = "None"
        manual_vips = "None"

        if policy_id:
            detailed_policy_url = f"{f5_host}/mgmt/tm/asm/policies/{policy_id}?$select=virtualServers,manualVirtualServers"
            detailed_policy_data = fetch_json(detailed_policy_url)
            if detailed_policy_data:
                direct_vips_list = detailed_policy_data.get("virtualServers", [])
                manual_vips_list = detailed_policy_data.get("manualVirtualServers", [])
                direct_vips = ", ".join(direct_vips_list) if direct_vips_list else "None"
                manual_vips = ", ".join(manual_vips_list) if manual_vips_list else "None"
        result.append({
            "policy_name": policy_name,
            "enforcement_mode": enforcement_mode,
            "direct_vips": direct_vips,
            "manual_vips": manual_vips
        })
    return result

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/asm-policies')
def asm_policies():
    data = get_asm_policies()
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)
