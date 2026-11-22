import json
import pytest
from starlette.requests import Request
from starlette.testclient import TestClient
from services.analytics.admin_analytics import (
    get_periodic_report,
    export_periodic_report_csv,
    export_periodic_report_json,
)
from routers.admin import admin_reports_page, admin_reports_export
from core import app


def test_periodic_report_daily():
    report = get_periodic_report("daily")
    assert report["period"] == "daily"
    assert "Daily" in report["title"]
    assert len(report["intervals"]) == 14
    assert "totals" in report
    for k in ["signups", "resumes", "interviews", "bookings", "coding", "events"]:
        assert k in report["totals"]


def test_periodic_report_monthly():
    report = get_periodic_report("monthly")
    assert report["period"] == "monthly"
    assert "Monthly" in report["title"]
    assert len(report["intervals"]) == 12
    assert "totals" in report
    for k in ["signups", "resumes", "interviews", "bookings", "coding", "events"]:
        assert k in report["totals"]


def test_periodic_report_yearly():
    report = get_periodic_report("yearly")
    assert report["period"] == "yearly"
    assert "Yearly" in report["title"]
    assert len(report["intervals"]) == 5
    assert "totals" in report
    for k in ["signups", "resumes", "interviews", "bookings", "coding", "events"]:
        assert k in report["totals"]


def test_periodic_report_exports():
    csv_out = export_periodic_report_csv("daily")
    assert "Period Interval" in csv_out
    assert "TOTAL" in csv_out

    json_out = export_periodic_report_json("monthly")
    data = json.loads(json_out)
    assert data["period"] == "monthly"
    assert len(data["intervals"]) == 12


def test_admin_reports_endpoint_unauthenticated():
    client = TestClient(app, follow_redirects=False)
    resp = client.get("/admin/reports")
    # Redirects to auth-required / admin-login
    assert resp.status_code == 303
    assert resp.headers.get("location") in ("/admin-login", "/?auth=required")


def test_admin_reports_view_authenticated():
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/admin/reports",
        "headers": [],
        "session": {"admin": True, "user_role": "admin"},
    }
    req = Request(scope)

    # Test daily view
    resp_daily = admin_reports_page(req, period="daily")
    assert resp_daily.status_code == 200

    # Test monthly view
    resp_monthly = admin_reports_page(req, period="monthly")
    assert resp_monthly.status_code == 200

    # Test yearly view
    resp_yearly = admin_reports_page(req, period="yearly")
    assert resp_yearly.status_code == 200

    # Test export endpoints
    csv_resp = admin_reports_export(req, period="daily", format="csv")
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers.get("content-type", "")

    json_resp = admin_reports_export(req, period="monthly", format="json")
    assert json_resp.status_code == 200
    assert "application/json" in json_resp.headers.get("content-type", "")
