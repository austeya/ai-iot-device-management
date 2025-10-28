from src.ai_model import AIModel

def test_training_and_prediction():
    model = AIModel()
    data = list(range(0, 100))
    model.train(data)
    assert model.predict(50) in [True, False]
