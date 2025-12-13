from flask import Flask, request, jsonify, send_file
import os
import requests
import io

app = Flask(__name__)

# --- 1. LOAD SECRETS ---
ELEVEN_KEY = os.getenv("ELEVENLABS_API_KEY")
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")
DEEPL_KEY = os.getenv("DEEPL_API_KEY")
GROQ_KEY = os.getenv("GROQ_API_KEY")

# NEW: The ID of your product on Gumroad (e.g., "anki-pro-academy")
GUMROAD_PERMALINK = os.getenv("GUMROAD_PERMALINK") 

# --- 2. REAL LICENSE CHECK (GUMROAD) ---
@app.route('/check-license', methods=['POST'])
def check_license():
    user_key = request.json.get('key')
    
    if not user_key:
        return jsonify({"active": False}), 401

    # Ask Gumroad if this key exists and is paid for
    try:
        response = requests.post(
            "https://api.gumroad.com/v2/licenses/verify",
            data={
                "product_id": GUMROAD_PERMALINK,
                "license_key": user_key,
                "increment_uses_count": "true"  # Tracks how many times they install it
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            # Check if success AND not refunded/cancelled
            if data.get("success") and not data.get("purchase", {}).get("refunded", False):
                return jsonify({"active": True})
                
    except Exception as e:
        print(f"Gumroad Error: {e}")

    return jsonify({"active": False}), 401

# --- 3. CREDITS CHECK ---
@app.route('/credits', methods=['GET'])
def get_credits():
    try:
        headers = {"xi-api-key": ELEVEN_KEY}
        r = requests.get("https://api.elevenlabs.io/v1/user/subscription", headers=headers, timeout=5)
        if r.status_code == 200:
            d = r.json()
            # Return Master remaining.
            return jsonify({"remaining": d.get("character_count", 0) - d.get("character_used", 0)}) 
        return jsonify({"error": "Provider Error"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- 4. PROVIDER PROXIES (Standard) ---
@app.route('/tts/elevenlabs', methods=['POST'])
def tts_eleven():
    # ... (Same as v30, no changes needed)
    data = request.json
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{data.get('voice_id')}"
    headers = {"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"}
    resp = requests.post(url, json={"text": data.get('text')}, headers=headers)
    if resp.status_code == 200:
        return send_file(io.BytesIO(resp.content), mimetype="audio/mpeg", as_attachment=True, download_name="a.mp3")
    return jsonify({"error": "TTS Failed"}), 500

@app.route('/translate/deepl', methods=['POST'])
def translate_deepl():
    # ... (Same as v30)
    text = request.json.get('text')
    domain = "api-free.deepl.com" if ":fx" in DEEPL_KEY else "api.deepl.com"
    resp = requests.post(f"https://{domain}/v2/translate", data={'auth_key': DEEPL_KEY, 'text': text, 'target_lang': 'PT'})
    return jsonify(resp.json())

@app.route('/ai/generate', methods=['POST'])
def ai_generate():
    # ... (Same as v30)
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    resp = requests.post("https://api.groq.com/openai/v1/chat/completions", json=request.json, headers=headers)
    return jsonify(resp.json())

@app.route('/azure/token', methods=['GET'])
def get_azure_token():
    # ... (Same as v30)
    url = f"https://{AZURE_SPEECH_REGION}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
    resp = requests.post(url, headers={'Ocp-Apim-Subscription-Key': AZURE_SPEECH_KEY})
    if resp.status_code == 200: return jsonify({"token": resp.text, "region": AZURE_SPEECH_REGION})
    return jsonify({"error": "Auth Failed"}), 401

if __name__ == '__main__':
    app.run(port=5000)
