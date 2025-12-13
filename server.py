from flask import Flask, request, jsonify, send_file
import os
import requests
import io

app = Flask(__name__)

# --- 1. LOAD SECRETS (From Render Environment) ---
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
    # In future, connect to Gumroad/Stripe API here
    user_key = request.json.get('key')
    if user_key and len(user_key) > 5:
        return jsonify({"active": True})
    return jsonify({"active": False}), 401

# --- 3. ELEVENLABS PROXY ---
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

# --- 4. DEEPL PROXY ---
@app.route('/translate/deepl', methods=['POST'])
def translate_deepl():
    text = request.json.get('text')
    # Determines if using Free or Pro API based on key format (usually free keys end in :fx)
    domain = "api-free.deepl.com" if ":fx" in DEEPL_KEY else "api.deepl.com"
    
    url = f"https://{domain}/v2/translate"
    data = {
        'auth_key': DEEPL_KEY,
        'text': text,
        'target_lang': 'PT'
    }
    
    response = requests.post(url, data=data)
    if response.status_code == 200:
        return jsonify(response.json())
    return jsonify({"error": "DeepL failed"}), 500

# --- 5. GROQ AI PROXY ---
@app.route('/ai/generate', methods=['POST'])
def ai_generate():
    data = request.json
    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }
    # Pass through the prompt structure
    response = requests.post("https://api.groq.com/openai/v1/chat/completions", json=data, headers=headers)
    return jsonify(response.json())

# --- 6. AZURE AUTH TOKEN (The Smart Way) ---
# Instead of proxying heavy audio for transcription, we issue a temporary "Pass" 
# that the desktop app can use for 10 minutes. This keeps the Master Key safe.
@app.route('/azure/token', methods=['GET'])
def get_azure_token():
    fetch_url = f"https://{AZURE_SPEECH_REGION}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_SPEECH_KEY
    }
    response = requests.post(fetch_url, headers=headers)
    
    if response.status_code == 200:
        # Return the temporary token and the region
        return jsonify({"token": response.text, "region": AZURE_SPEECH_REGION})
    return jsonify({"error": "Azure Auth Failed"}), 401

if __name__ == '__main__':
    app.run(port=5000)
