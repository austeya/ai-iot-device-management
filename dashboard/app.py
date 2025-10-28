from flask import Flask, jsonify, request
import threading, os, json, time, sqlite3
from pathlib import Path
import paho.mqtt.client as mqtt

# AI model
from src.ai_model import AIModel

app = Flask(__name__)

MQTT_BROKER = os.getenv("MQTT_BROKER", "broker")
IOT_TOPIC   = os.getenv("IOT_TOPIC", "iot/devices/sensor")

# ---- SQLite setup ----
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

def db_insert(row):
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
                ),
            )
            _db.commit()
    except Exception as e:
        print("DB insert error:", e)

def db_select_recent(limit: int):
    with _db_lock:
        cur = _db.execute(
            "SELECT ts, device_id, temperature, humidity, is_anomaly "
            "FROM readings ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = cur.fetchall()
    rows.reverse()  # oldest -> newest
    out = []
    for ts, device_id, temperature, humidity, is_anomaly in rows:
        out.append({
            "_ts": ts,
            "device_id": device_id,
            "temperature": temperature,
            "humidity": humidity,
            "is_anomaly": (bool(is_anomaly) if is_anomaly in (0,1) else None)
        })
    return out
# ----------------------

latest = {"status": "waiting for data..."}

# ---- AI model bootstrap ----
model = AIModel()
try:
    model.load_model()
except Exception:
    model.train([x / 10.0 for x in range(180, 281)])  # 18.0..28.0 normal
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

    # anomaly detection
    try:
        t = float(payload.get("temperature", "nan"))
        payload["is_anomaly"] = (bool(model.predict(t)) if t == t else None)
    except Exception as e:
        print("AI predict error:", e)
        payload["is_anomaly"] = None

    latest = payload
    db_insert(payload)  # 💾 persist every reading
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

@app.get("/api/latest")
def api_latest():
    return jsonify(latest)

@app.get("/api/history")
def api_history():
    try:
        limit = int(request.args.get("limit", 120))
        limit = max(1, min(limit, 2000))
    except Exception:
        limit = 120
    rows = db_select_recent(limit)
    return jsonify(rows)

@app.get("/")
def index():
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta http-equiv="Cache-Control" content="no-store" />
  <title>AI-Powered IoT Dashboard</title>
  <style>
    :root { color-scheme: light dark; }
    body { font-family: system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,sans-serif; margin:3rem; background:#fafafa; }
    h1 { margin:0 0 1.5rem 0; font-size:2rem; }
    .card { padding:1.5rem 2rem; border:1px solid #ccc; border-radius:14px; max-width:1000px; background:#fff;
            box-shadow:0 2px 8px rgba(0,0,0,.05); transition:background .25s ease,border-color .25s ease; }
    .pill { display:inline-block; padding:.45rem .9rem; border-radius:999px; font-size:.95rem; font-weight:700; }
    .ok  { background:#22c55e; color:#fff; border:1px solid #16a34a; }
    .bad { background:#ef4444; color:#fff; border:1px solid #dc2626; }
    .none{ background:#e5e7eb; color:#374151; border:1px solid #d1d5db; }
    .k { color:#666; } .v { font-weight:600; }
    small { color:#777; }
    #raw { display:block; margin-top:1rem; font-family:monospace; font-size:.85rem; }
    canvas{ margin-top:2rem; max-width:1000px; }
  </style>
</head>
<body>
  <h1>AI-Powered IoT Dashboard <span id="badge" class="pill none">—</span></h1>

  <div class="card" id="card">
    <div><span class="k">Device:</span> <span class="v" id="device">—</span></div>
    <div><span class="k">Temperature:</span> <span class="v" id="temp">—</span> °C</div>
    <div><span class="k">Humidity:</span> <span class="v" id="hum">—</span> %</div>
    <div><span class="k">Timestamp:</span> <span class="v" id="ts">—</span></div>
    <small id="raw"></small>
  </div>

  <canvas id="comboChart" height="140"></canvas>

  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

  <script>
    function setBadge(anom){
      const b=document.getElementById('badge');
      const c=document.getElementById('card');
      if(anom===true){ b.className='pill bad'; b.textContent='ANOMALY'; c.style.background='#fee2e2'; c.style.borderColor='#ef4444'; }
      else if(anom===false){ b.className='pill ok'; b.textContent='Normal'; c.style.background='#dcfce7'; c.style.borderColor='#22c55e'; }
      else { b.className='pill none'; b.textContent='—'; c.style.background='#fff'; c.style.borderColor='#ccc'; }
    }

    const labels=[], temps=[], hums=[], tempColors=[], humColors=[];
    const maxPoints=300;
    const ctx=document.getElementById('comboChart').getContext('2d');
    const chart=new Chart(ctx,{
      type:'line',
      data:{
        labels,
        datasets:[
          { label:'Temperature (°C)', data:temps, yAxisID:'y',
            borderColor:'#0ea5e9', backgroundColor:'rgba(14,165,233,0.10)',
            borderWidth:3, tension:0.3, fill:false, pointRadius:3,
            pointBackgroundColor:tempColors, pointStyle:'circle' },
          { label:'Humidity (%)', data:hums, yAxisID:'y',
            borderColor:'#ff9800', backgroundColor:'rgba(255,152,0,0.12)',
            borderWidth:3, borderDash:[6,4], tension:0.3, fill:false, pointRadius:3,
            pointBackgroundColor:humColors, pointStyle:'triangle', spanGaps:true }
        ]
      },
      options:{
        animation:false, maintainAspectRatio:true,
        scales:{
          x:{ title:{display:true,text:'Time'} },
          y:{ type:'linear', position:'left',
              title:{display:true,text:'Temperature (°C) / Humidity (%)'},
              min:0, max:100 }
        },
        plugins:{ legend:{ display:true } }
      }
    });

    function addPoint(ts, temp, hum, anom){
      const t=Number.parseFloat(temp);
      const h=Number.parseFloat(hum);

      labels.push(ts);
      temps.push(Number.isFinite(t)?t:null);
      hums.push(Number.isFinite(h)?h:null);

      const col = (anom===true) ? '#ef4444' : '#22c55e';
      tempColors.push(col); humColors.push(col);

      if(labels.length>maxPoints){ labels.shift(); temps.shift(); hums.shift(); tempColors.shift(); humColors.shift(); }
      chart.update('none');
    }

    async function preloadHistory(){
      try{
        const r = await fetch('/api/history?limit=120', {cache:'no-store'});
        const arr = await r.json();
        labels.length=0; temps.length=0; hums.length=0; tempColors.length=0; humColors.length=0;
        arr.forEach(d=>{
          const col = (d.is_anomaly===true) ? '#ef4444' : '#22c55e';
          labels.push(d._ts ?? '');
          temps.push(Number.isFinite(+d.temperature) ? +d.temperature : null);
          hums.push(Number.isFinite(+d.humidity) ? +d.humidity : null);
          tempColors.push(col); humColors.push(col);
        });
        chart.update();
      }catch(e){ console.error('history error', e); }
    }

    async function refresh(){
      try{
        const r = await fetch('/api/latest', {cache:'no-store'});
        const d = await r.json();

        document.getElementById('device').textContent = d.device_id ?? '—';
        document.getElementById('temp').textContent   = d.temperature ?? '—';
        document.getElementById('hum').textContent    = d.humidity ?? '—';
        document.getElementById('ts').textContent     = d._ts ?? '—';
        document.getElementById('raw').textContent    = JSON.stringify(d);

        setBadge(d.is_anomaly);
        addPoint(d._ts ?? new Date().toLocaleTimeString(), d.temperature, d.humidity, d.is_anomaly);
      }catch(e){
        console.error('refresh error', e);
      }
    }

    (async function(){
      await preloadHistory();   // fill chart from DB once
      refresh();
      setInterval(refresh, 1500);
    })();
  </script>
</body>
</html>
"""

if __name__ == "__main__":
    threading.Thread(target=mqtt_thread, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
    