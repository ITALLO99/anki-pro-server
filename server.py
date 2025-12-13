# server.py (Hosted on Cloud)
from flask import Flask, request, jsonify, send_file
import os
import requests
import io

app = Flask(__name__)

# --- SECRETS (These live in the Cloud Environment Variables, NOT code) ---
ELEVEN_KEY = os.getenv("ELEVENLABS_API_KEY")
AZURE_KEY = os.getenv("AZURE_SPEECH_KEY")
GROQ_KEY = os.getenv("GROQ_API_KEY")

# --- 1. LICENSE CHECK ENDPOINT ---
@app.route('/check-license', methods=['POST'])
def check_license():
    user_key = request.json.get('key')
    # Connect to Gumroad/Stripe API here to verify status
    # For now, simulation:
    if user_key and len(user_key) > 5:
        return jsonify({"active": True, "plan": "pro"})
    return jsonify({"active": False}), 401

# --- 2. ELEVENLABS PROXY ---
@app.route('/tts/elevenlabs', methods=['POST'])
def tts_eleven():
    data = request.json
    text = data.get('text')
    voice_id = data.get('voice_id', '21m00Tcm4TlvDq8ikWAM') # Default voice
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": ELEVEN_KEY, # Uses YOUR hidden key
        "Content-Type": "application/json"
    }
    payload = {"text": text}
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        # Return audio directly to the desktop app
        return send_file(
            io.BytesIO(response.content),
            mimetype="audio/mpeg",
            as_attachment=True,
            download_name="audio.mp3"
        )
    return jsonify({"error": "Provider failed"}), 500

# --- 3. GROQ AI PROXY ---
@app.route('/ai/generate', methods=['POST'])
def ai_generate():
    data = request.json
    prompt = data.get('prompt')
    
    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}]
    }
    
    response = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers)
    return response.json()

if __name__ == '__main__':
    app.run(port=5000)