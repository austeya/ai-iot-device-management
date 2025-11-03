import time
import random
import paho.mqtt.client as mqtt

BROKER = "broker.ai-iot.local"
TOPIC = "devices/sensor1/data"

client = mqtt.Client()
client.connect(BROKER, 1883, 60)

print("Simulator started. Sending fake data...")

while True:
    payload = {
        "temperature": round(random.uniform(20.0, 30.0), 2),
        "humidity": round(random.uniform(40.0, 60.0), 2)
    }
    client.publish(TOPIC, str(payload))
    print("Sent:", payload)
    time.sleep(5)
