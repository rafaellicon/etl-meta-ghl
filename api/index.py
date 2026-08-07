from flask import Flask, request, jsonify
import os
from supabase import create_client, Client

app = Flask(__name__)

# --- VARIABLES DE ENTORNO (Se configuran en Vercel, NUNCA en el código) ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") # Usar la Secret Key de Supabase
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "Iberconsulting_Token_Seguro_2026") # Token inventado por ti para Meta

# Inicializar Supabase si las credenciales existen
if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    supabase = None

@app.route('/webhook', methods=['GET', 'POST'])
def meta_webhook():
    # 1. VERIFICACIÓN DE META (Método GET)
    # Meta hace un "ping" a esta URL cuando configuras el Webhook en el panel de desarrolladores.
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')

        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("¡Webhook verificado exitosamente por Meta!")
            return challenge, 200
        else:
            return 'Token de verificación inválido', 403

    # 2. RECEPCIÓN DE LEADS (Método POST)
    # Meta envía los datos en tiempo real cada vez que entra un formulario.
    if request.method == 'POST':
        data = request.json
        
        try:
            # Meta envía los datos anidados en listas, iteramos para extraerlos
            for entry in data.get('entry', []):
                for change in entry.get('changes', []):
                    value = change.get('value', {})
                    leadgen_id = value.get('leadgen_id')
                    
                    if leadgen_id:
                        print(f"¡Nuevo Lead recibido! ID en Meta: {leadgen_id}")
                        
                        # --- FASE 3: AQUÍ INTEGRAREMOS LA LÓGICA DE CRUCE ---
                        # A. Buscar el correo/teléfono usando el leadgen_id (API Meta)
                        # B. Buscar etiquetas de "pago info" en GHL (API GHL)
                        # C. Extraer Costo del Anuncio (API Meta)
                        # D. Insertar fila en Supabase
                        
            return jsonify({"status": "success"}), 200
            
        except Exception as e:
            print(f"Error procesando webhook: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

# Punto de entrada para ejecución local (opcional)
if __name__ == '__main__':
    app.run(port=5000)