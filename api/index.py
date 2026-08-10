from flask import Flask, jsonify
import os
import requests
import traceback

app = Flask(__name__)

# --- VARIABLES DE ENTORNO ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
META_TOKEN = os.environ.get("META_TOKEN")
META_AD_ACCOUNT_ID = os.environ.get("META_AD_ACCOUNT_ID")
GHL_TOKEN = os.environ.get("GHL_TOKEN")
GHL_LOCATION_ID = os.environ.get("GHL_LOCATION_ID")

# --- CONEXIÓN A SUPABASE ---
supabase = None
try:
    if SUPABASE_URL and SUPABASE_KEY:
        from supabase import create_client, Client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"Error conectando a Supabase: {e}")

@app.route('/', methods=['GET'])
def home():
    return jsonify({"estado": "activo", "tipo": "Servidor ETL Auditor - Iberconsulting"})

@app.route('/auditoria', methods=['GET'])
def auditar_leads():
    try:
        # 1. LLAMADA A META ADS (Leads de hoy)
        act_id = f"act_{META_AD_ACCOUNT_ID}"
        meta_url = f"https://graph.facebook.com/v19.0/{act_id}/insights"
        meta_params = {
            "fields": "actions,spend",
            "date_preset": "today",
            "access_token": META_TOKEN
        }
        meta_response = requests.get(meta_url, params=meta_params).json()
        
        meta_leads = 0
        meta_spend = 0.0
        
        if "data" in meta_response and len(meta_response["data"]) > 0:
            data = meta_response["data"][0]
            meta_spend = float(data.get("spend", 0))
            # Buscar la acción específica de 'lead'
            for action in data.get("actions", []):
                if action.get("action_type") == "lead":
                    meta_leads = int(action.get("value", 0))

        # 2. LLAMADA A GOHIGHLEVEL (Contactos creados hoy)
        # Nota: La URL usa v2 de LeadConnector
        ghl_url = "https://services.leadconnectorhq.com/contacts/"
        ghl_headers = {
            "Authorization": f"Bearer {GHL_TOKEN}",
            "Version": "2021-07-28",
            "Accept": "application/json"
        }
        ghl_params = {
            "locationId": GHL_LOCATION_ID,
            "limit": 100
        }
        ghl_response = requests.get(ghl_url, headers=ghl_headers, params=ghl_params).json()
        
        ghl_total_contactos = len(ghl_response.get("contacts", []))
        
        # 3. CONSOLIDACIÓN DE DATOS
        reporte = {
            "fecha": "hoy",
            "meta_inversion": meta_spend,
            "meta_leads_generados": meta_leads,
            "ghl_contactos_totales": ghl_total_contactos,
            "fuga_leads": meta_leads - ghl_total_contactos,
            "cpa_estimado": round(meta_spend / meta_leads, 2) if meta_leads > 0 else 0
        }
        
        # Opcional: Guardar en Supabase automáticamente
        if supabase:
            supabase.table("reportes_diarios").insert(reporte).execute()

        return jsonify({"status": "éxito", "data": reporte}), 200

    except Exception as e:
        error_trace = traceback.format_exc()
        return jsonify({"status": "error", "mensaje": str(e), "trace": error_trace}), 500

if __name__ == '__main__':
    app.run(port=5000)
