import pytest
from src.device_simulator import publish_data

def test_simulator_runs():
    assert callable(publish_data)
