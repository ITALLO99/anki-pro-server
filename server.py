from flask import Flask, request, jsonify, send_file
import os
import json
import requests
from groq import Groq

# --- CONFIGURATION ---
app = Flask(__name__)

# UPDATE THIS TO MATCH YOUR LATEST RELEASE ON GITHUB
LATEST_VERSION = "v69.0"
DOWNLOAD_URL = "https://github.com/ITALLO99/anki-pro-releases/releases/download/v69.0/anki_pro_app.exe"

# SECURE KEYS (These load from Render's Environment Variables)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
ELEVEN_KEY = os.getenv("ELEVENLABS_API_KEY")
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_REGION = os.getenv("AZURE_SPEECH_REGION")

# --- ROUTES ---

@app.route('/version', methods=['GET'])
def version():
    return jsonify({
        "version": LATEST_VERSION,
        "url": DOWNLOAD_URL
    })

@app.route('/check-license', methods=['POST'])
def check_license():
    data = request.json
    key = data.get('license_key', '')
    
    # Simple Logic: If key > 5 chars -> Premium. 
    # (Later you can connect this to Gumroad API)
    if len(key) > 5:
        return jsonify({"active": True, "plan": "premium"}) 
    else:
        return jsonify({"active": False, "error": "Invalid Key"}), 401

@app.route('/credits', methods=['POST'])
def check_credits():
    data = request.json
    plan = data.get('plan', 'free')
    
    if plan == 'premium': limit = 10000
    elif plan == 'standard': limit = 5000
    else: limit = 0
    return jsonify({"remaining": limit})

# --- NEW AI ROUTES (Fixes your 404 Error) ---

@app.route('/ai/generate', methods=['POST'])
def ai_generate():
    if not GROQ_API_KEY: return jsonify({"error": "Server missing Groq Key"}), 500
    data = request.json
    try:
        client = Groq(api_key=GROQ_API_KEY)
        chat_completion = client.chat.completions.create(
            messages=data.get("messages"),
            model=data.get("model", "llama-3.3-70b-versatile"),
            response_format=data.get("response_format", None)
        )
        return jsonify({
            "choices": [{
                "message": {
                    "content": chat_completion.choices[0].message.content
                }
            }]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/translate/deepl', methods=['POST'])
def translate_deepl():
    if not DEEPL_API_KEY: return jsonify({"error": "Server missing DeepL Key"}), 500
    data = request.json
    try:
        r = requests.post(
            "https://api-free.deepl.com/v2/translate",
            data={
                'auth_key': DEEPL_API_KEY,
                'text': data.get("text"),
                'source_lang': 'EN',
                'target_lang': 'PT'
            }
        )
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/tts/generate', methods=['POST'])
def generate_tts():
    data = request.json
    text = data.get("text")
    provider = data.get("provider")
    voice_id = data.get("voice_id")
    temp_file = "temp_tts.mp3"
    
    try:
        if provider == "elevenlabs":
            if not ELEVEN_KEY: return jsonify({"error": "Missing Eleven Key"}), 500
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            headers = {"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"}
            r = requests.post(url, json={"text": text}, headers=headers)
            if r.status_code == 200:
                with open(temp_file, 'wb') as f: f.write(r.content)
                return send_file(temp_file, mimetype="audio/mpeg")
            return jsonify({"error": r.text}), r.status_code

        elif provider == "azure":
            if not AZURE_SPEECH_KEY: return jsonify({"error": "Missing Azure Keys"}), 500
            import azure.cognitiveservices.speech as speechsdk
            
            speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_REGION)
            speech_config.speech_synthesis_voice_name = voice_id
            audio_config = speechsdk.audio.AudioOutputConfig(filename=temp_file)
            
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
            result = synthesizer.speak_text_async(text).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                return send_file(temp_file, mimetype="audio/mpeg")
            return jsonify({"error": "Azure TTS Failed"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- TRANSCRIPTION ROUTE (Video Mode) ---
@app.route('/transcribe', methods=['POST'])
def transcribe():
    if not AZURE_SPEECH_KEY: return jsonify({"error": "Missing Azure Keys"}), 500
    if 'file' not in request.files: return jsonify({"error": "No file uploaded"}), 400
    
    try:
        file = request.files['file']
        file.save("temp_upload.wav")
        
        import azure.cognitiveservices.speech as speechsdk
        speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_REGION)
        speech_config.set_profanity(speechsdk.ProfanityOption.Raw)
        
        audio_config = speechsdk.audio.AudioConfig(filename="temp_upload.wav")
        speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
        
        result = speech_recognizer.recognize_once_async().get()
        return jsonify({"text": result.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
