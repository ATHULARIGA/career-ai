from fastapi.testclient import TestClient
import main


def test_healthz_ok():
    client = TestClient(main.app)
    resp = client.get('/healthz')
    assert resp.status_code == 200
    assert resp.json().get('status') == 'ok'


def test_public_pages():
    client = TestClient(main.app)
    assert client.get('/').status_code == 200
    assert client.get('/login').status_code == 200
    assert client.get('/signup').status_code == 200


def test_protected_redirect_when_logged_out():
    client = TestClient(main.app)
    resp = client.get('/resume', follow_redirects=False)
    assert resp.status_code in (302, 303, 307)
