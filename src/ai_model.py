from sklearn.ensemble import IsolationForest
import numpy as np
import joblib
import os

MODEL_PATH = "ai_model.pkl"


class AIModel:
    def __init__(self):
        self.model = None

    def train(self, data):
        """Train anomaly detection model on sample data."""
        X = np.array(data, dtype=float).reshape(-1, 1)
        self.model = IsolationForest(contamination=0.05, random_state=42)
        self.model.fit(X)
        joblib.dump(self.model, MODEL_PATH)
        print("✅ Model trained and saved to", MODEL_PATH)

    def load_model(self):
        """Load trained model from disk."""
        if os.path.exists(MODEL_PATH):
            self.model = joblib.load(MODEL_PATH)
            print("✅ Model loaded.")
        else:
            raise FileNotFoundError("Model not found, train it first!")

    def predict(self, value):
        """Return True if anomaly detected (as a native Python bool)."""
        if not self.model:
            self.load_model()
        pred = self.model.predict([[float(value)]])
        return bool(pred[0] == -1)

