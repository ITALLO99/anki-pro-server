from flask import Flask, request, jsonify
import requests
import os
import sys

app = Flask(__name__)

# --- CONFIGURATION ---
# We don't need the Token for simple verification, just the permalink.
PRODUCT_PERMALINK = "kybfx" 

active_sessions = {} 

def log(msg):
    """Forces logs to appear immediately in Render."""
    print(msg, file=sys.stdout, flush=True)

def verify_gumroad(license_key):
    url = "https://api.gumroad.com/v2/licenses/verify"
    
    # CLEAN THE KEY: Remove accidental spaces
    clean_key = license_key.strip()
    
    payload = {
        "product_permalink": PRODUCT_PERMALINK,
        "license_key": clean_key,
        "increment_uses_count": "false"
    }
    
    try:
        log(f"--- CHECKING KEY: {clean_key} ---")
        
        response = requests.post(url, data=payload)
        
        log(f"Gumroad HTTP Code: {response.status_code}")
        log(f"Gumroad Raw Response: {response.text}")
        
        try:
            data = response.json()
        except:
            return {"valid": False, "reason": "Gumroad returned non-JSON"}

        if data.get("success"):
            variant = data["purchase"].get("variants", "")
            plan = "free"
            if "Standard" in variant: plan = "standard"
            if "Premium" in variant: plan = "premium"
            return {"valid": True, "plan": plan}
        else:
            # Gumroad usually gives a message like "License key not found"
            reason = data.get("message", "Unknown Error")
            return {"valid": False, "reason": reason}
            
    except Exception as e:
        log(f"Connection Error: {e}")
        return {"valid": False, "reason": str(e)}

@app.route('/check-license', methods=['POST'])
def check_license():
    data = request.json
    raw_key = data.get("license_key", "")
    machine_id = data.get("machine_id")

    if not raw_key:
        return jsonify({"active": False, "message": "No key provided"}), 400

    # 1. Verify with Gumroad
    gumroad_result = verify_gumroad(raw_key)
    
    if not gumroad_result["valid"]:
        # We return the EXACT reason from Gumroad to the client/logs
        log(f"Verification Failed: {gumroad_result['reason']}")
        return jsonify({"active": False, "message": gumroad_result['reason']}), 401

    # 2. Concurrency Check (Anti-Sharing)
    clean_key = raw_key.strip()
    if clean_key in active_sessions:
        registered_machine = active_sessions[clean_key]
        if machine_id and registered_machine != machine_id:
             log(f"Concurrent Access Blocked: {clean_key}")
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
    return "Anki Pro Server v58.0 - Logging Active"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
