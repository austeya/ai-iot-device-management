import os
import time
import json
import random
from typing import List
import paho.mqtt.client as mqtt

BROKER = os.getenv("MQTT_BROKER", "broker")
TOPIC = os.getenv("IOT_TOPIC", "iot/devices/sensor")

# Comma-separated list of device IDs; default two devices
DEVICES: List[str] = [
    d.strip() for d in os.getenv("DEVICES", "device-001,device-002").split(",") if d.strip()
]

client = mqtt.Client()

def connect():
    client.on_connect = lambda c, u, f, rc: print(f"🔗 MQTT on_connect rc={rc}")
    # retry loop so we don’t crash if broker isn’t ready
    for attempt in range(1, 11):
        try:
            print(f"🔌 Connecting to MQTT broker: {BROKER} (attempt {attempt})")
            client.connect(BROKER, 1883, 60)
            break
        except Exception as e:
            print(f"⚠️ Connect failed: {e}; retrying…")
            time.sleep(2)
    client.loop_start()

def _device_seed(device_id: str) -> int:
    # stable seed per device so patterns differ but remain consistent
    return sum(ord(ch) for ch in device_id) % 10_000

def _generate_reading(device_id: str) -> dict:
    rnd = random.Random(_device_seed(device_id) + int(time.time()) // 5)
    base_temp = rnd.uniform(18, 30)      # “normal” window
    base_hum  = rnd.uniform(35, 85)
    # sporadic spikes/dips to trigger anomalies occasionally
    if rnd.random() < 0.08:
        base_temp += rnd.uniform(10, 18)   # heat spike
    if rnd.random() < 0.06:
        base_temp -= rnd.uniform(8, 12)    # cold dip

    return {
        "device_id": device_id,
        "temperature": round(base_temp, 2),
        "humidity": round(base_hum, 2),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

def publish_data(payload: dict):
    """Kept for tests: publish a single reading."""
    msg = json.dumps(payload)
    client.publish(TOPIC, msg, qos=0, retain=False)
    print(f"📤 Published: {msg}")

def run():
    connect()
    print(f"🧪 Devices configured: {DEVICES}")
    while True:
        for device_id in DEVICES:
            reading = _generate_reading(device_id)
            publish_data(reading)
            time.sleep(0.8)   # small gap between devices
        time.sleep(0.7)       # small pause between cycles

if __name__ == "__main__":
    run()
