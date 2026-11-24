import os
import urllib.parse
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import db.backend as db
from main import app

client = TestClient(app)


def test_google_auth_redirect_when_not_configured():
    with patch.dict(os.environ, {"GOOGLE_CLIENT_ID": ""}):
        resp = client.get("/auth/google", follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert "/login" in resp.headers.get("location", "")
        assert "not+configured" in resp.headers.get("location", "")


def test_google_auth_initiates_oauth_flow():
    with patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "test-client-id-123.apps.googleusercontent.com"}):
        resp = client.get("/auth/google", follow_redirects=False)
        assert resp.status_code in (302, 303)
        location = resp.headers.get("location", "")
        assert "accounts.google.com/o/oauth2/v2/auth" in location
        assert "client_id=test-client-id-123.apps.googleusercontent.com" in location
        assert "scope=" in location
        assert "state=" in location


def test_google_callback_rejects_state_mismatch():
    with patch.dict(os.environ, {
        "GOOGLE_CLIENT_ID": "test-client-id",
        "GOOGLE_CLIENT_SECRET": "test-client-secret"
    }):
        resp = client.get("/auth/google/callback?code=fake_code&state=bad_state", follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert "/login" in resp.headers.get("location", "")
        assert "Invalid+or+expired" in resp.headers.get("location", "")


def test_google_callback_handles_user_cancellation():
    resp = client.get("/auth/google/callback?error=access_denied", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/login" in resp.headers.get("location", "")
    assert "cancelled" in resp.headers.get("location", "")


def test_google_callback_registers_new_user_and_logs_in():
    test_email = "test.google.signup@example.com"
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, "DELETE FROM users WHERE email=?", (test_email,))
    conn.commit()
    conn.close()

    mock_token_resp = MagicMock()
    mock_token_resp.status_code = 200
    mock_token_resp.json.return_value = {"access_token": "fake_google_access_token"}

    mock_userinfo_resp = MagicMock()
    mock_userinfo_resp.status_code = 200
    mock_userinfo_resp.json.return_value = {
        "email": test_email,
        "name": "Google Test Candidate",
        "sub": "google-1234567890",
    }

    with patch.dict(os.environ, {
        "GOOGLE_CLIENT_ID": "mock-client-id",
        "GOOGLE_CLIENT_SECRET": "mock-client-secret"
    }), patch("requests.post", return_value=mock_token_resp), patch("requests.get", return_value=mock_userinfo_resp):
        # 1. Initiate to seed session state
        init_resp = client.get("/auth/google", follow_redirects=False)
        loc = init_resp.headers.get("location", "")
        parsed = urllib.parse.urlparse(loc)
        q = urllib.parse.parse_qs(parsed.query)
        state = q["state"][0]

        # 2. Callback with valid state and code
        cb_resp = client.get(f"/auth/google/callback?code=mock_auth_code&state={state}", follow_redirects=False)
        assert cb_resp.status_code in (302, 303)
        assert "/?auth=success" in cb_resp.headers.get("location", "")

        # 3. Verify user was created in database
        conn = db.get_conn()
        cur = conn.cursor()
        db.execute(cur, "SELECT id, full_name, email, role, plan, auth_provider FROM users WHERE email=?", (test_email,))
        row = cur.fetchone()
        conn.close()

        assert row is not None
        assert row[1] == "Google Test Candidate"
        assert row[2] == test_email
        assert row[3] == "user"
        assert row[4] == "free"
        assert row[5] == "google"


def test_google_callback_logs_in_existing_user():
    existing_email = "existing.google.user@example.com"
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, "DELETE FROM users WHERE email=?", (existing_email,))
    db.execute(cur,
        "INSERT INTO users(full_name, email, password_hash, role, plan, created_ts) VALUES(?,?,?,?,?,?)",
        ("Existing User", existing_email, "hash123", "user", "premium", 1700000000)
    )
    conn.commit()
    conn.close()

    mock_token_resp = MagicMock()
    mock_token_resp.status_code = 200
    mock_token_resp.json.return_value = {"access_token": "fake_google_access_token"}

    mock_userinfo_resp = MagicMock()
    mock_userinfo_resp.status_code = 200
    mock_userinfo_resp.json.return_value = {
        "email": existing_email,
        "name": "Existing User From Google",
    }

    with patch.dict(os.environ, {
        "GOOGLE_CLIENT_ID": "mock-client-id",
        "GOOGLE_CLIENT_SECRET": "mock-client-secret"
    }), patch("requests.post", return_value=mock_token_resp), patch("requests.get", return_value=mock_userinfo_resp):
        init_resp = client.get("/auth/google", follow_redirects=False)
        parsed = urllib.parse.urlparse(init_resp.headers.get("location", ""))
        state = urllib.parse.parse_qs(parsed.query)["state"][0]

        cb_resp = client.get(f"/auth/google/callback?code=mock_code&state={state}", follow_redirects=False)
        assert cb_resp.status_code in (302, 303)

        # Confirm no duplicate created and existing plan kept
        conn = db.get_conn()
        cur = conn.cursor()
        db.execute(cur, "SELECT COUNT(*), plan, auth_provider FROM users WHERE email=?", (existing_email,))
        row = cur.fetchone()
        conn.close()

        assert row[0] == 1
        assert row[1] == "premium"
        assert row[2] == "google"
