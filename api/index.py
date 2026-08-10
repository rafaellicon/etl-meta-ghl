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
    return jsonify({"estado": "activo", "tipo": "Servidor ETL Auditor - Iberconsulting", "dashboard_url": "/dashboard"}), 200

# 1. RUTA DE DATOS (El motor trasero)
@app.route('/api/datos', methods=['GET'])
def obtener_datos():
    try:
        # LLAMADA A META ADS (Filtrando por objetivo de campaña)
        act_id = f"act_{META_AD_ACCOUNT_ID}"
        meta_url = f"https://graph.facebook.com/v19.0/{act_id}/insights"
        meta_params = {
            "level": "campaign",
            "fields": "campaign_name,objective,actions,spend",
            "date_preset": "last_30d",
            "access_token": META_TOKEN
        }
        meta_response = requests.get(meta_url, params=meta_params).json()
        
        meta_leads = 0
        meta_spend = 0.0
        
        # Filtramos solo las campañas de clientes potenciales
        for campaign in meta_response.get("data", []):
            objective = campaign.get("objective", "").upper()
            if objective in ["LEAD_GENERATION", "OUTCOME_LEADS"]:
                meta_spend += float(campaign.get("spend", 0))
                for action in campaign.get("actions", []):
                    if action.get("action_type") == "lead":
                        meta_leads += int(action.get("value", 0))

        # LLAMADA A GOHIGHLEVEL (Con paginación y búsqueda flexible de etiquetas)
        ghl_url = "https://services.leadconnectorhq.com/contacts/"
        ghl_headers = {
            "Authorization": f"Bearer {GHL_TOKEN}", 
            "Version": "2021-07-28", 
            "Accept": "application/json"
        }
        ghl_params = {"locationId": GHL_LOCATION_ID, "limit": 100}
        
        ghl_leads_meta = 0
        ghl_pagos_info = 0
        
        # Leemos hasta 10 páginas (1000 contactos recientes) para asegurar que escaneamos todo
        for _ in range(10):
            ghl_response = requests.get(ghl_url, headers=ghl_headers, params=ghl_params).json()
            
            for contacto in ghl_response.get("contacts", []):
                # Limpiamos las etiquetas (minúsculas y sin espacios extra en los bordes)
                tags = [tag.lower().strip() for tag in contacto.get("tags", [])]
                
                # Buscamos si ALGUNA etiqueta contiene la palabra clave
                tiene_meta = any("meta" in t for t in tags)
                tiene_pago = any("pago info" in t for t in tags)

                if tiene_meta:
                    ghl_leads_meta += 1
                    if tiene_pago:
                        ghl_pagos_info += 1
            
            # Paginación: Si hay más contactos, GHL nos da la URL de la siguiente página
            meta_data = ghl_response.get("meta", {})
            next_url = meta_data.get("nextPageUrl")
            if next_url:
                ghl_url = next_url
                ghl_params = {} # La URL nueva ya trae los parámetros incrustados
            else:
                break
        
        # EL REPORTE FINAL AUDITADO
        reporte = {
            "inversion": round(meta_spend, 2),
            "leads_meta": meta_leads,
            "leads_ghl": ghl_leads_meta,
            "fuga": meta_leads - ghl_leads_meta,
            "pagos": ghl_pagos_info,
            "cpa": round(meta_spend / ghl_pagos_info, 2) if ghl_pagos_info > 0 else 0
        }

        return jsonify({"status": "éxito", "reporte": reporte}), 200

    except Exception as e:
        error_trace = traceback.format_exc()
        return jsonify({"status": "error", "mensaje": str(e), "trace": error_trace}), 500

# 2. RUTA DEL DASHBOARD (La interfaz visual)
@app.route('/dashboard', methods=['GET'])
def dashboard():
    html = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dashboard Directivo | Iberconsulting</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Inter', sans-serif; background-color: #0B1120; color: #F8FAFC; }
            .glass-panel { background: rgba(30, 41, 59, 0.4); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 1rem; box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1); }
            .text-gradient { background: linear-gradient(to right, #38BDF8, #818CF8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
            .text-gradient-danger { background: linear-gradient(to right, #F87171, #FB923C); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
            .text-gradient-success { background: linear-gradient(to right, #34D399, #3B82F6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        </style>
    </head>
    <body class="min-h-screen p-6 md:p-12">
        <div class="max-w-7xl mx-auto">
            
            <header class="flex flex-col md:flex-row justify-between items-center mb-12">
                <div>
                    <h1 class="text-3xl md:text-4xl font-bold tracking-tight">Rendimiento <span class="text-gradient">España Te Homologa</span></h1>
                    <p class="text-slate-400 mt-2">Auditoría en tiempo real (Meta Ads vs GoHighLevel) - Últimos 30 días</p>
                </div>
                <button onclick="cargarDatos()" id="btn-actualizar" class="mt-4 md:mt-0 bg-blue-600 hover:bg-blue-500 text-white font-semibold py-2 px-6 rounded-lg transition-all shadow-[0_0_15px_rgba(37,99,235,0.4)] flex items-center gap-2">
                    <svg id="spinner" class="animate-spin h-5 w-5 hidden" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                    <span>Actualizar Datos</span>
                </button>
            </header>

            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                <div class="glass-panel p-6 flex flex-col justify-between">
                    <h3 class="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-2">Inversión (C. Potenciales)</h3>
                    <div class="text-5xl font-bold text-gradient mt-2" id="val-inversion">€0.00</div>
                </div>
                <div class="glass-panel p-6 flex flex-col justify-between">
                    <h3 class="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-2">Leads Registrados (Meta)</h3>
                    <div class="text-5xl font-bold text-white mt-2" id="val-leads-meta">0</div>
                </div>
                <div class="glass-panel p-6 flex flex-col justify-between border-t-4 border-t-emerald-500">
                    <h3 class="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-2">Leads Reales (CRM GHL)</h3>
                    <div class="text-5xl font-bold text-gradient-success mt-2" id="val-leads-ghl">0</div>
                </div>
                <div class="glass-panel p-6 flex flex-col justify-between border-t-4 border-t-rose-500">
                    <h3 class="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-2">Fuga de Leads</h3>
                    <div class="text-5xl font-bold text-gradient-danger mt-2" id="val-fuga">0</div>
                    <p class="text-xs text-slate-500 mt-2">Leads cobrados pero no ingresados al CRM</p>
                </div>
                <div class="glass-panel p-6 flex flex-col justify-between">
                    <h3 class="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-2">Asesorías Pagadas</h3>
                    <div class="text-5xl font-bold text-white mt-2" id="val-pagos">0</div>
                    <p class="text-xs text-slate-500 mt-2">Etiqueta "pago info" detectada</p>
                </div>
                <div class="glass-panel p-6 flex flex-col justify-between">
                    <h3 class="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-2">Costo por Asesoría (CPA)</h3>
                    <div class="text-5xl font-bold text-gradient mt-2" id="val-cpa">€0.00</div>
                    <p class="text-xs text-slate-500 mt-2">Inversión Meta / Asesorías Pagadas</p>
                </div>
            </div>
        </div>

        <script>
            async function cargarDatos() {
                const btn = document.getElementById('btn-actualizar');
                const spinner = document.getElementById('spinner');
                
                btn.disabled = true;
                spinner.classList.remove('hidden');
                btn.querySelector('span').innerText = 'Conectando APIs...';

                try {
                    const response = await fetch('/api/datos');
                    const data = await response.json();
                    
                    if(data.status === 'éxito') {
                        document.getElementById('val-inversion').innerText = '€' + data.reporte.inversion.toFixed(2);
                        document.getElementById('val-leads-meta').innerText = data.reporte.leads_meta;
                        document.getElementById('val-leads-ghl').innerText = data.reporte.leads_ghl;
                        document.getElementById('val-fuga').innerText = data.reporte.fuga;
                        document.getElementById('val-pagos').innerText = data.reporte.pagos;
                        document.getElementById('val-cpa').innerText = '€' + data.reporte.cpa.toFixed(2);
                    } else {
                        alert("Error al cruzar datos: " + data.mensaje);
                    }
                } catch (error) {
                    alert("Error de conexión con el servidor.");
                }

                btn.disabled = false;
                spinner.classList.add('hidden');
                btn.querySelector('span').innerText = 'Actualizar Datos';
            }

            window.onload = cargarDatos;
        </script>
    </body>
    </html>
    """
    return html, 200

if __name__ == '__main__':
    app.run(port=5000)
