from flask import Flask, request, jsonify, Response
import requests
import os
import sys
import re
from datetime import datetime

app = Flask(__name__)

# --- OS SEUS 3 PRODUTOS DO GUMROAD ---
PERMALINKS = [
    "kybfx",      # Plano Mensal
    "toreea",     # Acesso Vitalício
    "nuixna"      # Add-ons (Créditos IA)
]

active_sessions = {} 

GROQ_KEY = os.environ.get("GROQ_API_KEY", "").strip()
DEEPL_KEY = os.environ.get("DEEPL_API_KEY", "").strip()
AZURE_KEY = os.environ.get("AZURE_SPEECH_KEY", "").strip()
AZURE_REGION = os.environ.get("AZURE_SPEECH_REGION", "brazilsouth").strip()
ELEVEN_KEY = os.environ.get("ELEVENLABS_API_KEY", "").strip()
ELEVEN_KEY_2 = os.environ.get("ELEVENLABS_API_KEY_2", "").strip() 
PLAYHT_KEY = os.environ.get("PLAY_HT_API_KEY", "").strip()
PLAYHT_USER = os.environ.get("PLAY_HT_USER_ID", "").strip()
WELLSAID_KEY = os.environ.get("WELL_SAID_LABS_API_KEY", "").strip()
CARTESIA_KEY = os.environ.get("CARTESIA_API_KEY", "").strip()
HF_KEY = os.environ.get("HF_API_KEY", "").strip()

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()

# ==============================================================================
# CONTROLE DE ATUALIZAÇÕES AUTOMÁTICAS (AUTO-UPDATER VIA GITHUB RELEASES)
# ==============================================================================
CURRENT_APP_VERSION = float(os.environ.get("LATEST_APP_VERSION", "5.0"))
DOWNLOAD_URL = os.environ.get("UPDATE_DOWNLOAD_URL", "") 

@app.route('/check-update', methods=['GET'])
def check_update():
    return jsonify({
        "latest_version": CURRENT_APP_VERSION,
        "download_url": DOWNLOAD_URL,
        "release_notes": "Uma nova atualização obrigatória está disponível com melhorias de estabilidade e novas funcionalidades!"
    })
# ==============================================================================

def alert_admin(provider_name, error_msg):
    if DISCORD_WEBHOOK_URL:
        try:
            msg = f"🚨 **ALERTA DE SAAS (FALTA DE CRÉDITOS)** 🚨\nO provedor **{provider_name}** recusou uma requisição!\n**Erro:** `{error_msg}`"
            requests.post(DISCORD_WEBHOOK_URL, json={"content": msg}, timeout=5)
        except: pass

def log(msg):
    print(msg, file=sys.stdout, flush=True)

def verify_gumroad(license_key):
    url = "https://api.gumroad.com/v2/licenses/verify"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for permalink in PERMALINKS:
        payload = {"product_permalink": permalink, "license_key": license_key.strip(), "increment_uses_count": "false"}
        try:
            response = requests.post(url, data=payload, headers=headers)
            data = response.json()
            if data.get("success"):
                purchase = data.get("purchase", {})
                variant = purchase.get("variants", "")
                product_name = purchase.get("product_name", "")
                
                plan = "free"
                if "Standard" in variant or "Standard" in product_name: plan = "standard"
                if "Premium" in variant or "Premium" in product_name: plan = "premium"
                
                created_at_str = purchase.get("created_at", "")
                days_diff = 0
                current_cycle = 0
                if created_at_str:
                    try:
                        created_dt = datetime.strptime(created_at_str[:19], "%Y-%m-%dT%H:%M:%S")
                        now_dt = datetime.utcnow()
                        days_diff = (now_dt - created_dt).days
                        current_cycle = max(0, days_diff // 30)
                    except Exception as e:
                        log(f"Erro de data: {e}")
                
                return {"valid": True, "plan": plan, "current_cycle": current_cycle, "days_diff": days_diff}
        except Exception:
            continue
            
    return {"valid": False, "reason": "Chave inválida ou não encontrada."}

# ... (MANTENHA O RESTO DO SEU SERVER.PY INTACTO A PARTIR DAQUI: @app.route('/check-license', methods=['POST']) ) ...


# ==============================================================================
# CONTROLE DE ATUALIZAÇÕES AUTOMÁTICAS (AUTO-UPDATER VIA GITHUB RELEASES)
# ==============================================================================
# O servidor agora lê a versão e o link diretamente do painel do Render!
CURRENT_APP_VERSION = float(os.environ.get("LATEST_APP_VERSION", "5.0"))
DOWNLOAD_URL = os.environ.get("UPDATE_DOWNLOAD_URL", "") 

@app.route('/check-update', methods=['GET'])
def check_update():
    return jsonify({
        "latest_version": CURRENT_APP_VERSION,
        "download_url": DOWNLOAD_URL,
        "release_notes": "Uma nova atualização obrigatória está disponível com melhorias de estabilidade e novas funcionalidades!"
    })
# ==============================================================================      

@app.route('/check-license', methods=['POST'])
def check_license():
    data = request.json
    raw_key = data.get("license_key", "")
    addon_keys = data.get("addon_keys", []) 
    machine_id = data.get("machine_id")
    
    if not raw_key: return jsonify({"active": False, "message": "No key provided"}), 400
    
    main_res = verify_gumroad(raw_key)
    if not main_res["valid"]: return jsonify({"active": False, "message": main_res['reason']}), 401
        
    clean_key = raw_key.strip()
    if clean_key in active_sessions:
        if machine_id and active_sessions[clean_key] != machine_id:
             return jsonify({"active": False, "message": "Concurrent Access", "code": "CONCURRENT_ACCESS"}), 409
    else:
        if machine_id: active_sessions[clean_key] = machine_id
        
    plan = main_res["plan"]
    current_cycle = main_res["current_cycle"]
    base_limit = 10000 if plan == "premium" else (5000 if plan == "standard" else 0)
    
    bonus_limit = 0
    valid_addons = 0
    
    for ak in addon_keys:
        ak = ak.strip()
        if not ak: continue
        ak_res = verify_gumroad(ak)
        if ak_res["valid"] and ak_res["days_diff"] <= 30:
            bonus = 10000 if ak_res["plan"] == "premium" else 5000
            bonus_limit += bonus
            valid_addons += 1

    return jsonify({"active": True, "plan": plan, "current_cycle": current_cycle, "base_limit": base_limit, "bonus_limit": bonus_limit, "valid_addons": valid_addons})

@app.route('/credits', methods=['POST'])
def check_credits():
    plan = request.json.get("plan", "free")
    credits = 10000 if plan == "premium" else (5000 if plan == "standard" else 0)
    return jsonify({"remaining": credits})

def handle_ai_error(res, provider):
    err_text = res.text.lower()
    if any(x in err_text for x in ["quota", "exceeded", "insufficient", "limit", "unusual activity", "balance", "payment"]):
        alert_admin(provider, res.text)
    return jsonify({"error": res.text}), res.status_code

@app.route('/ai/generate', methods=['POST'])
def ai_generate():
    if not GROQ_KEY: return jsonify({"error": "Server missing Groq Key"}), 500
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    response = requests.post(url, headers=headers, json=request.json)
    if response.status_code != 200: return handle_ai_error(response, "Groq AI (Texto)")
    return jsonify(response.json()), response.status_code

@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    if not GROQ_KEY: return jsonify({"error": "Server missing Groq Key"}), 500
    if 'file' not in request.files: return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {GROQ_KEY}"}
    files = {"file": (file.filename, file.read(), "audio/mpeg")}
    data = {"model": "whisper-large-v3", "language": "en", "prompt": "Damn, fuck, shit, bitch, motherfucker, cunt, asshole, crap, hell."}
    response = requests.post(url, headers=headers, files=files, data=data)
    if response.status_code != 200: return handle_ai_error(response, "Groq Whisper (Áudio)")
    return jsonify(response.json()), response.status_code

@app.route('/translate/deepl', methods=['POST'])
def translate_deepl():
    if not DEEPL_KEY: return jsonify({"error": "Server missing DeepL Key"}), 500
    text = request.json.get("text", "")
    url = "https://api-free.deepl.com/v2/translate"
    data = {'auth_key': DEEPL_KEY, 'text': text, 'source_lang': 'EN', 'target_lang': 'PT'}
    response = requests.post(url, data=data)
    if response.status_code != 200: return handle_ai_error(response, "DeepL Translator")
    return jsonify(response.json()), response.status_code

def safe_tts_error(res, provider):
    try: err = res.json()
    except: err = {"error": res.text}
    
    err_str = str(err).lower()
    if any(x in err_str for x in ["quota", "exceeded", "insufficient", "limit", "unusual activity", "balance", "payment"]):
        alert_admin(provider, str(err))
        
    return jsonify(err), res.status_code

@app.route('/tts/generate', methods=['POST'])
def tts_generate():
    data = request.json
    text = data.get("text", "")
    provider = data.get("provider", "").lower()
    voice_id = data.get("voice_id", "")

    try:
        if provider == "azure":
            safe_text = re.sub(r'\[.*?\]', '', text).replace("&", "and")
            url = f"https://{AZURE_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
            headers = {"Ocp-Apim-Subscription-Key": AZURE_KEY, "Content-Type": "application/ssml+xml", "X-Microsoft-OutputFormat": "audio-16khz-32kbitrate-mono-mp3", "User-Agent": "AnkiProServer"}
            locale = "-".join(voice_id.split("-")[:2]) if "-" in voice_id else "en-US"
            if "<mstts:express-as" in safe_text: body = f"<speak version='1.0' xml:lang='{locale}'><voice xml:lang='{locale}' name='{voice_id}'>{safe_text}</voice></speak>"
            else: body = f"<speak version='1.0' xml:lang='{locale}'><voice name='{voice_id}'>{safe_text}</voice></speak>"
            res = requests.post(url, headers=headers, data=body.encode('utf-8'))
            if res.status_code == 200: return Response(res.content, mimetype="audio/mpeg")
            else: return safe_tts_error(res, "Azure TTS")

        elif provider in ["elevenlabs", "elevenlabs2"]:
            key_to_use = ELEVEN_KEY_2 if provider == "elevenlabs2" else ELEVEN_KEY
            if not key_to_use: return jsonify({"error": f"Server missing Key for {provider}"}), 500
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            headers = {"xi-api-key": key_to_use, "Content-Type": "application/json"}
            payload = {"text": text, "model_id": "eleven_multilingual_v2"}
            res = requests.post(url, json=payload, headers=headers)
            if res.status_code == 200: return Response(res.content, mimetype="audio/mpeg")
            else: return safe_tts_error(res, provider.upper())

        elif provider == "cartesia":
            if not CARTESIA_KEY: return jsonify({"error": "Server missing Cartesia Key"}), 500
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
            payload = {"model_id": "sonic-english", "transcript": clean_transcript, "voice": {"mode": "id", "id": voice_id}, "output_format": {"container": "mp3", "encoding": "mp3", "sample_rate": 44100}}
            if emo_api: payload["voice"]["__experimental_controls"] = {"emotion": [f"{emo_api}:high"]}
            res = requests.post(url, headers=headers, json=payload)
            if res.status_code == 200: return Response(res.content, mimetype="audio/mpeg")
            else: return safe_tts_error(res, "Cartesia")

        elif provider == "playht":
            url = "https://api.play.ht/api/v2/tts/stream"
            headers = {"AUTHORIZATION": PLAYHT_KEY, "X-USER-ID": PLAYHT_USER, "accept": "audio/mpeg", "content-type": "application/json"}
            payload = {"text": text, "voice": voice_id, "output_format": "mp3"}
            res = requests.post(url, headers=headers, json=payload)
            if res.status_code == 200: return Response(res.content, mimetype="audio/mpeg")
            else: return safe_tts_error(res, "PlayHT")

        elif provider == "wellsaid":
            url = "https://api.wellsaidlabs.com/v1/tts/stream"
            headers = {"X-Api-Key": WELLSAID_KEY, "Accept": "audio/mpeg", "Content-Type": "application/json"}
            payload = {"text": text, "speaker_avatar_id": voice_id}
            res = requests.post(url, headers=headers, json=payload)
            if res.status_code == 200: return Response(res.content, mimetype="audio/mpeg")
            else: return safe_tts_error(res, "WellSaid Labs")

        elif provider == "coquixtts":
            url = f"https://api-inference.huggingface.co/models/{voice_id}"
            headers = {"Authorization": f"Bearer {HF_KEY}", "Content-Type": "application/json"}
            res = requests.post(url, headers=headers, json={"inputs": text}, timeout=25)
            if res.status_code == 200: return Response(res.content, mimetype="audio/wav")
            else: return safe_tts_error(res, "Coqui (HuggingFace)")
            
        return jsonify({"error": f"Provider {provider} failed or invalid."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)


