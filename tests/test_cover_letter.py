import sys
import json
import time
from fastapi.testclient import TestClient
import db_backend as db

def _setup_tables():
    from core import app, hash_password, init_resume_tables
    conn = db.get_conn()
    cur = conn.cursor()
    id_col = db.id_pk_col()
    db.execute(cur, f"CREATE TABLE IF NOT EXISTS users (id {id_col}, full_name TEXT, email TEXT UNIQUE, password_hash TEXT, role TEXT, plan TEXT, password_updated_ts INTEGER, created_ts INTEGER)")
    db.execute(cur, "DELETE FROM users WHERE email IN ('cl_owner@example.com', 'cl_foreign@example.com')")
    
    # Owner
    db.execute(cur, "INSERT INTO users(full_name,email,password_hash,role,plan,password_updated_ts,created_ts) VALUES(?,?,?,?,?,?,?)",
        ("CL Owner", "cl_owner@example.com", hash_password("Password123"), "user", "free", int(time.time()), int(time.time())))
    # Foreign
    db.execute(cur, "INSERT INTO users(full_name,email,password_hash,role,plan,password_updated_ts,created_ts) VALUES(?,?,?,?,?,?,?)",
        ("CL Foreign", "cl_foreign@example.com", hash_password("Password123"), "user", "free", int(time.time()), int(time.time())))
    conn.commit()
    conn.close()
    init_resume_tables()

_setup_tables()

from main import app
client = TestClient(app)

def get_auth_client(email="cl_owner@example.com"):
    resp = client.post("/login", data={"email": email, "password": "Password123", "website": ""}, follow_redirects=False)
    assert resp.status_code in (302, 303)
    return client

def seed_report():
    conn = db.get_conn()
    cur = conn.cursor()
    rep_json = {
        "scores": {"Overall": 7.5, "Skills": 8.0},
        "keyword_gaps": ["Python", "FastAPI"],
        "resume_text": "Experienced Python developer working with Flask for 3 years.",
        "jd_text": "Looking for a Python Developer proficient in FastAPI and SQLite to build scalable APIs."
    }
    db.execute(cur, "INSERT INTO resume_reports (user_email, target_role, overall, ats, keyword_coverage, status, report_json, created_ts) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("cl_owner@example.com", "Python Developer", 7.5, 7.0, 75, "Good", json.dumps(rep_json), int(time.time())))
    conn.commit()
    db.execute(cur, "SELECT id FROM resume_reports WHERE user_email='cl_owner@example.com' ORDER BY id DESC LIMIT 1")
    report_id = cur.fetchone()[0]
    conn.close()
    return report_id

def test_cover_letter_post_cached():
    print("Testing POST /resume/{id}/cover_letter cached generation...")
    report_id = seed_report()
    c = get_auth_client()
    
    # 1. Trigger Generation
    post_res = c.post(f"/resume/{report_id}/cover_letter", follow_redirects=False)
    assert post_res.status_code in (302, 303)
    assert f"/resume/{report_id}/cover_letter" in post_res.headers.get("location")
    
    # 2. View Cache
    get_res = c.get(f"/resume/{report_id}/cover_letter")
    assert get_res.status_code == 200
    assert "Your Cover Letter" in get_res.text
    assert "Copy to Clipboard" in get_res.text
    print("✅ Passed - POST cached redirects correctly")

def test_cover_letter_foreign_block():
    print("Testing foreign user block for cover letter view...")
    report_id = seed_report()
    c_foreign = get_auth_client("cl_foreign@example.com")
    
    res = c_foreign.get(f"/resume/{report_id}/cover_letter")
    assert res.status_code == 404 # Non-enumerated Access denied
    print("✅ Passed - Cover letter foreign block restricted")

def test_cover_letter_unauthenticated():
    print("Testing unauthenticated redirects...")
    report_id = seed_report()
    anon_client = TestClient(app)
    res = anon_client.get(f"/resume/{report_id}/cover_letter", follow_redirects=False)
    assert res.status_code in (302, 303)
    print("✅ Passed - unauthenticated redirects")

def seed_report_with_overrides(keyword_gaps=None, jd_text=""):
    conn = db.get_conn()
    cur = conn.cursor()
    rep_json = {
        "scores": {"Overall": 7.5, "Skills": 8.0},
        "keyword_gaps": keyword_gaps if keyword_gaps is not None else ["Python", "FastAPI"],
        "resume_text": "Experienced Python developer working with Flask for 3 years.",
        "jd_text": jd_text
    }
    db.execute(cur, "INSERT INTO resume_reports (user_email, target_role, overall, ats, keyword_coverage, status, report_json, created_ts) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("cl_owner@example.com", "Python Developer", 7.5, 7.0, 75, "Good", json.dumps(rep_json), int(time.time())))
    conn.commit()
    db.execute(cur, "SELECT id FROM resume_reports WHERE user_email='cl_owner@example.com' ORDER BY id DESC LIMIT 1")
    report_id = cur.fetchone()[0]
    conn.close()
    return report_id

def test_cover_letter_empty_gaps():
    print("Testing cover letter with empty keyword gaps...")
    report_id = seed_report_with_overrides(keyword_gaps=[], jd_text="Required Python Flask APIs.")
    c = get_auth_client()
    
    post_res = c.post(f"/resume/{report_id}/cover_letter", follow_redirects=False)
    assert post_res.status_code in (302, 303)
    
    get_res = c.get(f"/resume/{report_id}/cover_letter")
    assert get_res.status_code == 200
    print("✅ Passed - empty gaps handled")

def test_cover_letter_empty_jd():
    print("Testing cover letter with empty JD (Warning banner test)...")
    report_id = seed_report_with_overrides(jd_text="")
    c = get_auth_client()
    
    post_res = c.post(f"/resume/{report_id}/cover_letter", follow_redirects=False)
    assert post_res.status_code in (302, 303)
    
    get_res = c.get(f"/resume/{report_id}/cover_letter")
    assert get_res.status_code == 200
    assert "Empty or generic Job Description" in get_res.text
    print("✅ Passed - empty JD banner triggers")

def test_cover_letter_hallucination_audit():
    print("Testing cover letter for hallucinated non-present entities...")
    report_id = seed_report_with_overrides()
    c = get_auth_client()
    
    # 1. Trigger Generate
    c.post(f"/resume/{report_id}/cover_letter")
    
    # 2. Inspect DB Cache directly instead of HTML Layout wrapper (avoids layout.html font false-positives)
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, "SELECT report_json FROM resume_reports WHERE id=?", (report_id,))
    row = cur.fetchone()
    conn.close()
    
    report_data = json.loads(row[0] or "{}")
    text = report_data.get("cover_letter_text", "").lower()
    
    assert text.strip() != "", "Cover letter is empty"
    
    hallucination_list = ["google", "facebook", "amazon", "microsoft"]
    for word in hallucination_list:
        assert word not in text, f"Potential Hallucination: Found {word}"
    print("✅ Passed - hallucination audit clean")

if __name__ == "__main__":
    try:
        test_cover_letter_post_cached()
        test_cover_letter_empty_gaps()
        test_cover_letter_empty_jd()
        test_cover_letter_hallucination_audit()
        test_cover_letter_foreign_block()
        test_cover_letter_unauthenticated()
        print("\n🎉 All Cover Letter Verification Tests Passed!")
        sys.exit(0)
    except AssertionError:
        import traceback
        print("\n❌ Test Failed:")
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Execution Error: {e}")
        sys.exit(1)
