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

# --- 2. SINGLE PRODUCT CONFIGURATION ---
# Now we only need ONE ID for the main "Anki App PRO" product
PRODUCT_ID_MAIN = os.getenv("ID_MAIN") 

# --- 3. TIERED LICENSE CHECK ---
@app.route('/check-license', methods=['POST'])
def check_license():
    user_key = request.json.get('key')
    if not user_key: return jsonify({"active": False}), 401

    try:
        # Verify against the MAIN product
        res = requests.post(
            "https://api.gumroad.com/v2/licenses/verify",
            data={"product_id": PRODUCT_ID_MAIN, "license_key": user_key, "increment_uses_count": "false"}
        )
        
        if res.status_code == 200:
            data = res.json()
            if not data.get("success"): return jsonify({"active": False})

            purchase = data.get("purchase", {})
            
            # 1. Security Checks (Refund/Chargeback/Cancelled)
            if purchase.get("refunded") or purchase.get("chargebacked"):
                return jsonify({"active": False})
            if purchase.get("subscription_cancelled_at") or purchase.get("subscription_failed_at"):
                return jsonify({"active": False})

            # 2. DETECT VARIANT (TIER)
            # Gumroad returns variants like: "Plan: Premium" or "Tier: Standard"
            variants = purchase.get("variants", "")
            
            # Default to free if no variant found (safety net)
            detected_plan = "free"
            
            # Check for keywords in the variant name
            if "Premium" in variants:
                detected_plan = "premium"
            elif "Standard" in variants:
                detected_plan = "standard"
            elif "Free" in variants:
                detected_plan = "free"
            
            return jsonify({"active": True, "plan": detected_plan})
                
    except Exception as e:
        print(f"Error: {e}")

    return jsonify({"active": False}), 401

# --- 4. CREDITS & PROXIES (Standard) ---
@app.route('/credits', methods=['POST'])
def get_credits():
    user_plan = request.json.get('plan', 'free')
    # Premium gets 10k, Standard 5k, Free 0
    limits = {"free": 0, "standard": 5000, "premium": 10000}
    try:
        headers = {"xi-api-key": ELEVEN_KEY}
        r = requests.get("https://api.elevenlabs.io/v1/user/subscription", headers=headers, timeout=5)
        if r.status_code == 200: return jsonify({"remaining": limits.get(user_plan, 0)}) 
        return jsonify({"error": "Provider Error"}), 500
    except: return jsonify({"error": "Error"}), 500

@app.route('/tts/elevenlabs', methods=['POST'])
def tts_eleven():
    data = request.json
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{data.get('voice_id')}"
    headers = {"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"}
    resp = requests.post(url, json={"text": data.get('text')}, headers=headers)
    if resp.status_code == 200: return send_file(io.BytesIO(resp.content), mimetype="audio/mpeg", as_attachment=True, download_name="a.mp3")
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
