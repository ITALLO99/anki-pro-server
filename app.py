from flask import Flask, request, jsonify
import requests
import os
import sys

app = Flask(__name__)

# --- CONFIGURATION ---
GUMROAD_ACCESS_TOKEN = os.environ.get("GUMROAD_ACCESS_TOKEN", "YOUR_GUMROAD_TOKEN_HERE")
PRODUCT_PERMALINK = "kybfx" 

active_sessions = {} 

def verify_gumroad(license_key):
    url = "https://api.gumroad.com/v2/licenses/verify"
    payload = {
        "product_permalink": PRODUCT_PERMALINK,
        "license_key": license_key,
        "increment_uses_count": "false"
    }
    
    try:
        # Debugging: Print exactly what we are sending
        print(f"Checking Key: {license_key} for Product: {PRODUCT_PERMALINK}", file=sys.stdout)
        
        response = requests.post(url, data=payload)
        
        # Debugging: Print exactly what Gumroad replied
        print(f"Gumroad Response Status: {response.status_code}", file=sys.stdout)
        print(f"Gumroad Response Body: {response.text}", file=sys.stdout)
        
        data = response.json()
        
        if data.get("success"):
            variant = data["purchase"].get("variants", "")
            plan = "free"
            if "Standard" in variant: plan = "standard"
            if "Premium" in variant: plan = "premium"
            return {"valid": True, "plan": plan}
        else:
            return {"valid": False}
    except Exception as e:
        print(f"Gumroad Connection Error: {e}", file=sys.stdout)
        return {"valid": False, "error": str(e)}

@app.route('/check-license', methods=['POST'])
def check_license():
    data = request.json
    license_key = data.get("license_key")
    machine_id = data.get("machine_id")

    if not license_key:
        return jsonify({"active": False, "message": "No key provided"}), 400

    gumroad_data = verify_gumroad(license_key)
    
    if not gumroad_data["valid"]:
        return jsonify({"active": False, "message": "Invalid Key"}), 401

    if license_key in active_sessions:
        registered_machine = active_sessions[license_key]
        if machine_id and registered_machine != machine_id:
             return jsonify({"active": False, "message": "Concurrent Access", "code": "CONCURRENT_ACCESS"}), 409
    else:
        if machine_id: active_sessions[license_key] = machine_id

    return jsonify({
        "active": True,
        "plan": gumroad_data["plan"],
        "remaining_credits": 5000 if gumroad_data["plan"] == "standard" else (10000 if gumroad_data["plan"] == "premium" else 0)
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
    return "Anki Pro Server Running - v57 Debug Mode"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
