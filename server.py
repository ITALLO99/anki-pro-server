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

# --- 2. MULTI-PRODUCT CONFIGURATION ---
# You will add these IDs in Render Environment Variables
PRODUCT_ID_FREE = os.getenv("ID_FREE")
PRODUCT_ID_STANDARD = os.getenv("ID_STANDARD")
PRODUCT_ID_PREMIUM = os.getenv("ID_PREMIUM")

# Map IDs to Plan Names
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

    detected_plan = None
    
    # Try verification against all 3 products to find which one fits
    for pid, plan_name in PLAN_MAP.items():
        if not pid: continue 
        
        try:
            # Use 'product_id' as required by modern Gumroad API
            res = requests.post(
                "https://api.gumroad.com/v2/licenses/verify",
                data={"product_id": pid, "license_key": user_key, "increment_uses_count": "false"}
            )
            
            if res.status_code == 200:
                data = res.json()
                # Check success + active subscription
                if data.get("success") and not data.get("purchase", {}).get("refunded", False):
                    # Also check for cancelled subscriptions if you want strict enforcement
                    if not data.get("purchase", {}).get("subscription_cancelled_at"):
                        detected_plan = plan_name
                        break
        except: pass

    if detected_plan:
        return jsonify({"active": True, "plan": detected_plan})
    
    return jsonify({"active": False}), 401

# --- 4. TIERED CREDITS CHECK ---
@app.route('/credits', methods=['POST'])
def get_credits():
    user_plan = request.json.get('plan', 'free')
    
    # DEFINE YOUR LIMITS HERE
    limits = {
        "free": 0,
        "standard": 5000,
        "premium": 10000
    }
    
    try:
        headers = {"xi-api-key": ELEVEN_KEY}
        r = requests.get("https://api.elevenlabs.io/v1/user/subscription", headers=headers, timeout=5)
        if r.status_code == 200:
            # Return the limit specific to THEIR plan
            return jsonify({"remaining": limits.get(user_plan, 0)}) 
        return jsonify({"error": "Provider Error"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- PROXIES (Standard) ---
@app.route('/tts/elevenlabs', methods=['POST'])
def tts_eleven():
    data = request.json
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{data.get('voice_id')}"
    headers = {"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"}
    resp = requests.post(url, json={"text": data.get('text')}, headers=headers)
    if resp.status_code == 200:
        return send_file(io.BytesIO(resp.content), mimetype="audio/mpeg", as_attachment=True, download_name="a.mp3")
    return jsonify({"error": "TTS Failed"}), 500

@app.route('/translate/deepl', methods=['POST'])
def translate_deepl():
    text = request.json.get('text')
    domain = "api-free.deepl.com" if ":fx" in DEEPL_KEY else "api.deepl.com"
    resp = requests.post(f"https://{domain}/v2/translate", data={'auth_key': DEEPL_KEY, 'text': text, 'target_lang': 'PT'})
    return jsonify(resp.json())

@app.route('/ai/generate', methods=['POST'])
def ai_generate():
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    resp = requests.post("https://api.groq.com/openai/v1/chat/completions", json=request.json, headers=headers)
    return jsonify(resp.json())

@app.route('/azure/token', methods=['GET'])
def get_azure_token():
    url = f"https://{AZURE_SPEECH_REGION}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
    resp = requests.post(url, headers={'Ocp-Apim-Subscription-Key': AZURE_SPEECH_KEY})
    if resp.status_code == 200: return jsonify({"token": resp.text, "region": AZURE_SPEECH_REGION})
    return jsonify({"error": "Auth Failed"}), 401

if __name__ == '__main__':
    app.run(port=5000)
