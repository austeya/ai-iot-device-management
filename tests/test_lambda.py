import json
from src.lambda_handler import lambda_handler

def test_lambda_handler():
    event = {"body": json.dumps({"device_id": "device-001", "temperature": 25})}
    response = lambda_handler(event)
    assert response["statusCode"] == 200
