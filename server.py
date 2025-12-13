from flask import Flask, request, jsonify, send_file
import os
import requests
import io

app = Flask(__name__)

# --- 1. SECRETS ---
ELEVEN_KEY = os.getenv("ELEVENLABS_API_KEY")
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")
DEEPL_KEY = os.getenv("DEEPL_API_KEY")
GROQ_KEY = os.getenv("GROQ_API_KEY")

# --- 2. PLAN CONFIGURATION (From Render Env) ---
# You will add these 3 IDs in Render later
PRODUCT_ID_FREE = os.getenv("ID_FREE")
PRODUCT_ID_STANDARD = os.getenv("ID_STANDARD")
PRODUCT_ID_PREMIUM = os.getenv("ID_PREMIUM")

# Map IDs to Plan Names for easy logic
PLAN_MAP = {
    PRODUCT_ID_FREE: "free",
    PRODUCT_ID_STANDARD: "standard",
    PRODUCT_ID_PREMIUM: "premium"
}

# --- 3. SMART LICENSE CHECK ---
@app.route('/check-license', methods=['POST'])
def check_license():
    user_key = request.json.get('key')
    if not user_key: return jsonify({"active": False}), 401

    # We try checking the key against all 3 products
    detected_plan = None
    
    for pid, plan_name in PLAN_MAP.items():
        if not pid: continue # Skip if not set in Render yet
        
        try:
            res = requests.post(
                "https://api.gumroad.com/v2/licenses/verify",
                data={"product_id": pid, "license_key": user_key, "increment_uses_count": "false"}
            )
            
            if res.status_code == 200:
                data = res.json()
                if data.get("success") and not data.get("purchase", {}).get("refunded", False):
                    # Found it!
                    detected_plan = plan_name
                    break # Stop checking other products
        except: pass

    if detected_plan:
        # Return success AND the plan type
        return jsonify({"active": True, "plan": detected_plan})
    
    return jsonify({"active": False}), 401

# --- 4. CREDITS CHECK (Dynamic Limit) ---
@app.route('/credits', methods=['POST']) # Changed to POST to receive plan info
def get_credits():
    # The app sends us the user's plan so we know which limit to show
    user_plan = request.json.get('plan', 'free')
    
    # Define Limits
    limits = {
        "free": 0,
        "standard": 5000,
        "premium": 10000
    }
    
    try:
        # Get Master Balance (Real ElevenLabs Account)
        headers = {"xi-api-key": ELEVEN_KEY}
        r = requests.get("https://api.elevenlabs.io/v1/user/subscription", headers=headers, timeout=5)
        
        if r.status_code == 200:
            d = r.json()
            master_remaining = d.get("character_count", 0) - d.get("character_used", 0)
            
            # The User's "Virtual Balance" is the Plan Limit
            # (In a real SaaS, you'd track their individual usage in a database. 
            # For now, we just display their theoretical cap).
            user_cap = limits.get(user_plan, 0)
            
            return jsonify({
                "remaining": user_cap, # Show user their plan limit
                "master_pool": master_remaining # Internal debug info if needed
            })
    except: pass
    return jsonify({"error": "Error"}), 500

# ... (Keep tts_eleven, translate_deepl, ai_generate, get_azure_token exactly as they were) ...
# Just copy the proxy functions from v36.0 here
