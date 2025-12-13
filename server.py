from flask import Flask, request, jsonify, send_file
import os
import requests
import io

app = Flask(__name__)

# --- 1. LOAD SECRETS ---
ELEVEN_KEY = os.getenv("ELEVENLABS_API_KEY")
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")
AZURE_TRANS_KEY = os.getenv("AZURE_TRANSLATOR_KEY") 
AZURE_TRANS_REGION = os.getenv("AZURE_TRANSLATOR_REGION")
DEEPL_KEY = os.getenv("DEEPL_API_KEY")
GROQ_KEY = os.getenv("GROQ_API_KEY")

# --- 2. LICENSE CHECK ---
@app.route('/check-license', methods=['POST'])
def check_license():
    user_key = request.json.get('key')
    if user_key and len(user_key) > 5:
        return jsonify({"active": True})
    return jsonify({"active": False}), 401

# --- 3. CREDITS CHECK (NEW) ---
@app.route('/credits', methods=['GET'])
def get_credits():
    """
    Returns the Master Account balance.
    FUTURE UPGRADE: Implement a database here to track 
    'user_key' usage and enforce the 10k limit per user.
    """
    try:
        headers = {"xi-api-key": ELEVEN_KEY}
        r = requests.get("https://api.elevenlabs.io/v1/user/subscription", headers=headers, timeout=5)
        if r.status_code == 200:
            d = r.json()
            total = d.get("character_count", 0)
            used = d.get("character_used", 0)
            # For now, return Master remaining. 
            # Later, you can return min(10000, master_remaining) based on user logic.
            return jsonify({"remaining": total - used, "limit": 10000}) 
        return jsonify({"error": "Provider Error"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- 4. ELEVENLABS PROXY ---
@app.route('/tts/elevenlabs', methods=['POST'])
def tts_eleven():
    data = request.json
    text = data.get('text')
    voice_id = data.get('voice_id', '21m00Tcm4TlvDq8ikWAM') 
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"}
    
    response = requests.post(url, json={"text": text}, headers=headers)
    
    if response.status_code == 200:
        return send_file(io.BytesIO(response.content), mimetype="audio/mpeg", as_attachment=True, download_name="audio.mp3")
    return jsonify({"error": "Provider failed", "details": response.text}), 500

# --- 5. DEEPL PROXY ---
@app.route('/translate/deepl', methods=['POST'])
def translate_deepl():
    text = request.json.get('text')
    domain = "api-free.deepl.com" if ":fx" in DEEPL_KEY else "api.deepl.com"
    
    url = f"https://{domain}/v2/translate"
    data = {'auth_key': DEEPL_KEY, 'text': text, 'target_lang': 'PT'}
    
    response = requests.post(url, data=data)
    if response.status_code == 200:
        return jsonify(response.json())
    return jsonify({"error": "DeepL failed"}), 500

# --- 6. GROQ AI PROXY ---
@app.route('/ai/generate', methods=['POST'])
def ai_generate():
    data = request.json
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    response = requests.post("https://api.groq.com/openai/v1/chat/completions", json=data, headers=headers)
    return jsonify(response.json())

# --- 7. AZURE TOKEN ---
@app.route('/azure/token', methods=['GET'])
def get_azure_token():
    fetch_url = f"https://{AZURE_SPEECH_REGION}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
    headers = {'Ocp-Apim-Subscription-Key': AZURE_SPEECH_KEY}
    response = requests.post(fetch_url, headers=headers)
    if response.status_code == 200:
        return jsonify({"token": response.text, "region": AZURE_SPEECH_REGION})
    return jsonify({"error": "Azure Auth Failed"}), 401

if __name__ == '__main__':
    app.run(port=5000)
