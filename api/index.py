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

@app.route('/', methods=['GET'])
def home():
    return jsonify({"estado": "activo", "tipo": "Servidor ETL Auditor - Iberconsulting"}), 200

@app.route('/auditoria', methods=['GET'])
def auditar_leads():
    try:
        # 1. LLAMADA A META ADS (Leads y gasto de hoy)
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
            for action in data.get("actions", []):
                if action.get("action_type") == "lead":
                    meta_leads = int(action.get("value", 0))

        # 2. LLAMADA A GOHIGHLEVEL (Buscando contactos con etiquetas)
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
        
        ghl_leads_meta = 0
        ghl_pagos_info = 0
        
        # Filtramos por las etiquetas que me comentaste
        for contacto in ghl_response.get("contacts", []):
            tags = [tag.lower() for tag in contacto.get("tags", [])]
            if "meta" in tags:
                ghl_leads_meta += 1
                if "pago info" in tags:
                    ghl_pagos_info += 1
        
        # 3. EL REPORTE FINAL AUDITADO
        reporte = {
            "1_inversion_meta": f"{meta_spend} EUR",
            "2_leads_cobrados_por_meta": meta_leads,
            "3_leads_reales_en_ghl": ghl_leads_meta,
            "4_fuga_de_leads": meta_leads - ghl_leads_meta,
            "5_pagos_de_info_exitosos": ghl_pagos_info,
            "6_costo_por_pago_info": round(meta_spend / ghl_pagos_info, 2) if ghl_pagos_info > 0 else 0
        }

        return jsonify({"status": "éxito", "reporte": reporte}), 200

    except Exception as e:
        error_trace = traceback.format_exc()
        return jsonify({"status": "error", "mensaje": str(e), "trace": error_trace}), 500

if __name__ == '__main__':
    app.run(port=5000)
