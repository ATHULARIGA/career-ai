import sys
import json
import requests
from fastapi.testclient import TestClient

# Standard setup
from main import app
from core import scrape_job_link
from scoring import clean_scraped_jd

def test_scrape_unsupported():
    print("Testing unsupported domains...")
    res = scrape_job_link("https://www.linkedin.com/jobs/view/12345")
    assert "error" in res
    assert "LinkedIn/Indeed/Glassdoor require login" in res["error"]
    print("✅ Passed - unsupported domains blocked")

def test_scrape_timeout():
    print("Testing timeout handler (using unreachable IP)...")
    # httpbin.org/delay/10 can test wait, but to be 100% offline-solid:
    res = scrape_job_link("http://10.255.255.1") # Unroutable IP to force timeout
    assert "error" in res
    assert "Request timed out" in res["error"] or "Scraping failed" in res["error"]
    print("✅ Passed - timeout handled")

def test_scrape_404():
    print("Testing HTTP 404 response handler...")
    res = scrape_job_link("https://httpbin.org/status/404")
    assert "error" in res
    assert "Could not access URL" in res["error"]
    print("✅ Passed - HTTP 404 handled")

def test_scrape_short_content():
    print("Testing <120 char short content failure...")
    # httpbin.org/html returns a decent amount of text, let's use a URL that returns almost nothing
    res = scrape_job_link("https://httpbin.org/deny") # Returns very little text typically
    assert "error" in res
    assert "Could not extract a readable description" in res["error"]
    print("✅ Passed - short content rejected")

def test_ai_cleanup_trigger():
    print("Testing AI cleanup fallback threshold...")
    # We can invoke clean_scraped_jd directly
    large_text = "Job Description Overview.\n" + ("We need a developer.\n" * 200) # >4000 chars
    res = clean_scraped_jd(large_text)
    assert res is not None
    assert len(res) < len(large_text) # AI should condense it
    print("✅ Passed - AI cleanup executed")

def test_scrape_greenhouse_fallback():
    print("Testing greenhouse selector fallback (no .job-body)...")
    original_get = requests.get
    def monkey_get(url, **kwargs):
        class Resp:
            status_code = 200
            text = "<html><body><h1>Engineering Lead</h1><p>Requires Python, SQL, and 5 years experience. We are looking for a highly motivated individual with deep expertise in full-stack architecture, database indexing, and leading agile engineering sprints for at least 5 years.</p></body></html>"
        return Resp()
    requests.get = monkey_get
    try:
        res = scrape_job_link("https://boards.greenhouse.io/demo")
        assert "error" not in res or res["error"] is None
        assert "Engineering Lead" in res["text"]
        print("✅ Passed - greenhouse fallback supported")
    finally:
        requests.get = original_get

if __name__ == "__main__":
    try:
        test_scrape_unsupported()
        test_scrape_timeout()
        test_scrape_404()
        test_scrape_short_content()
        test_ai_cleanup_trigger()
        test_scrape_greenhouse_fallback()
        print("\n🎉 All JD Auto-Extraction Verification Tests Passed!")
        sys.exit(0)
    except AssertionError:
        import traceback
        print("\n❌ Test Failed:")
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Execution Error: {e}")
        sys.exit(1)
