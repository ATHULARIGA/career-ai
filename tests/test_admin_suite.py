from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_all_admin_pages_demo_access():
    admin_pages = [
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
    for url in admin_pages:
        resp = client.get(url, follow_redirects=False)
        assert resp.status_code == 200, f"Failed for {url}: status {resp.status_code}"
        # Ensure zero inline styles
        assert 'style="' not in resp.text, f"Inline style found in {url}"
        # Ensure zero article tags lacking headings
        assert '<article' not in resp.text, f"Article tag found in {url}"


def test_admin_demo_redirects():
    resp = client.get("/admin/demo", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "/admin?demo=true" in resp.headers["location"]

    resp = client.get("/admin/demo/reports", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "/admin/reports?demo=true" in resp.headers["location"]


def test_unauthenticated_admin_blocked():
    resp = client.get("/admin", follow_redirects=False)
    assert resp.status_code in (302, 303, 307)
    assert "/admin-login" in resp.headers["location"]
