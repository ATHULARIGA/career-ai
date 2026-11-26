"""Tests for versioned /api/v1 endpoints, Pydantic schemas, and repository layer."""

from starlette.testclient import TestClient

from main import app

client = TestClient(app)


def test_api_v1_health():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["version"] == "v1"


def test_api_v1_interview_endpoints():
    resumes_res = client.get("/api/v1/interview/resumes")
    assert resumes_res.status_code == 200
    assert "resumes" in resumes_res.json()

    techs_res = client.get("/api/v1/interview/technologies")
    assert techs_res.status_code == 200
    assert "resume_technologies" in techs_res.json()

    cs_res = client.get("/api/v1/interview/cheatsheet?tech=FastAPI")
    assert cs_res.status_code == 200
    assert cs_res.json()["tech_name"] == "FastAPI"

    missing_res = client.get("/api/v1/interview/cheatsheet?tech=")
    assert missing_res.status_code == 400
    assert missing_res.json()["code"] == "validation_error"

    not_found_res = client.post("/api/v1/interview/select-resume", json={"resume_id": "nonexistent_999"})
    assert not_found_res.status_code == 404
    assert not_found_res.json()["code"] == "not_found"

    revise_res = client.post(
        "/api/v1/interview/cheatsheet/revise",
        json={"tech": "FastAPI", "card_index": 0, "revised": True},
    )
    assert revise_res.status_code == 200
    assert 0 in revise_res.json()["revised_indices"]
