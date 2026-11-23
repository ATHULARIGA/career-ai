from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_admin_demo_direct_pages():
    pages = [
        "/admin/demo",
        "/admin/demo/reports",
        "/admin/demo/traffic",
        "/admin/demo/premium",
        "/admin/demo/bookings",
        "/admin/demo/coding",
        "/admin/demo/experiments",
        "/admin/demo/users",
        "/admin/demo/safety",
    ]
    for url in pages:
        resp = client.get(url, follow_redirects=False)
        assert resp.status_code == 200, f"Failed for {url}: status {resp.status_code}"
        assert 'style="' not in resp.text, f"Inline style found in {url}"
        assert '<article' not in resp.text, f"Article tag found in {url}"


def test_admin_query_param_pages():
    pages = [
        "/admin?demo=true",
        "/admin/reports?demo=true",
        "/admin/traffic?demo=true",
        "/admin/premium?demo=true",
        "/admin/bookings?demo=true",
        "/admin/coding?demo=true",
        "/admin/experiments?demo=true",
        "/admin/users?demo=true",
        "/admin/safety?demo=true",
    ]
    for url in pages:
        resp = client.get(url, follow_redirects=False)
        assert resp.status_code == 200, f"Failed for {url}: status {resp.status_code}"
        assert 'style="' not in resp.text, f"Inline style found in {url}"
        assert '<article' not in resp.text, f"Article tag found in {url}"


def test_robots_txt_allows_admin_demo():
    resp = client.get("/robots.txt")
    assert resp.status_code == 200
    assert "Disallow: /admin/" not in resp.text
    assert "Allow: /admin/demo" in resp.text
    assert "Allow: /admin" in resp.text


def test_unauthenticated_admin_blocked():
    resp = client.get("/admin", follow_redirects=False)
    assert resp.status_code in (302, 303, 307)
    assert "/admin-login" in resp.headers["location"]
