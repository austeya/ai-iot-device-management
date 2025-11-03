from dashboard.app import app
def test_health():
    client = app.test_client()
    resp = client.get('/api/latest')
    assert resp.status_code == 200
