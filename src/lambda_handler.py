import json
from src.ai_model import AIModel

model = AIModel()
try:
    model.load_model()
except Exception:
    # Fallback: train a tiny model so tests can run
    model.train(list(range(0, 100)))


def lambda_handler(event, context=None):
    """
    Simulated AWS Lambda handler.
    Expects event like: {"body": "{\"device_id\": \"device-001\", \"temperature\": 25}"}
    """
    # In tests we pass event["body"] as a JSON string
    raw_body = event.get("body", "{}")
    if isinstance(raw_body, str):
        data = json.loads(raw_body)
    else:
        data = raw_body  # already a dict

    value = float(data.get("temperature", 0))
    anomaly = bool(model.predict(value))
    response = {
        "device_id": data.get("device_id", "unknown"),
        "temperature": value,
        "is_anomaly": anomaly,  # plain Python bool (JSON-serializable)
    }
    print(f"Processed event: {response}")
    return {"statusCode": 200, "body": json.dumps(response)}
