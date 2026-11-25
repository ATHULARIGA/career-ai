"""
Unit and integration tests for Technology Interview Cheat Sheets.
Verifies resume skill extraction, curated card decks, custom technology generation,
resume tailoring, API endpoints, revision tracking, standalone HTML export,
and WCAG contrast standards.
"""

import pytest
from starlette.testclient import TestClient
from main import app
from services.interview.cheatsheet_generator import (
    extract_technologies_from_resume,
    get_cheatsheet_for_technology,
    build_standalone_cheatsheet_html,
    tailor_cheatsheet_for_resume,
)
from core.database import (
    save_user_cheatsheet,
    get_user_cheatsheets,
    update_cheatsheet_revised,
    delete_user_cheatsheet,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_extract_technologies_from_resume_text():
    sample_resume = """
    Athul Ananthariga
    Senior Backend Engineer
    Skills: Python, FastAPI, Docker, PostgreSQL, Redis, React, AWS, Kubernetes, Git
    Experience: Built high-throughput microservices using FastAPI and asyncpg.
    """
    techs = extract_technologies_from_resume(sample_resume)
    assert isinstance(techs, list)
    assert len(techs) >= 4
    assert "FastAPI" in techs
    assert "Python" in techs
    assert "Docker" in techs
    assert "PostgreSQL" in techs


def test_extract_technologies_fallback_when_empty():
    techs = extract_technologies_from_resume("")
    assert isinstance(techs, list)
    assert len(techs) >= 3
    assert "FastAPI" in techs
    assert "Python" in techs


def test_get_cheatsheet_curated_fastapi():
    cs = get_cheatsheet_for_technology("FastAPI")
    assert cs["tech_name"] == "FastAPI"
    assert cs["total_cards"] >= 10
    assert "All" in cs["categories"]
    assert "Basics" in cs["categories"]
    # Verify card schema: [category, title, say_it_like_this, code, use_case, tip]
    first_card = cs["cards"][0]
    assert len(first_card) == 6
    assert "FastAPI" in first_card[2]


def test_get_cheatsheet_custom_technology_fallback():
    cs = get_cheatsheet_for_technology("Apache Kafka", target_role="Data Engineer")
    assert "Kafka" in cs["tech_name"] or cs["tech_name"] == "Apache Kafka"
    assert cs["total_cards"] >= 5
    assert len(cs["cards"][0]) == 6
    assert cs["target_role"] == "Data Engineer"


def test_tailor_cheatsheet_for_resume():
    base_cards = [
        ["Basics", "Overview", "Answer text", "code()", "Use case", "Tip text"],
        ["Q&A", "Scaling", "Scaling answer", "", "Production", "Scaling tip"],
    ]
    tailored = tailor_cheatsheet_for_resume(
        base_cards,
        resume_context="Architected 50k rpm microservice",
        target_role="Lead Architect",
        tech_name="FastAPI",
    )
    assert len(tailored) == len(base_cards)
    assert "Lead Architect" in tailored[0][5]
    assert "Resume anchor" in tailored[1][5]


def test_build_standalone_cheatsheet_html():
    cards = [
        ["Basics", "FastAPI App", "FastAPI is fast.", "app = FastAPI()", "APIs", "Keep it simple."],
        ["Requests", "Path Params", "Path parameters are in URL.", "@app.get('/{id}')", "Lookup", "Validate types."],
    ]
    html = build_standalone_cheatsheet_html("FastAPI", cards, target_role="Backend Developer")
    assert "<!doctype html>" in html
    assert "FastAPI interview cheatsheet" in html
    assert "FastAPI App" in html
    assert "app = FastAPI()" in html
    assert "Revised 0 of" in html or "id=\"pb\"" in html
    assert "Tailored for Backend Developer interviews" in html


def test_user_cheatsheet_database_crud():
    user = "test_cheatsheet_user@example.com"
    tech = "Kubernetes"
    data = {"cards": [["Basics", "Pods", "Smallest unit", "", "K8s", "Tip"]]}

    # Create / Save
    save_user_cheatsheet(user, tech, data, is_custom=True, revised_indices=[0])
    records = get_user_cheatsheets(user)
    matching = [r for r in records if r["tech_name"] == tech]
    assert len(matching) == 1
    assert matching[0]["is_custom"] is True
    assert matching[0]["revised_indices"] == [0]

    # Update revision
    update_cheatsheet_revised(user, tech, [0, 1])
    records = get_user_cheatsheets(user)
    matching = [r for r in records if r["tech_name"] == tech]
    assert matching[0]["revised_indices"] == [0, 1]

    # Delete
    delete_user_cheatsheet(user, tech)
    records = get_user_cheatsheets(user)
    matching = [r for r in records if r["tech_name"] == tech]
    assert len(matching) == 0


def test_api_interview_technologies(client):
    res = client.get("/api/interview/technologies")
    assert res.status_code == 200
    data = res.json()
    assert "resume_technologies" in data
    assert "custom_technologies" in data
    assert "saved_revised" in data
    assert len(data["resume_technologies"]) >= 1


def test_api_interview_cheatsheet(client):
    res = client.get("/api/interview/cheatsheet?tech=FastAPI")
    assert res.status_code == 200
    data = res.json()
    assert data["tech_name"] == "FastAPI"
    assert "cards" in data
    assert len(data["cards"]) >= 5
    assert "revised_indices" in data


def test_api_interview_cheatsheet_missing_tech(client):
    res = client.get("/api/interview/cheatsheet?tech=")
    assert res.status_code == 400


def test_api_interview_cheatsheet_add_custom(client):
    payload = {"tech": "Next.js"}
    res = client.post("/api/interview/cheatsheet/add", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "Next" in data["tech_name"] or data["tech_name"] == "Next.js"
    assert len(data["cards"]) >= 4


def test_api_interview_cheatsheet_delete(client):
    del_res = client.delete("/api/interview/cheatsheet?tech=Docker")
    assert del_res.status_code == 200
    data = del_res.json()
    assert data["success"] is True
    assert data["deleted"] == "Docker"

    tech_res = client.get("/api/interview/technologies")
    assert tech_res.status_code == 200
    tech_data = tech_res.json()
    assert "Docker" not in tech_data["resume_technologies"]


def test_api_interview_cheatsheet_revise(client):
    payload = {"tech": "FastAPI", "card_index": 0, "revised": True}
    res = client.post("/api/interview/cheatsheet/revise", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert 0 in data["revised_indices"]

    # Toggle off
    payload_off = {"tech": "FastAPI", "card_index": 0, "revised": False}
    res_off = client.post("/api/interview/cheatsheet/revise", json=payload_off)
    assert res_off.status_code == 200
    assert 0 not in res_off.json()["revised_indices"]


def test_interview_cheatsheet_export_html(client):
    res = client.get("/interview/cheatsheet/export?tech=FastAPI")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "attachment;" in res.headers.get("content-disposition", "")
    assert "fastapi_interview_cheatsheet.html" in res.headers.get("content-disposition", "")
    assert "<!doctype html>" in res.text


def test_interview_page_renders_cheatsheet_elements(client):
    res = client.get("/interview")
    assert res.status_code == 200
    # Tabs exist
    assert "tabBtnSimulator" in res.text
    assert "tabBtnCheatsheet" in res.text
    assert "viewCheatsheet" in res.text
    # Cheatsheet controls exist
    assert "csTechNav" in res.text
    assert "csSearch" in res.text
    assert "csExpandAll" in res.text
    assert "csCollapseAll" in res.text
    assert "csRandomCard" in res.text
    assert "csExportHtml" in res.text
    assert "csProgressFill" in res.text
    # Resume selector elements exist
    assert "iv-selected-resume" in res.text
    assert "csResumeSelect" in res.text
    # WCAG accessibility: tabs have corresponding tabpanels and labels match visible text
    assert 'role="tabpanel" aria-labelledby="tabBtnSimulator"' in res.text
    assert 'role="tabpanel" aria-labelledby="tabBtnCheatsheet"' in res.text
    assert 'aria-label="+ Upload Resume"' in res.text


def test_api_interview_resumes(client):
    res = client.get("/api/interview/resumes")
    assert res.status_code == 200
    data = res.json()
    assert "resumes" in data
    assert "selected_resume_id" in data
    assert len(data["resumes"]) >= 1
    # Verify no report review history runs clutter the dropdown
    for r in data["resumes"]:
        assert not r["id"].startswith("report_")
        assert "Review (" not in r["title"]


def test_api_interview_select_resume(client):
    # Fetch list
    list_res = client.get("/api/interview/resumes")
    assert list_res.status_code == 200
    resumes = list_res.json()["resumes"]
    first_id = resumes[0]["id"]

    # Select resume
    sel_res = client.post("/api/interview/select-resume", json={"resume_id": first_id})
    assert sel_res.status_code == 200
    sel_data = sel_res.json()
    assert sel_data["success"] is True
    assert sel_data["selected_resume_id"] == first_id
    assert "resume_technologies" in sel_data
    assert "cheatsheet" in sel_data


def test_api_interview_select_resume_invalid(client):
    res = client.post("/api/interview/select-resume", json={"resume_id": "non_existent_id_12345"})
    assert res.status_code == 404


def test_api_interview_upload_resume(client):
    # Test uploading a new text resume
    resume_content = b"""
    John Doe
    Backend Software Engineer
    Technologies: Python, FastAPI, Docker, PostgreSQL, Redis, Kubernetes
    Experience building high performance REST APIs with FastAPI and asyncpg.
    """
    files = {"file": ("my_custom_resume.txt", resume_content, "text/plain")}
    data = {"target_role": "Backend Engineer"}
    res = client.post("/api/interview/upload-resume", files=files, data=data)
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["success"] is True
    assert "my_custom_resume" in res_data["title"]
    assert "FastAPI" in res_data["resume_technologies"]
    assert "cheatsheet" in res_data
    assert res_data["selected_resume_id"]


def test_api_interview_upload_resume_empty(client):
    files = {"file": ("empty.txt", b"", "text/plain")}
    res = client.post("/api/interview/upload-resume", files=files)
    assert res.status_code == 400


def test_api_interview_upload_resume_invalid_format(client):
    files = {"file": ("malware.exe", b"binarycontent", "application/octet-stream")}
    res = client.post("/api/interview/upload-resume", files=files)
    assert res.status_code == 400


def test_interview_page_error_handling_and_toast(client):
    res = client.get("/interview")
    assert res.status_code == 200
    # Toast notification container exists
    assert 'id="ivToast"' in res.text
    assert 'role="status"' in res.text
    assert 'aria-live="polite"' in res.text
    # Heading level hierarchy valid: h2 for verdict breakdown
    assert '<h2 class="iv-verdict-heading">Question Breakdown</h2>' in res.text
    # No aria-label on span tags
    assert '<span class="cs-tech-remove" title=' not in res.text
    # Tech pills use aria-pressed, not role="tab"
    assert 'class="cs-tech-pill active" onclick="selectTechnology(\'FastAPI\', this)" aria-pressed="true"' in res.text


def test_global_exception_handler_returns_json_for_api_endpoints(client, monkeypatch):
    import routers.interview
    def broken_func(*args, **kwargs):
        raise RuntimeError("Simulated internal backend error")

    monkeypatch.setattr(routers.interview, "resolve_resume_context", broken_func)
    res = client.get("/api/interview/cheatsheet?tech=Python")
    assert res.status_code == 500
    data = res.json()
    assert "error" in data
    assert "Simulated internal backend error" in data["error"] or "Failed to load" in data["error"]


def test_interview_page_javascript_syntax_valid(client):
    import re
    import subprocess
    import tempfile

    res = client.get("/interview")
    assert res.status_code == 200
    script_match = re.search(r"<script>(.*?)</script>", res.text, re.DOTALL)
    assert script_match, "Inline script tag not found"
    js_code = script_match.group(1)

    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as tf:
        tf.write(js_code)
        tf_path = tf.name

    result = subprocess.run(["node", "-c", tf_path], capture_output=True, text=True)
    assert result.returncode == 0, f"JavaScript syntax error in interview.html: {result.stderr}"


def test_detect_technology_domain_and_deterministic_cards():
    from services.interview.cheatsheet_generator import (
        _detect_technology_domain,
        _generate_deterministic_cards,
    )

    assert _detect_technology_domain("PostgreSQL") == "database"
    assert _detect_technology_domain("MongoDB") == "database"
    assert _detect_technology_domain("Apache Kafka") == "streaming"
    assert _detect_technology_domain("Docker") == "devops"
    assert _detect_technology_domain("Kubernetes") == "devops"
    assert _detect_technology_domain("React") == "frontend"
    assert _detect_technology_domain("FastAPI") == "framework"
    assert _detect_technology_domain("Python") == "language"

    # Verify deterministic cards have real code snippets, not dummy setup = True
    db_cards = _generate_deterministic_cards("PostgreSQL", "Database Engineer")
    assert len(db_cards) >= 6
    assert any("CREATE INDEX" in c[3] or "shared_buffers" in c[3] for c in db_cards)

    kafka_cards = _generate_deterministic_cards("Kafka", "Streaming Engineer")
    assert len(kafka_cards) >= 6
    assert any("acks" in c[3] or "kafka-consumer-groups" in c[3] for c in kafka_cards)


def test_extract_project_talking_points_dynamic():
    from services.interview.cheatsheet_generator import extract_project_talking_points_for_tech

    sample_resume = """
    # Experience
    ### Acme Corp - Senior Infrastructure Engineer
    - Architected Kubernetes clusters across 3 regions serving 40k req/sec with sub-second response times.
    - Automated Docker container deployments using GitHub Actions pipelines.

    ### Beta Labs - Distributed Systems Architect
    - Built real-time Apache Kafka streaming ingestion pipelines processing 500GB daily.
    """
    pts = extract_project_talking_points_for_tech(sample_resume, "Kubernetes")
    assert len(pts) >= 1
    assert "Acme Corp" in pts[0]["context"]
    assert "Kubernetes clusters" in pts[0]["point"]

    kafka_pts = extract_project_talking_points_for_tech(sample_resume, "Kafka")
    assert len(kafka_pts) >= 1
    assert "Beta Labs" in kafka_pts[0]["context"]
    assert "Apache Kafka" in kafka_pts[0]["point"]


def test_interview_page_tab_accessibility_attributes(client):
    res = client.get("/interview")
    assert res.status_code == 200
    html = res.text
    # Tabs have tabindex and aria-controls
    assert 'id="tabBtnSimulator" role="tab" aria-selected="true" aria-controls="viewSimulator" tabindex="0"' in html
    assert 'id="tabBtnCheatsheet" role="tab" aria-selected="false" aria-controls="viewCheatsheet" tabindex="-1"' in html
    # Tabpanels have role="tabpanel" and tabindex="0"
    assert 'id="viewSimulator" class="iv-view-pane active" role="tabpanel" aria-labelledby="tabBtnSimulator" tabindex="0"' in html
    assert 'id="viewCheatsheet" class="iv-view-pane" role="tabpanel" aria-labelledby="tabBtnCheatsheet" tabindex="0"' in html



