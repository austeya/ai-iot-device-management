# AI-Powered IoT Device Management

![CI](https://github.com/austeya/ai-iot-device-management/actions/workflows/ci-cd.yml/badge.svg)

The AI-Powered IoT Device Management System is a cloud-based platform designed to simulate, monitor, and intelligently manage Internet of Things (IoT) devices using DevOps principles and artificial intelligence. The system enables real-time device data collection, processing, and anomaly detection to improve operational efficiency and reliability.

---

## 🚀 Features

- 🛰️ **MQTT simulator** publishing multiple devices (`device-001`, `device-002`, …)
- 🧠 **Anomaly detection** (simple model, easy to swap out)
- 📊 **Realtime dashboard** (temperature + humidity, color status pill)
- 🗄️ **History API** for plotting last N points
- 🧪 **Pytest** suite + **GitHub Actions CI**
- 📦 **Dockerized** (broker, dashboard, simulator) + optional CD to Docker Hub

---

## ⚙️ Architecture
┌────────────┐ MQTT ┌─────────────┐
│ Simulated │ publish JSON → │ Mosquitto │
│ IoT Devices│ │ Broker │
└─────┬──────┘ └─────┬───────┘
│ │
│ subscribe │
▼ ▼
┌─────────────┐ AI + Storage ┌──────────────┐
│ Flask App │◄────────────────▶│ SQLite DB │
│ (Dashboard) │ └──────────────┘
└─────────────┘


### Data Flow
1. `device_simulator.py` publishes temperature + humidity data for multiple devices.  
2. Mosquitto broker forwards messages to the Flask dashboard subscriber.  
3. `app.py` receives payloads, runs `AIModel.predict()`, and stores data in SQLite.  
4. Dashboard displays:
   - Current device readings  
   - Real-time temperature & humidity charts  
   - Anomaly indicators (green/red background)  

---

## 🧩 Technologies

| Component | Tool / Library |
|------------|----------------|
| **Language** | Python 3.11 |
| **Frameworks** | Flask, scikit-learn, paho-mqtt |
| **Storage** | SQLite |
| **Containerization** | Docker & Docker Compose |
| **Visualization** | HTML, CSS, JavaScript (Charts) |
| **ML Model** | Isolation Forest for anomaly detection |

---

## 🚀 Setup & Run Instructions

### 1️⃣ Clone and open project
```bash
git clone https://github.com/austeya/ai-iot-device-management.git
cd ai-iot-device-management