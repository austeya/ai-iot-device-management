# AI-Powered IoT Device Management

![CI](https://github.com/austeya/ai-iot-device-management/actions/workflows/ci-cd.yml/badge.svg)

An end-to-end IoT demo: MQTT device simulator → anomaly detection → Flask dashboard with live charts and history.

---

## 🚀 Features

- 🛰️ **MQTT simulator** publishing multiple devices (`device-001`, `device-002`, …)
- 🧠 **Anomaly detection** (simple model, easy to swap out)
- 📊 **Realtime dashboard** (temperature + humidity, color status pill)
- 🗄️ **History API** for plotting last N points
- 🧪 **Pytest** suite + **GitHub Actions CI**
- 📦 **Dockerized** (broker, dashboard, simulator) + optional CD to Docker Hub

---

## 🧩 Architecture

[Simulated Devices] --MQTT--> [Mosquitto Broker] --HTTP--> [Flask Dashboard]
| |
+-------------------------+
/api/latest
/api/history?limit=100

yaml
Copy code

---

## ⚙️ Quick Start (Docker Compose)

```bash
docker compose up --build
Services
mqtt-broker – Eclipse Mosquitto at localhost:1883

dashboard – Flask UI at http://localhost:5000

simulator – publishes to topic iot/devices/sensor

Key environment variables (see docker-compose.yml)
ini
Copy code
MQTT_BROKER=broker
IOT_TOPIC=iot/devices/sensor
DEVICES=device-001,device-002
🔗 API Endpoints
Endpoint	Description
/	Dashboard UI
/api/latest	Last message + anomaly flag
/api/history?limit=100	Recent messages (newest first)

Example JSON output
json
Copy code
{
  "_ts": "2025-10-22 14:37:46",
  "device_id": "device-001",
  "temperature": 43.26,
  "humidity": 50.01,
  "is_anomaly": true,
  "timestamp": "2025-10-22 14:37:46"
}
🧪 Local Development
bash
Copy code
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -q
Run the dashboard locally
bash
Copy code
export MQTT_BROKER=localhost
export IOT_TOPIC=iot/devices/sensor
python dashboard/app.py
# open http://localhost:5000
✅ Tests
bash
Copy code
pytest -q
⚡ CI / CD
CI runs on every push to main: installs dependencies, runs tests, builds image.

CD (optional) pushes Docker image to Docker Hub if tests pass.

To enable Docker Hub publishing
Set these repository secrets in GitHub → Settings → Secrets → Actions:

DOCKERHUB_USERNAME

DOCKERHUB_TOKEN (Docker Hub access token)

Image tags
latest

<git-sha>

📂 Folder Structure
bash
Copy code
.
├─ dashboard/           # Flask app (UI + APIs)
├─ src/                 # AI model, simulator, utils
├─ tests/               # pytest tests
├─ infra/               # optional IaC placeholders
├─ docker-compose.yml
├─ Dockerfile
└─ .github/workflows/ci-cd.yml
🪪 License
MIT (or your preferred license)

🧭 Commit your changes
bash
Copy code
git add README.md
git commit -m "Fix README formatting and structure"
git push
