from flask import Flask, request, jsonify
import os
import traceback

app = Flask(__name__)

# --- VARIABLES DE ENTORNO ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "Iberconsulting_Token_Seguro_2026")

# --- INICIALIZACIÓN SEGURA DE SUPABASE ---
supabase = None
try:
    if SUPABASE_URL and SUPABASE_KEY:
        from supabase import create_client, Client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabase conectado correctamente.")
except Exception as e:
    print(f"Error crítico al conectar con Supabase: {e}")

# --- RUTA PRINCIPAL (Para que Vercel no marque error) ---
@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "estado": "activo",
        "mensaje": "Servidor ETL de Iberconsulting funcionando 24/7",
        "supabase_configurado": supabase is not None
    }), 200

# --- RUTA DEL WEBHOOK DE META ---
@app.route('/webhook', methods=['GET', 'POST'])
def meta_webhook():
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')

        if mode == 'subscribe' and token == VERIFY_TOKEN:
            return challenge, 200
        else:
            return 'Token de verificación inválido', 403

    if request.method == 'POST':
        data = request.json
        try:
            for entry in data.get('entry', []):
                for change in entry.get('changes', []):
                    value = change.get('value', {})
                    leadgen_id = value.get('leadgen_id')
                    if leadgen_id:
                        print(f"Nuevo Lead recibido: {leadgen_id}")
                        # Aquí irá la lógica de cruce más adelante
            return jsonify({"status": "success"}), 200
        except Exception as e:
            error_trace = traceback.format_exc()
            print(f"Error: {error_trace}")
            return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000)
