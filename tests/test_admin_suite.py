from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

def test_unauthenticated_admin_blocked():
    pages = [
        "/admin",
        "/admin?demo=true",
        "/admin/demo",
        "/admin/demo/reports",
        "/admin/demo/traffic",
        "/admin/demo/premium",
        "/admin/demo/bookings",
        "/admin/demo/coding",
        "/admin/demo/experiments",
        "/admin/demo/users",
        "/admin/demo/safety",
        "/admin/reports",
        "/admin/traffic",
        "/admin/premium",
        "/admin/bookings",
        "/admin/coding",
        "/admin/experiments",
        "/admin/users",
        "/admin/safety",
    ]
    for url in pages:
        resp = client.get(url, follow_redirects=False)
        assert resp.status_code in (302, 303, 307), f"Expected redirect for {url}, got {resp.status_code}"
        assert "/admin-login" in resp.headers.get("location", ""), f"Expected redirect to /admin-login for {url}"


def test_robots_txt_disallows_admin():
    resp = client.get("/robots.txt")
    assert resp.status_code == 200
    assert "Disallow: /admin/" in resp.text
    assert "Disallow: /admin" in resp.text
    assert "Allow: /admin/demo" not in resp.text
    assert "Allow: /admin\n" not in resp.text
    assert "Allow: /admin/\n" not in resp.text
    assert "Allow: /admin-login" in resp.text
