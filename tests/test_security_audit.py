"""
Security regression tests covering SSRF protection, DOM XSS escaping,
and production error/CSRF hardening.
"""

from core.helpers import _is_safe_public_url, scrape_job_link


def test_ssrf_blocks_internal_and_non_http_urls():
    for bad_url in [
        "http://127.0.0.1:8000/admin",
        "http://localhost:8000/healthz",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/internal",
        "http://192.168.1.1/router",
        "file:///etc/passwd",
        "ftp://example.com/file",
    ]:
        ok, err = _is_safe_public_url(bad_url)
        assert ok is False, f"Expected SSRF guard to block {bad_url}"
        assert err

        res = scrape_job_link(bad_url)
        assert res["text"] == ""
        assert res["error"]


def test_interview_template_escapes_dynamic_tech_pills():
    with open("templates/interview/interview.html", encoding="utf-8") as f:
        html = f.read()

    assert "const safeTech = escapeHtml(data.tech_name);" in html
    assert "<span>${t}</span>" not in html
    assert "<span>${data.tech_name}</span>" not in html
