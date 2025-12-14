from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# --- CONFIGURATION ---
GUMROAD_ACCESS_TOKEN = os.environ.get("GUMROAD_ACCESS_TOKEN", "YOUR_GUMROAD_TOKEN_HERE")
PRODUCT_PERMALINK = "kybfx"  # Your Gumroad product permalink

# --- IN-MEMORY DATABASE FOR LOCKING ---
# In a real production app, use Redis or a Database. 
# For Render Free Tier, this resets on every deploy/restart, which is actually good for resetting stuck users.
active_sessions = {}  # Format: { "LICENSE_KEY": "MACHINE_ID" }

def verify_gumroad(license_key):
    """Checks Gumroad API to see if key exists and get the plan."""
    url = "https://api.gumroad.com/v2/licenses/verify"
    params = {
        "product_permalink": PRODUCT_PERMALINK,
        "license_key": license_key,
        "increment_uses_count": "false"  # Don't use up the activation limit, we manage it manually
    }
    
    try:
        response = requests.post(url, params=params)
        data = response.json()
        
        if data.get("success"):
            # Determine Plan based on Variant (Tier) name
            variant = data["purchase"].get("variants", "")
            plan = "free"
            if "Standard" in variant: plan = "standard"
            if "Premium" in variant: plan = "premium"
            
            return {"valid": True, "plan": plan, "uses": data["purchase"]["uses"]}
        else:
            return {"valid": False}
    except Exception as e:
        return {"valid": False, "error": str(e)}

@app.route('/check-license', methods=['POST'])
def check_license():
    data = request.json
    license_key = data.get("license_key")
    machine_id = data.get("machine_id")

    if not license_key:
        return jsonify({"active": False, "message": "No key provided"}), 400

    # 1. Verify with Gumroad
    gumroad_data = verify_gumroad(license_key)
    
    if not gumroad_data["valid"]:
        return jsonify({"active": False, "message": "Invalid Key"}), 401

    # 2. Concurrency Check (Machine ID Lock)
    # If this key is already in memory
    if license_key in active_sessions:
        registered_machine = active_sessions[license_key]
        
        # If the machine requesting is DIFFERENT from the registered one -> BLOCK
        if machine_id and registered_machine != machine_id:
             return jsonify({
                 "active": False, 
                 "message": "Key is active on another device.",
                 "code": "CONCURRENT_ACCESS"
             }), 409
    else:
        # First time seeing this key (since server restart), lock it to this machine
        if machine_id:
            active_sessions[license_key] = machine_id

    # 3. Return Success
    return jsonify({
        "active": True,
        "plan": gumroad_data["plan"],
        "remaining_credits": 5000 if gumroad_data["plan"] == "standard" else (10000 if gumroad_data["plan"] == "premium" else 0)
    })

@app.route('/credits', methods=['POST'])
def check_credits():
    # Simple mock for credits
    data = request.json
    plan = data.get("plan", "free")
    credits = 0
    if plan == "standard": credits = 5000
    if plan == "premium": credits = 10000
    return jsonify({"remaining": credits})

@app.route('/')
def home():
    return "Anki Pro Server Running"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)