from flask import Flask, jsonify, request, redirect, make_response
import threading, os, json, time, sqlite3
from pathlib import Path
import paho.mqtt.client as mqtt
from functools import wraps
import sys

# ---------------- Python path so we can import src/* ----------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if "/app" not in sys.path:
    sys.path.append("/app")

from src.ai_model import AIModel  # noqa

app = Flask(__name__)

# ---------------- Environment ----------------
MQTT_BROKER = os.getenv("MQTT_BROKER", "broker")
IOT_TOPIC   = os.getenv("IOT_TOPIC", "iot/devices/sensor")

ADMIN_USER = (os.getenv("ADMIN_USER", "admin") or "").strip()
ADMIN_PASSWORD = (os.getenv("ADMIN_PASSWORD", "admin") or "").strip()
AUTH_DISABLE = str(os.getenv("AUTH_DISABLE", "0")).strip().lower() in ("1", "true", "yes")

print(f"[AUTH] ADMIN_USER set? {'yes' if ADMIN_USER else 'no'}; "
      f"ADMIN_PASSWORD length={len(ADMIN_PASSWORD)}; AUTH_DISABLE={AUTH_DISABLE}")

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

# ---------------- Live state ----------------
latest = {"status": "waiting for data..."}

# ---------------- AI model ----------------
model = AIModel()
try:
    model.load_model()
except Exception:
    model.train([x / 10.0 for x in range(180, 281)])  # 18.0..28.0 "normal"

# ---------------- MQTT ----------------
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

    try:
        t = float(payload.get("temperature", "nan"))
        payload["is_anomaly"] = (bool(model.predict(t)) if t == t else None)
    except Exception as e:
        print("AI predict error:", e)
        payload["is_anomaly"] = None

    latest = payload
    db_insert(payload)
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

# ---------------- AUTH ----------------
def _is_authed():
    return request.cookies.get("auth") == "1" or AUTH_DISABLE

def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if _is_authed():
            return fn(*args, **kwargs)
        nxt = request.full_path if request.query_string else request.path
        return redirect(f"/login?next={nxt}", code=302)
    return wrapper

@app.get("/login")
def login_form():
    if _is_authed():
        return redirect(request.args.get("next") or "/", code=302)
    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Login</title>
  <style>
    :root{{ color-scheme: light dark; }}
    body{{font-family:system-ui;display:grid;place-items:center;height:100vh;background:#f7fafc;margin:0}}
    form{{background:#fff;padding:24px;border:1px solid #e5e7eb;border-radius:12px;min-width:360px;box-shadow:0 10px 20px rgba(0,0,0,.05)}}
    label{{display:block;margin:8px 0 4px;color:#374151}}
    input{{width:100%;padding:10px;border:1px solid #cbd5e1;border-radius:8px}}
    button{{margin-top:14px;width:100%;padding:12px;border:0;border-radius:10px;background:#2563eb;color:#fff;font-weight:700}}
    small{{color:#6b7280}}
  </style>
</head>
<body>
  <form method="post" action="/login">
    <h2 style="margin:0 0 8px 0">Sign in</h2>
    <small>Env credentials (ADMIN_USER / ADMIN_PASSWORD)</small>
    <label for="u">Username</label>
    <input id="u" name="username" required>
    <label for="p">Password</label>
    <input id="p" name="password" type="password" required>
    <input type="hidden" name="next" value="{(request.args.get('next') or '/') }">
    <button type="submit">Login</button>
  </form>
</body>
</html>
"""

@app.post("/login")
def login():
    if request.is_json:
        data = request.get_json(silent=True) or {}
        in_user = (data.get("username") or "").strip()
        in_pass = (data.get("password") or "").strip()
        next_url = (data.get("next") or "/")
    else:
        in_user = (request.form.get("username") or "").strip()
        in_pass = (request.form.get("password") or "").strip()
        next_url = (request.form.get("next") or "/")

    ok = (in_user == ADMIN_USER) and (in_pass == ADMIN_PASSWORD)
    if not ok and AUTH_DISABLE:
        ok = True

    print(f"[AUTH] login attempt user='{in_user}' "
          f"match_user={in_user==ADMIN_USER} "
          f"pass_len={len(in_pass)} match_pass={in_pass==ADMIN_PASSWORD}")

    if ok:
        resp = make_response(redirect(next_url, code=303))
        resp.set_cookie("auth", "1", max_age=8*60*60, httponly=True, samesite="Lax")
        return resp

    return ("Invalid credentials", 401)

@app.get("/logout")
def logout():
    resp = make_response(redirect("/login", code=302))
    resp.delete_cookie("auth")
    return resp

@app.get("/whoami")
def whoami():
    return jsonify({
        "authed": _is_authed(),
        "user_env": bool(ADMIN_USER),
        "auth_disabled": AUTH_DISABLE,
        "admin_user_len": len(ADMIN_USER),
        "admin_pass_len": len(ADMIN_PASSWORD)
    })

# ---------------- Health & APIs ----------------
@app.get("/healthz")
def healthz():
    return jsonify({"ok": True})

@app.get("/api/latest")
def api_latest():
    return jsonify(latest)

@app.get("/api/history")
def api_history():
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

# ---------------- Dashboard page (wider layout) ----------------
@app.get("/")
@require_auth
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
      .wrap{ display:grid; gap:1.25rem; grid-template-columns: 1fr; max-width: 1280px; }
      .row { display:flex; align-items:center; gap:.75rem; }
      .card { padding:1.25rem 1.5rem; border:1px solid #cbd5e1; border-radius:14px; background:#fff; box-shadow: 0 10px 20px rgba(0,0,0,.04);}
      .pill { display:inline-flex; align-items:center; padding:.4rem .75rem; border-radius:999px; font-weight:700; letter-spacing:.2px }
      .ok { background:#22c55e; color:#fff; border:1px solid #16a34a; }
      .bad{ background:#ef4444; color:#fff; border:1px solid #dc2626; }
      .none{background:#e5e7eb; color:#374151; border:1px solid #d1d5db; }
      .kv { display:grid; grid-template-columns: 240px 1fr; gap:.6rem 1rem; }
      .k { color:#475569; font-weight:600; }
      .v { font-weight:600; color:#0f172a; }
      .charts{ display:grid; grid-template-columns: 1fr 1fr; gap:1.25rem; }
      canvas{ width:100%; height:300px; border:1px solid #e2e8f0; border-radius:12px; background:#fff; }
      label{ font-size:1rem; color:#334155; }
      select{ padding:.5rem .7rem; border-radius:10px; border:1px solid #cbd5e1; min-width:200px; }
      small { color:#64748b; }
      #raw { display:block; margin-top:.5rem; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; font-size:.9rem; color:#0f172a }
      a.btn { padding:.4rem .7rem; border:1px solid #cbd5e1; border-radius:10px; text-decoration:none; color:#0f172a; background:#fff }
      a.btn:hover{ background:#f8fafc }
      .spacer{ flex:1 }
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="row">
        <h1 style="margin:0;">AI-Powered IoT Dashboard</h1>
        <span id="badge" class="pill none">—</span>
        <div class="spacer"></div>
        <a class="btn" href="/logout">Logout</a>
      </div>

      <div class="row">
        <div class="card" style="flex:1">
          <div class="row" style="gap:1.5rem; align-items:flex-start">
            <div style="min-width:380px; max-width:560px;">
              <div class="kv">
                <div class="k">Device</div>     <div class="v" id="device">—</div>
                <div class="k">Temperature</div> <div class="v"><span id="temp">—</span> °C</div>
                <div class="k">Humidity</div>    <div class="v"><span id="hum">—</span> %</div>
                <div class="k">Timestamp</div>   <div class="v" id="ts">—</div>
              </div>
            </div>
            <div style="min-width:260px;">
              <label for="deviceSel">Filter by device</label><br/>
              <select id="deviceSel"><option value="">All</option></select>
              <div><small id="raw"></small></div>
            </div>
          </div>
        </div>
      </div>

      <div class="charts">
        <canvas id="tempChart" width="620" height="300"></canvas>
        <canvas id="humChart"  width="620" height="300"></canvas>
      </div>
    </div>

    <script>
      const sel = document.getElementById('deviceSel');

      function setBadge(anom){
        const b = document.getElementById('badge');
        if(anom===true){ b.className='pill bad'; b.textContent='ANOMALY'; }
        else if(anom===false){ b.className='pill ok'; b.textContent='Normal'; }
        else { b.className='pill none'; b.textContent='—'; }
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
        ctx.clearRect(0,0,ctx.canvas.width, ctx.canvas.height);
        const W = ctx.canvas.width, H = ctx.canvas.height;
        const left=50, right=W-12, top=16, bottom=H-34;

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

        // labels
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

        // anomalies
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

      loadDevices(); refreshLatest(); refreshCharts();
      setInterval(refreshLatest, 1500);
      setInterval(refreshCharts, 3000);
      setInterval(loadDevices, 7000);
      sel.addEventListener('change', ()=> { refreshCharts(); });
    </script>
  </body>
</html>
"""

# ---------------- Main ----------------
if __name__ == "__main__":
    threading.Thread(target=mqtt_thread, daemon=True).start()
    app.run(host="0.0.0.0", port=80)