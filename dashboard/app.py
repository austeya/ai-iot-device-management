from flask import Flask, jsonify, request
import threading, os, json, time, sqlite3
from pathlib import Path
import paho.mqtt.client as mqtt

# AI model
import os, sys
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
import os, sys
sys.path.append("/app")
from src.ai_model import AIModel

app = Flask(__name__)

MQTT_BROKER = os.getenv("MQTT_BROKER", "broker")
IOT_TOPIC   = os.getenv("IOT_TOPIC", "iot/devices/sensor")

# ---------------- SQLite setup ----------------
DB_PATH = os.getenv("DB_PATH", "/app/data/iot.db")
Path(os.path.dirname(DB_PATH)).mkdir(parents=True, exist_ok=True)

_db = sqlite3.connect(DB_PATH, check_same_thread=False)
_db.execute("""
CREATE TABLE IF NOT EXISTS readings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  device_id TEXT,
  temperature REAL,
  humidity REAL,
  is_anomaly INTEGER
)
""")
_db.commit()
_db_lock = threading.Lock()

def _to_float(x):
    try: return float(x)
    except Exception: return None

def db_insert(row: dict):
    try:
        with _db_lock:
            _db.execute(
                "INSERT INTO readings(ts, device_id, temperature, humidity, is_anomaly) VALUES (?,?,?,?,?)",
                (
                    row.get("_ts"),
                    row.get("device_id"),
                    _to_float(row.get("temperature")),
                    _to_float(row.get("humidity")),
                    (1 if row.get("is_anomaly") is True else 0 if row.get("is_anomaly") is False else None),
                )
            )
            _db.commit()
    except Exception as e:
        print("DB insert error:", e)

def db_select_recent(limit: int, device_id: str | None):
    sql = ("SELECT ts, device_id, temperature, humidity, is_anomaly "
           "FROM readings ")
    args = []
    if device_id:
        sql += "WHERE device_id = ? "
        args.append(device_id)
    sql += "ORDER BY id DESC LIMIT ?"
    args.append(limit)

    with _db_lock:
        rows = _db.execute(sql, tuple(args)).fetchall()

    rows.reverse()  # oldest → newest
    out = []
    for ts, dev, temp, hum, anom in rows:
        out.append({
            "_ts": ts,
            "device_id": dev,
            "temperature": temp,
            "humidity": hum,
            "is_anomaly": (bool(anom) if anom in (0,1) else None),
        })
    return out

def db_distinct_devices():
    with _db_lock:
        rows = _db.execute("SELECT DISTINCT device_id FROM readings WHERE device_id IS NOT NULL ORDER BY device_id").fetchall()
    return [r[0] for r in rows if r[0]]
# ----------------------------------------------

latest = {"status": "waiting for data..."}

# ---- AI model bootstrap ----
model = AIModel()
try:
    model.load_model()
except Exception:
    model.train([x / 10.0 for x in range(180, 281)])  # 18.0..28.0 as "normal"
# --------------------------------

def on_connect(client, userdata, flags, rc):
    print(f"🔗 Dashboard MQTT connected rc={rc}, subscribing to {IOT_TOPIC}")
    client.subscribe(IOT_TOPIC)

def on_message(client, userdata, msg):
    global latest
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except Exception:
        payload = {"raw": msg.payload.decode("utf-8", errors="ignore")}

    payload["_ts"] = time.strftime("%Y-%m-%d %H:%M:%S")

    # anomaly detection on temperature if present
    try:
        t = float(payload.get("temperature", "nan"))
        payload["is_anomaly"] = (bool(model.predict(t)) if t == t else None)
    except Exception as e:
        print("AI predict error:", e)
        payload["is_anomaly"] = None

    latest = payload
    db_insert(payload)  # 💾 persist each reading
    print("📥 Dashboard received:", payload)

def mqtt_thread():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    for attempt in range(1, 11):
        try:
            print(f"🔌 Dashboard connecting to MQTT broker: {MQTT_BROKER} (attempt {attempt})")
            client.connect(MQTT_BROKER, 1883, 60)
            break
        except Exception as e:
            print("⚠️ Dashboard connect failed:", e, "retrying…")
            time.sleep(2)
    client.loop_forever()

# ---------------- API routes ----------------

@app.get("/api/latest")
def api_latest():
    return jsonify(latest)

@app.get("/api/history")
def api_history():
    """Return recent rows. Optional query params:
       - limit (int, default 240, max 2000)
       - device_id (optional filter)
    """
    try:
        limit = int(request.args.get("limit", 240))
        limit = max(1, min(limit, 2000))
    except Exception:
        limit = 240
    device_id = request.args.get("device_id")
    rows = db_select_recent(limit, device_id)
    return jsonify(rows)

@app.get("/api/devices")
def api_devices():
    return jsonify(db_distinct_devices())

# --------------- Page with charts & filter ---------------
@app.get("/")
def index():
    return """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8"/>
    <title>AI IoT Dashboard</title>
    <style>
      :root { color-scheme: light dark; }
      body { font-family: system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,sans-serif; margin:2rem; background:#fafafa; }
      .wrap{ display:grid; gap:1rem; grid-template-columns: 1fr; max-width: 1100px; }
      .row { display:flex; align-items:center; gap:.75rem; }
      .card { padding:1rem 1.25rem; border:1px solid #ccc; border-radius:12px; background:#fff; }
      .pill { display:inline-block; padding:.35rem .7rem; border-radius:999px; font-weight:700; }
      .ok { background:#22c55e; color:#fff; border:1px solid #16a34a; }
      .bad{ background:#ef4444; color:#fff; border:1px solid #dc2626; }
      .none{background:#e5e7eb; color:#374151; border:1px solid #d1d5db; }
      .k { color:#666; min-width: 120px; } .v { font-weight:600; }
      .charts{ display:grid; grid-template-columns: 1fr 1fr; gap:1rem; }
      canvas{ width:100%; height:280px; border:1px solid #ddd; border-radius:10px; background:#fff; }
      label{ font-size:.95rem; color:#333; }
      select{ padding:.4rem .6rem; border-radius:8px; border:1px solid #cbd5e1; }
      small { color:#6b7280; }
      #raw { display:block; margin-top:.5rem; font-family:monospace; font-size:.85rem; }
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="row">
        <h1 style="margin:0;">AI-Powered IoT Dashboard</h1>
        <span id="badge" class="pill none">—</span>
        <div style="margin-left:auto" class="row">
          <label for="deviceSel">Device:</label>
          <select id="deviceSel"><option value="">All</option></select>
        </div>
      </div>

      <div class="card" id="card">
        <div class="row"><span class="k">Device:</span> <span class="v" id="device">—</span></div>
        <div class="row"><span class="k">Temperature:</span> <span class="v" id="temp">—</span> °C</div>
        <div class="row"><span class="k">Humidity:</span> <span class="v" id="hum">—</span> %</div>
        <div class="row"><span class="k">Timestamp:</span> <span class="v" id="ts">—</span></div>
        <small id="raw"></small>
      </div>

      <div class="charts">
        <canvas id="tempChart" width="520" height="280"></canvas>
        <canvas id="humChart"  width="520" height="280"></canvas>
      </div>
    </div>

    <script>
      const sel = document.getElementById('deviceSel');
      const badge = document.getElementById('badge');
      const card = document.getElementById('card');

      function setBadge(anom){
        if(anom===true){ badge.className='pill bad'; badge.textContent='ANOMALY'; card.style.background='#fee2e2'; card.style.borderColor='#ef4444'; }
        else if(anom===false){ badge.className='pill ok'; badge.textContent='Normal'; card.style.background='#dcfce7'; card.style.borderColor='#22c55e'; }
        else { badge.className='pill none'; badge.textContent='—'; card.style.background='#fff'; card.style.borderColor='#ccc'; }
      }

      async function loadDevices(){
        try{
          const r = await fetch('/api/devices', {cache:'no-store'});
          const arr = await r.json();
          const cur = sel.value;
          sel.innerHTML = '<option value="">All</option>' + arr.map(d => `<option value="${d}">${d}</option>`).join('');
          if (cur && [...sel.options].some(o => o.value===cur)) sel.value = cur;
        }catch(e){ console.error(e); }
      }

      async function refreshLatest(){
        try{
          const r = await fetch('/api/latest', {cache:'no-store'});
          const d = await r.json();
          document.getElementById('device').textContent = d.device_id ?? '—';
          document.getElementById('temp').textContent   = d.temperature ?? '—';
          document.getElementById('hum').textContent    = d.humidity ?? '—';
          document.getElementById('ts').textContent     = d._ts ?? '—';
          document.getElementById('raw').textContent    = JSON.stringify(d);
          setBadge(d.is_anomaly);
        }catch(e){ console.error(e); }
      }

      function drawSeries(ctx, points, yLabel){
        // clear
        ctx.clearRect(0,0,ctx.canvas.width, ctx.canvas.height);
        const W = ctx.canvas.width, H = ctx.canvas.height;
        const pad = 36, left=50, right=W-12, top=12, bottom=H-28;

        // extract y values
        const ys = points.map(p => p.y);
        const minY = Math.min(...ys, 0);
        const maxY = Math.max(...ys, 1);
        const spanY = (maxY - minY) || 1;

        // grid
        ctx.strokeStyle = '#e5e7eb'; ctx.lineWidth = 1;
        for(let i=0;i<5;i++){
          const y = top + (bottom-top)*i/4;
          ctx.beginPath(); ctx.moveTo(left,y); ctx.lineTo(right,y); ctx.stroke();
        }

        // axes labels
        ctx.fillStyle='#374151'; ctx.font='12px system-ui';
        ctx.fillText(yLabel, 6, 14);
        ctx.fillText(maxY.toFixed(1), 6, top+10);
        ctx.fillText(minY.toFixed(1), 6, bottom);

        // line
        ctx.strokeStyle = '#2563eb'; ctx.lineWidth = 2; ctx.beginPath();
        points.forEach((p, i) => {
          const x = left + (right-left) * (i/(points.length-1 || 1));
          const y = bottom - ( (p.y - minY) / spanY ) * (bottom-top);
          if(i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
        });
        ctx.stroke();

        // anomaly dots
        points.forEach((p,i)=>{
          if(p.anom===true){
            const x = left + (right-left) * (i/(points.length-1 || 1));
            const y = bottom - ( (p.y - minY) / spanY ) * (bottom-top);
            ctx.beginPath(); ctx.arc(x,y,3,0,Math.PI*2);
            ctx.fillStyle='#dc2626'; ctx.fill();
          }
        });
      }

      async function refreshCharts(){
        try{
          const device = sel.value || '';
          const r = await fetch(`/api/history?limit=240${device?`&device_id=${encodeURIComponent(device)}`:''}`, {cache:'no-store'});
          const rows = await r.json();

          const tempPts = rows.map(r => ({ y: (r.temperature ?? 0), anom: r.is_anomaly }));
          const humPts  = rows.map(r => ({ y: (r.humidity ?? 0), anom: r.is_anomaly }));

          drawSeries(document.getElementById('tempChart').getContext('2d'), tempPts, 'Temperature (°C)');
          drawSeries(document.getElementById('humChart').getContext('2d'),  humPts,  'Humidity (%)');
        }catch(e){ console.error(e); }
      }

      // Init
      loadDevices();
      refreshLatest();
      refreshCharts();

      // Live updates
      setInterval(refreshLatest, 1500);
      setInterval(refreshCharts, 3000);
      setInterval(loadDevices, 7000);

      sel.addEventListener('change', ()=> { refreshCharts(); });
    </script>
  </body>
</html>
"""
# ------------------------------------------------------

if __name__ == "__main__":
    threading.Thread(target=mqtt_thread, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)