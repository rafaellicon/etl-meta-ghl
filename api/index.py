from flask import Flask, jsonify
import os
import requests
import traceback
import time

app = Flask(__name__)

# --- VARIABLES DE ENTORNO ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
META_TOKEN = os.environ.get("META_TOKEN")
META_AD_ACCOUNT_ID = os.environ.get("META_AD_ACCOUNT_ID")
GHL_TOKEN = os.environ.get("GHL_TOKEN")
GHL_LOCATION_ID = os.environ.get("GHL_LOCATION_ID")

# --- SISTEMA DE CACHÉ EN MEMORIA ---
# Evita saturar las APIs y hace que el dashboard cargue al instante
CACHE = {
    "timestamp": 0,
    "data": None,
    "ttl": 900 # 15 minutos de vida útil (900 segundos)
}

@app.route('/', methods=['GET'])
def home():
    return jsonify({"estado": "activo", "tipo": "Servidor BI - Iberconsulting", "dashboard_url": "/dashboard"}), 200

# 1. RUTA DE DATOS (El motor trasero con Caché)
@app.route('/api/datos', methods=['GET'])
def obtener_datos():
    global CACHE
    
    # Comprobar si la caché es válida
    if time.time() - CACHE["timestamp"] < CACHE["ttl"] and CACHE["data"] is not None:
        return jsonify({"status": "éxito (caché)", "reporte": CACHE["data"]}), 200

    try:
        # LLAMADA A META ADS (Desglose por campaña)
        act_id = f"act_{META_AD_ACCOUNT_ID}"
        meta_url = f"https://graph.facebook.com/v19.0/{act_id}/insights"
        meta_params = {
            "level": "campaign",
            "fields": "campaign_name,objective,actions,spend",
            "date_preset": "last_30d",
            "access_token": META_TOKEN
        }
        meta_response = requests.get(meta_url, params=meta_params).json()
        
        meta_leads_totales = 0
        meta_spend_total = 0.0
        campanas_meta = []
        
        for campaign in meta_response.get("data", []):
            objective = campaign.get("objective", "").upper()
            if objective in ["LEAD_GENERATION", "OUTCOME_LEADS"]:
                spend = float(campaign.get("spend", 0))
                leads = 0
                for action in campaign.get("actions", []):
                    if action.get("action_type") == "lead":
                        leads = int(action.get("value", 0))
                
                meta_spend_total += spend
                meta_leads_totales += leads
                
                campanas_meta.append({
                    "nombre": campaign.get("campaign_name", "Desconocida"),
                    "inversion": spend,
                    "leads": leads,
                    "cpl": round(spend / leads, 2) if leads > 0 else 0
                })

        # LLAMADA A GOHIGHLEVEL (Con detalle de leads)
        ghl_url = "https://services.leadconnectorhq.com/contacts/"
        ghl_headers = {
            "Authorization": f"Bearer {GHL_TOKEN}", 
            "Version": "2021-07-28", 
            "Accept": "application/json"
        }
        ghl_params = {"locationId": GHL_LOCATION_ID, "limit": 100}
        
        ghl_leads_meta = 0
        ghl_pagos_info = 0
        leads_detallados = []
        
        for _ in range(10): # Paginación
            ghl_response = requests.get(ghl_url, headers=ghl_headers, params=ghl_params).json()
            
            for contacto in ghl_response.get("contacts", []):
                tags = [tag.lower().strip() for tag in contacto.get("tags", [])]
                
                tiene_meta = any("meta" in t for t in tags)
                tiene_pago = any("pago info" in t for t in tags)

                if tiene_meta:
                    ghl_leads_meta += 1
                    estado = "Pagado" if tiene_pago else "Pendiente"
                    
                    if tiene_pago:
                        ghl_pagos_info += 1
                        
                    # Recolectar datos para la tabla detallada
                    leads_detallados.append({
                        "nombre": contacto.get("contactName", "Sin Nombre"),
                        "email": contacto.get("email", "Sin Email"),
                        "origen": contacto.get("source", "Desconocido"),
                        "estado": estado,
                        "creado": contacto.get("dateAdded", "")[:10] # Solo YYYY-MM-DD
                    })
            
            next_url = ghl_response.get("meta", {}).get("nextPageUrl")
            if next_url:
                ghl_url = next_url
                ghl_params = {} 
            else:
                break
        
        # EL REPORTE FINAL AUDITADO
        reporte = {
            "resumen": {
                "inversion": round(meta_spend_total, 2),
                "leads_meta": meta_leads_totales,
                "leads_ghl": ghl_leads_meta,
                "fuga": meta_leads_totales - ghl_leads_meta,
                "pagos": ghl_pagos_info,
                "cpa": round(meta_spend_total / ghl_pagos_info, 2) if ghl_pagos_info > 0 else 0
            },
            "campanas": campanas_meta,
            "leads": leads_detallados[:50] # Limitamos a los últimos 50 para no saturar la vista
        }

        # Guardar en caché
        CACHE["timestamp"] = time.time()
        CACHE["data"] = reporte

        return jsonify({"status": "éxito", "reporte": reporte}), 200

    except Exception as e:
        error_trace = traceback.format_exc()
        return jsonify({"status": "error", "mensaje": str(e), "trace": error_trace}), 500

# 2. RUTA DEL DASHBOARD (La interfaz visual con Gráficos y Tablas)
@app.route('/dashboard', methods=['GET'])
def dashboard():
    html = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dashboard BI | Iberconsulting</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Inter', sans-serif; background-color: #0B1120; color: #F8FAFC; }
            .glass-panel { background: rgba(30, 41, 59, 0.4); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 1rem; box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1); }
            .text-gradient { background: linear-gradient(to right, #38BDF8, #818CF8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
            .text-gradient-success { background: linear-gradient(to right, #34D399, #3B82F6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
            ::-webkit-scrollbar { width: 8px; }
            ::-webkit-scrollbar-track { background: #0B1120; }
            ::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
        </style>
    </head>
    <body class="min-h-screen p-6 md:p-12">
        <div class="max-w-7xl mx-auto space-y-8">
            
            <!-- Encabezado -->
            <header class="flex flex-col md:flex-row justify-between items-center">
                <div>
                    <h1 class="text-3xl md:text-4xl font-bold tracking-tight">Inteligencia <span class="text-gradient">España Te Homologa</span></h1>
                    <p class="text-slate-400 mt-2">Caché activa (15 min) - Últimos 30 días</p>
                </div>
                <button onclick="cargarDatos(true)" id="btn-actualizar" class="mt-4 md:mt-0 bg-blue-600 hover:bg-blue-500 text-white font-semibold py-2 px-6 rounded-lg transition-all shadow-[0_0_15px_rgba(37,99,235,0.4)] flex items-center gap-2">
                    <span id="btn-text">Recargar Datos</span>
                </button>
            </header>

            <!-- KPIs Principales -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <div class="glass-panel p-6">
                    <h3 class="text-slate-400 text-xs font-bold uppercase tracking-wider">Inversión (Meta)</h3>
                    <div class="text-3xl font-bold text-gradient mt-2" id="val-inversion">€0.00</div>
                </div>
                <div class="glass-panel p-6 border-t-4 border-t-emerald-500">
                    <h3 class="text-slate-400 text-xs font-bold uppercase tracking-wider">Leads CRM / Pagos</h3>
                    <div class="text-3xl font-bold text-gradient-success mt-2"><span id="val-leads-ghl">0</span> / <span id="val-pagos">0</span></div>
                </div>
                <div class="glass-panel p-6">
                    <h3 class="text-slate-400 text-xs font-bold uppercase tracking-wider">Fuga de Leads</h3>
                    <div class="text-3xl font-bold text-rose-400 mt-2" id="val-fuga">0</div>
                </div>
                <div class="glass-panel p-6">
                    <h3 class="text-slate-400 text-xs font-bold uppercase tracking-wider">CPA (Costo X Asesoría)</h3>
                    <div class="text-3xl font-bold text-white mt-2" id="val-cpa">€0.00</div>
                </div>
            </div>

            <!-- Gráficos y Tablas -->
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
                
                <!-- Gráfico de Campañas -->
                <div class="glass-panel p-6 lg:col-span-2">
                    <h3 class="text-lg font-bold mb-4">Rendimiento por Campaña (Meta)</h3>
                    <canvas id="campaignChart" height="100"></canvas>
                </div>

                <!-- Lista de Leads Detallada -->
                <div class="glass-panel p-6 lg:col-span-1 max-h-[400px] overflow-y-auto">
                    <h3 class="text-lg font-bold mb-4">Últimos Leads Recibidos</h3>
                    <div class="space-y-4" id="leads-list">
                        <p class="text-slate-500 text-sm">Cargando leads...</p>
                    </div>
                </div>

            </div>
        </div>

        <script>
            let myChart = null;

            async function cargarDatos(force = false) {
                const btn = document.getElementById('btn-actualizar');
                btn.disabled = true;
                document.getElementById('btn-text').innerText = 'Procesando...';

                try {
                    // Si forzamos, podríamos enviar un parámetro para limpiar caché en el futuro
                    const response = await fetch('/api/datos');
                    const data = await response.json();
                    
                    if(data.status.includes('éxito')) {
                        const rep = data.reporte;
                        
                        // Actualizar KPIs
                        document.getElementById('val-inversion').innerText = '€' + rep.resumen.inversion.toFixed(2);
                        document.getElementById('val-leads-ghl').innerText = rep.resumen.leads_ghl;
                        document.getElementById('val-pagos').innerText = rep.resumen.pagos;
                        document.getElementById('val-fuga').innerText = rep.resumen.fuga;
                        document.getElementById('val-cpa').innerText = '€' + rep.resumen.cpa.toFixed(2);

                        // Actualizar Gráfico
                        renderChart(rep.campanas);

                        // Actualizar Lista de Leads
                        renderLeads(rep.leads);
                    } else {
                        alert("Error: " + data.mensaje);
                    }
                } catch (error) {
                    alert("Error de red al conectar.");
                }

                btn.disabled = false;
                document.getElementById('btn-text').innerText = 'Recargar Datos';
            }

            function renderChart(campanas) {
                const ctx = document.getElementById('campaignChart').getContext('2d');
                
                const labels = campanas.map(c => c.nombre.length > 20 ? c.nombre.substring(0,20)+'...' : c.nombre);
                const leads = campanas.map(c => c.leads);
                const inversion = campanas.map(c => c.inversion);

                if(myChart) myChart.destroy();

                myChart = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: labels,
                        datasets: [
                            {
                                label: 'Leads Generados',
                                data: leads,
                                backgroundColor: '#38BDF8',
                                borderRadius: 4,
                                yAxisID: 'y'
                            },
                            {
                                label: 'Inversión (€)',
                                data: inversion,
                                type: 'line',
                                borderColor: '#818CF8',
                                tension: 0.4,
                                yAxisID: 'y1'
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        interaction: { mode: 'index', intersect: false },
                        scales: {
                            y: { type: 'linear', display: true, position: 'left', grid: { color: 'rgba(255,255,255,0.05)' } },
                            y1: { type: 'linear', display: true, position: 'right', grid: { drawOnChartArea: false } }
                        },
                        plugins: { legend: { labels: { color: '#F8FAFC' } } }
                    }
                });
            }

            function renderLeads(leads) {
                const container = document.getElementById('leads-list');
                container.innerHTML = '';
                
                if(leads.length === 0) {
                    container.innerHTML = '<p class="text-sm text-slate-400">No se encontraron leads recientes.</p>';
                    return;
                }

                leads.forEach(lead => {
                    const color = lead.estado === 'Pagado' ? 'text-emerald-400' : 'text-slate-400';
                    const html = `
                        <div class="border-b border-slate-700/50 pb-3 last:border-0">
                            <div class="flex justify-between items-start">
                                <div>
                                    <p class="font-semibold text-sm">${lead.nombre}</p>
                                    <p class="text-xs text-slate-500">${lead.email}</p>
                                </div>
                                <span class="text-xs font-bold ${color}">${lead.estado}</span>
                            </div>
                            <div class="mt-1 flex justify-between">
                                <span class="text-[10px] uppercase text-slate-500">${lead.origen}</span>
                                <span class="text-[10px] text-slate-500">${lead.creado}</span>
                            </div>
                        </div>
                    `;
                    container.innerHTML += html;
                });
            }

            window.onload = () => cargarDatos(false);
        </script>
    </body>
    </html>
    """
    return html, 200

if __name__ == '__main__':
    app.run(port=5000)
