from flask import Flask, request, jsonify, Response
import requests
import os
import sys
import re

app = Flask(__name__)

# ==============================================================================
# CONFIGURAÇÕES E VARIÁVEIS DE AMBIENTE (Segurança)
# ==============================================================================
PRODUCT_ID = "6Nm28bZgTFYl9u1nlijDBA==" 
active_sessions = {} 

# O servidor puxa as chaves do painel do Render, mantendo-as escondidas dos clientes
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
DEEPL_KEY = os.environ.get("DEEPL_API_KEY", "")
AZURE_KEY = os.environ.get("AZURE_SPEECH_KEY", "")
AZURE_REGION = os.environ.get("AZURE_SPEECH_REGION", "brazilsouth")
ELEVEN_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
PLAYHT_KEY = os.environ.get("PLAY_HT_API_KEY", "")
PLAYHT_USER = os.environ.get("PLAY_HT_USER_ID", "")
WELLSAID_KEY = os.environ.get("WELL_SAID_LABS_API_KEY", "")
CARTESIA_KEY = os.environ.get("CARTESIA_API_KEY", "")
HF_KEY = os.environ.get("HF_API_KEY", "")

def log(msg):
    print(msg, file=sys.stdout, flush=True)

# ==============================================================================
# ROTAS COMERCIAIS (GUMROAD E LICENÇAS)
# ==============================================================================
def verify_gumroad(license_key):
    url = "https://api.gumroad.com/v2/licenses/verify"
    payload = {"product_id": PRODUCT_ID, "license_key": license_key.strip(), "increment_uses_count": "false"}
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.post(url, data=payload, headers=headers)
        data = response.json()
        if data.get("success"):
            variant = data["purchase"].get("variants", "")
            product_name = data["purchase"].get("product_name", "")
            plan = "free"
            if "Standard" in variant or "Standard" in product_name: plan = "standard"
            if "Premium" in variant or "Premium" in product_name: plan = "premium"
            return {"valid": True, "plan": plan}
        return {"valid": False, "reason": data.get("message", "Unknown Error")}
    except Exception as e:
        return {"valid": False, "reason": str(e)}

@app.route('/check-license', methods=['POST'])
def check_license():
    data = request.json
    raw_key = data.get("license_key", "")
    machine_id = data.get("machine_id")

    if not raw_key: return jsonify({"active": False, "message": "No key provided"}), 400

    gumroad_result = verify_gumroad(raw_key)
    if not gumroad_result["valid"]:
        return jsonify({"active": False, "message": gumroad_result['reason']}), 401

    clean_key = raw_key.strip()
    if clean_key in active_sessions:
        if machine_id and active_sessions[clean_key] != machine_id:
             return jsonify({"active": False, "message": "Concurrent Access", "code": "CONCURRENT_ACCESS"}), 409
    else:
        if machine_id: active_sessions[clean_key] = machine_id

    return jsonify({"active": True, "plan": gumroad_result['plan']})

@app.route('/credits', methods=['POST'])
def check_credits():
    # Rota mantida para o painel de Live Status do Cliente
    plan = request.json.get("plan", "free")
    credits = 10000 if plan == "premium" else (5000 if plan == "standard" else 0)
    return jsonify({"remaining": credits})

# ==============================================================================
# ROTAS DE INTELIGÊNCIA ARTIFICIAL (O CÉREBRO)
# ==============================================================================

@app.route('/ai/generate', methods=['POST'])
def ai_generate():
    """Proxy para o Groq (Llama 3) - Gera frases e analisa PDFs"""
    if not GROQ_KEY: return jsonify({"error": "Server missing Groq Key"}), 500
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    
    response = requests.post(url, headers=headers, json=request.json)
    return jsonify(response.json()), response.status_code

@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    """Proxy para o Groq Whisper - Transcreve os recortes de vídeo"""
    if not GROQ_KEY: return jsonify({"error": "Server missing Groq Key"}), 500
    if 'file' not in request.files: return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {GROQ_KEY}"}
    files = {"file": (file.filename, file.read(), "audio/mpeg")}
    data = {"model": "whisper-large-v3", "language": "en"}
    
    response = requests.post(url, headers=headers, files=files, data=data)
    return jsonify(response.json()), response.status_code

@app.route('/translate/deepl', methods=['POST'])
def translate_deepl():
    """Proxy para o DeepL"""
    if not DEEPL_KEY: return jsonify({"error": "Server missing DeepL Key"}), 500
    
    text = request.json.get("text", "")
    url = "https://api-free.deepl.com/v2/translate"
    data = {'auth_key': DEEPL_KEY, 'text': text, 'source_lang': 'EN', 'target_lang': 'PT'}
    
    response = requests.post(url, data=data)
    return jsonify(response.json()), response.status_code

@app.route('/tts/generate', methods=['POST'])
def tts_generate():
    """O Motor Universal de Vozes - Gera o áudio e devolve o arquivo MP3 direto para o cliente"""
    data = request.json
    text = data.get("text", "")
    provider = data.get("provider", "").lower()
    voice_id = data.get("voice_id", "")

    try:
        # --- AZURE (Via REST API Leve) ---
        if provider == "azure":
            safe_text = re.sub(r'\[.*?\]', '', text).replace("&", "and")
            url = f"https://{AZURE_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
            headers = {
                "Ocp-Apim-Subscription-Key": AZURE_KEY,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "audio-16khz-32kbitrate-mono-mp3",
                "User-Agent": "AnkiProServer"
            }
            locale = "-".join(voice_id.split("-")[:2]) if "-" in voice_id else "en-US"
            
            if "<mstts:express-as" in safe_text:
                body = f"<speak version='1.0' xml:lang='{locale}'><voice xml:lang='{locale}' name='{voice_id}'>{safe_text}</voice></speak>"
            else:
                body = f"<speak version='1.0' xml:lang='{locale}'><voice name='{voice_id}'>{safe_text}</voice></speak>"
            
            res = requests.post(url, headers=headers, data=body.encode('utf-8'))
            if res.status_code == 200: return Response(res.content, mimetype="audio/mpeg")

        # --- ELEVENLABS ---
        elif provider == "elevenlabs":
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            headers = {"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"}
            payload = {"text": text, "model_id": "eleven_v3"}
            res = requests.post(url, json=payload, headers=headers)
            if res.status_code == 200: return Response(res.content, mimetype="audio/mpeg")

        # --- CARTESIA (Com injeção de emoção) ---
        elif provider == "cartesia":
            url = "https://api.cartesia.ai/tts/bytes"
            headers = {"Cartesia-Version": "2024-06-10", "X-API-Key": CARTESIA_KEY, "Content-Type": "application/json"}
            
            emo_api = None
            match = re.search(r'<emotion value="([^"]+)"', text)
            if match:
                raw_emo = match.group(1).lower()
                if any(x in raw_emo for x in ["ang", "mad", "frustrat"]): emo_api = "anger"
                elif any(x in raw_emo for x in ["sad", "cry", "fear"]): emo_api = "sadness"
                elif any(x in raw_emo for x in ["curio", "myst"]): emo_api = "curiosity"
                elif any(x in raw_emo for x in ["surpris", "amaz"]): emo_api = "surprise"
                else: emo_api = "positivity"
            
            clean_transcript = re.sub(r'<[^>]+>', '', text).strip().replace("[laughter]", "")
            
            payload = {
                "model_id": "sonic-english",
                "transcript": clean_transcript,
                "voice": {"mode": "id", "id": voice_id},
                "output_format": {"container": "mp3", "encoding": "mp3", "sample_rate": 44100}
            }
            if emo_api: payload["voice"]["__experimental_controls"] = {"emotion": [f"{emo_api}:high"]}
            
            res = requests.post(url, headers=headers, json=payload)
            if res.status_code == 200: return Response(res.content, mimetype="audio/mpeg")

        # --- PLAYHT ---
        elif provider == "playht":
            url = "https://api.play.ht/api/v2/tts/stream"
            headers = {"AUTHORIZATION": PLAYHT_KEY, "X-USER-ID": PLAYHT_USER, "accept": "audio/mpeg", "content-type": "application/json"}
            payload = {"text": text, "voice": voice_id, "output_format": "mp3"}
            res = requests.post(url, headers=headers, json=payload)
            if res.status_code == 200: return Response(res.content, mimetype="audio/mpeg")

        # --- WELLSAID LABS ---
        elif provider == "wellsaid":
            url = "https://api.wellsaidlabs.com/v1/tts/stream"
            headers = {"X-Api-Key": WELLSAID_KEY, "Accept": "audio/mpeg", "Content-Type": "application/json"}
            payload = {"text": text, "speaker_avatar_id": voice_id}
            res = requests.post(url, headers=headers, json=payload)
            if res.status_code == 200: return Response(res.content, mimetype="audio/mpeg")
            
        return jsonify({"error": f"Provider {provider} failed or invalid."}), 500
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    return "Anki Pro Central Server v1.0 - Active"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
