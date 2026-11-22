import json
import pytest
from starlette.requests import Request
from starlette.testclient import TestClient
from core.security import get_client_ip, get_client_geo
from services.analytics.admin_analytics import (
    record_visitor_traffic,
    get_visitor_traffic_analytics,
    export_visitor_traffic_csv,
    export_visitor_traffic_json,
    init_admin_tables,
)
from routers.admin import admin_traffic_page, admin_traffic_export
from core import app


def test_get_client_ip_forwarded_for():
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"x-forwarded-for", b"203.0.113.195, 70.41.3.18")],
    }
    req = Request(scope)
    assert get_client_ip(req) == "203.0.113.195"


def test_get_client_ip_real_ip():
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"x-real-ip", b"198.51.100.42")],
    }
    req = Request(scope)
    assert get_client_ip(req) == "198.51.100.42"


def test_get_client_geo_headers():
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [
            (b"x-vercel-ip-country", b"US"),
            (b"x-vercel-ip-country-region", b"CA"),
            (b"x-vercel-ip-city", b"San%20Francisco"),
        ],
    }
    req = Request(scope)
    geo = get_client_geo(req)
    assert geo["country"] == "US"
    assert geo["region"] == "CA"
    assert geo["city"] == "San Francisco"


def test_visitor_traffic_recording_and_analytics():
    init_admin_tables()

    # Record visits from distinct IPs and geographies
    record_visitor_traffic(
        ip="192.0.2.1",
        country="US",
        region="CA",
        city="San Francisco",
        path="/",
        method="GET",
        status_code=200,
        user_agent="Mozilla/5.0 TestBrowser",
        user_id="user_test_1",
    )
    record_visitor_traffic(
        ip="192.0.2.2",
        country="IN",
        region="KA",
        city="Bengaluru",
        path="/resume",
        method="GET",
        status_code=200,
        user_agent="Mozilla/5.0 TestBrowser",
        user_id="anonymous",
    )
    record_visitor_traffic(
        ip="192.0.2.1",
        country="US",
        region="CA",
        city="San Francisco",
        path="/coding",
        method="GET",
        status_code=200,
        user_agent="Mozilla/5.0 TestBrowser",
        user_id="user_test_1",
    )

    analytics = get_visitor_traffic_analytics()
    assert analytics["kpis"]["total_hits"] >= 3
    assert analytics["kpis"]["unique_ips_total"] >= 2
    assert analytics["kpis"]["unique_ips_today"] >= 2
    assert analytics["kpis"]["unique_countries"] >= 2

    # Check top countries
    countries = [c["country"] for c in analytics["top_countries"]]
    assert "US" in countries or "IN" in countries

    # Check recent visitors log
    assert len(analytics["recent_visitors"]) >= 3
    recent_ips = [v["ip"] for v in analytics["recent_visitors"]]
    assert "192.0.2.1" in recent_ips
    assert "192.0.2.2" in recent_ips


def test_visitor_traffic_exports():
    csv_out = export_visitor_traffic_csv(limit=10)
    assert "Timestamp_UTC" in csv_out
    assert "IP" in csv_out
    assert "Country" in csv_out

    json_out = export_visitor_traffic_json(limit=10)
    data = json.loads(json_out)
    assert isinstance(data, list)
    if data:
        assert "ip" in data[0]
        assert "country" in data[0]


def test_admin_traffic_endpoint_unauthenticated():
    client = TestClient(app, follow_redirects=False)
    resp = client.get("/admin/traffic")
    assert resp.status_code == 303
    assert resp.headers.get("location") in ("/admin-login", "/?auth=required")


def test_admin_traffic_view_authenticated():
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/admin/traffic",
        "headers": [],
        "session": {"admin": True, "user_role": "admin"},
    }
    req = Request(scope)

    # Test traffic view page
    resp = admin_traffic_page(req, q="")
    assert resp.status_code == 200

    # Test export CSV
    csv_resp = admin_traffic_export(req, format="csv")
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers.get("content-type", "")

    # Test export JSON
    json_resp = admin_traffic_export(req, format="json")
    assert json_resp.status_code == 200
    assert "application/json" in json_resp.headers.get("content-type", "")
