from flask import Flask, request, jsonify
import requests
import os
import sys

app = Flask(__name__)

# --- CONFIGURATION ---
PRODUCT_ID = "6Nm28bZgTFYl9u1nlijDBA==" 

# 1. UPDATE THIS NUMBER when you release a new version
LATEST_VERSION = "v64.0" 

# 2. PASTE THE GITHUB LINK HERE (from Part 1, Step 6)
# Example: "https://github.com/ITALLO99/anki-pro-server/releases/download/v62.0/AnkiProApp.exe"
DOWNLOAD_URL = "https://github.com/ITALLO99/anki-pro-server/releases/download/v64.0/anki_pro_app.exe" 

active_sessions = {} 

def log(msg):
    print(msg, file=sys.stdout, flush=True)

def verify_gumroad(license_key):
    url = "https://api.gumroad.com/v2/licenses/verify"
    clean_key = license_key.strip()
    
    payload = {
        "product_id": PRODUCT_ID,
        "license_key": clean_key,
        "increment_uses_count": "false"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        log(f"--- CHECKING KEY: {clean_key} ---")
        response = requests.post(url, data=payload, headers=headers)
        
        try:
            data = response.json()
        except:
            return {"valid": False, "reason": "Gumroad returned non-JSON"}

        if data.get("success"):
            variant = data["purchase"].get("variants", "")
            product_name = data["purchase"].get("product_name", "")
            
            plan = "free"
            if "Standard" in variant or "Standard" in product_name: plan = "standard"
            if "Premium" in variant or "Premium" in product_name: plan = "premium"
            
            return {"valid": True, "plan": plan}
        else:
            return {"valid": False, "reason": data.get("message", "Unknown Error")}
            
    except Exception as e:
        return {"valid": False, "reason": str(e)}

@app.route('/version', methods=['GET'])
def get_version():
    """Returns the latest version and DIRECT download link for the client."""
    return jsonify({
        "version": LATEST_VERSION,
        "url": DOWNLOAD_URL
    })

@app.route('/check-license', methods=['POST'])
def check_license():
    data = request.json
    raw_key = data.get("license_key", "")
    machine_id = data.get("machine_id")

    if not raw_key:
        return jsonify({"active": False, "message": "No key provided"}), 400

    gumroad_result = verify_gumroad(raw_key)
    
    if not gumroad_result["valid"]:
        log(f"FAILURE: {gumroad_result['reason']}")
        return jsonify({"active": False, "message": gumroad_result['reason']}), 401

    clean_key = raw_key.strip()
    if clean_key in active_sessions:
        registered_machine = active_sessions[clean_key]
        if machine_id and registered_machine != machine_id:
             log(f"Blocked Concurrent Access: {clean_key}")
             return jsonify({"active": False, "message": "Concurrent Access", "code": "CONCURRENT_ACCESS"}), 409
    else:
        if machine_id: active_sessions[clean_key] = machine_id

    log(f"Success! Plan: {gumroad_result['plan']}")
    return jsonify({
        "active": True,
        "plan": gumroad_result['plan'],
        "remaining_credits": 5000 if gumroad_result["plan"] == "standard" else (10000 if gumroad_result["plan"] == "premium" else 0)
    })

@app.route('/credits', methods=['POST'])
def check_credits():
    data = request.json
    plan = data.get("plan", "free")
    credits = 0
    if plan == "standard": credits = 5000
    if plan == "premium": credits = 10000
    return jsonify({"remaining": credits})

@app.route('/')
def home():
    return f"Anki Pro Server {LATEST_VERSION} Running"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)




