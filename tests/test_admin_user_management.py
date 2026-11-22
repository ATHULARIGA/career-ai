import pytest
from starlette.requests import Request
from core.security import is_admin_session
from services.analytics.admin_analytics import (
    get_admin_users_list,
    update_user_role,
    dashboard_payload,
)
import db.backend as db


def test_is_admin_session():
    class DummyRequest:
        def __init__(self, session_data):
            self.session = session_data

    # Legacy admin session flag
    req1 = DummyRequest({"admin": True})
    assert is_admin_session(req1) is True

    # Database admin role in user session
    req2 = DummyRequest({"user_role": "admin"})
    assert is_admin_session(req2) is True

    # Standard candidate role
    req3 = DummyRequest({"user_role": "user", "admin": False})
    assert is_admin_session(req3) is False

    # Empty session
    req4 = DummyRequest({})
    assert is_admin_session(req4) is False


def test_admin_analytics_payload_structure():
    payload = dashboard_payload([])
    assert "user_stats" in payload
    assert "conv_rates" in payload
    assert "conv_classes" in payload
    assert "tool_share" in payload
    assert "tool_classes" in payload
    assert "user_tier_share" in payload
    assert "user_tier_classes" in payload
    assert "activity_trend" in payload
    assert len(payload["activity_trend"]) == 7


def test_admin_user_role_management():
    # Insert a dummy user to test role management
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, """
        INSERT INTO users (full_name, email, password_hash, role, plan, created_ts)
        VALUES ('Test Candidate', 'test_candidate_admin_mgmt@example.com', 'hash', 'user', 'free', 1700000000)
    """)
    conn.commit()
    user_id = cur.lastrowid
    conn.close()

    try:
        # Verify user is listed
        users = get_admin_users_list(search="test_candidate_admin_mgmt")
        assert len(users) >= 1
        target = next(u for u in users if u["email"] == "test_candidate_admin_mgmt@example.com")
        assert target["role"] == "user"

        # Promote user to admin
        ok, msg = update_user_role(user_id, "admin", actor="root_admin@example.com")
        assert ok is True

        # Check updated role
        users_after = get_admin_users_list(search="test_candidate_admin_mgmt")
        target_after = next(u for u in users_after if u["email"] == "test_candidate_admin_mgmt@example.com")
        assert target_after["role"] == "admin"

        # Revoke admin back to user
        ok_revoke, _ = update_user_role(user_id, "user", actor="root_admin@example.com")
        assert ok_revoke is True

        # Test invalid role
        ok_invalid, err_msg = update_user_role(user_id, "super_god_mode", actor="root_admin@example.com")
        assert ok_invalid is False
        assert "Invalid role" in err_msg

    finally:
        # Clean up dummy user
        c = db.get_conn()
        cur_c = c.cursor()
        db.execute(cur_c, "DELETE FROM users WHERE id = ?", (user_id,))
        c.commit()
        c.close()
