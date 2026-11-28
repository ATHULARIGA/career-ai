"""SEO crawlability tests for 404 handling, HEAD support, robots.txt, sitemap.xml, and noindex."""

from starlette.testclient import TestClient

from main import app


def test_unknown_route_returns_real_404():
    client = TestClient(app)
    res = client.get("/nonexistent-seo-check", follow_redirects=False)
    assert res.status_code == 404


def test_head_requests_on_public_pages_return_200():
    client = TestClient(app)
    for path in ("/", "/resume", "/roadmap"):
        res = client.head(path, follow_redirects=False)
        assert res.status_code == 200, f"HEAD {path} returned {res.status_code}"


def test_robots_txt_allows_ai_crawlers_and_blocks_private_paths():
    client = TestClient(app)
    res = client.get("/robots.txt")
    assert res.status_code == 200
    body = res.text
    for bot in ("GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "PerplexityBot", "Google-Extended"):
        assert bot in body
    assert "Disallow: /admin-login" in body
    assert "Disallow: /login" in body
    assert "Disallow: /account" in body
    assert "Allow: /admin-login" not in body


def test_sitemap_xml_has_lastmod_and_tracks():
    client = TestClient(app)
    res = client.get("/sitemap.xml")
    assert res.status_code == 200
    assert "<lastmod>" in res.text
    assert "/roadmap/python-developer" in res.text


def test_auth_pages_have_noindex_header():
    client = TestClient(app)
    for path in ("/login", "/signup", "/admin-login"):
        res = client.get(path, follow_redirects=False)
        assert "noindex" in res.headers.get("x-robots-tag", "").lower()


def test_schema_and_llms_full_txt():
    client = TestClient(app)
    home = client.get("/")
    assert home.status_code == 200
    assert '"@type": "FAQPage"' in home.text

    roadmap = client.get("/roadmap")
    assert roadmap.status_code == 200
    assert '"@type": "BreadcrumbList"' in roadmap.text

    llms_full = client.get("/llms-full.txt")
    assert llms_full.status_code == 200
    assert "/roadmap/python-developer" in llms_full.text
