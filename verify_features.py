import sys
import os
import json
import uuid
import time
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import core
from db import backend as db
from routers.pages import api_interview_progress

class MockSessionRequest:
    def __init__(self, email):
        self.session = {"user_email": email}

def verify():
    print("--- Starting Verification ---\n")
    conn = db.get_conn()
    cur = conn.cursor()
    
    # Setup
    core._ensure_interview_tables()
    test_email = "testverif@example.com"
    other_email = "otheruser@example.com"
    cur.execute("DELETE FROM interview_sessions WHERE user_email IN (?, ?)", (test_email, other_email))
    conn.commit()

    print("Testing Feature 1 & 2: Weakness Tracking & Isolation")
    
    weaknesses = core.get_user_weaknesses(test_email)
    print(f"[TEST] 0 prior sessions -> weaknesses: {weaknesses}")
    assert len(weaknesses) == 0, "Should be empty"

    session_1 = str(uuid.uuid4())
    qa_1 = [
        {"round": 1, "question": "What is a load balancer?", "user_answer": "I don't know", "ideal_answer": "It distributes traffic.", "score": 4.0, "feedback": "Study system design load balancing."}
    ]
    cur.execute("INSERT INTO interview_sessions (id, session_id, user_email, topic, difficulty, overall_score, qa_history_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                (db.new_id(), session_1, test_email, "System Design", "intermediate", 4.0, json.dumps(qa_1), int(time.time()*1000)))
    conn.commit()

    weaknesses = core.get_user_weaknesses(test_email)
    print(f"[TEST] After bad session -> weaknesses: {weaknesses}")
    assert len(weaknesses) == 1
    assert "Study system design load balancing" in weaknesses[0]

    other_weaknesses = core.get_user_weaknesses(other_email)
    print(f"[TEST] Weakness data scoped per user -> User B weaknesses: {other_weaknesses}")
    assert len(other_weaknesses) == 0, "Weakness leaked to other user!"

    print("\nTesting Feature 3: Progress Dashboard")
    
    other_req = MockSessionRequest(other_email)
    res = api_interview_progress(other_req, conn)
    data = json.loads(res.body)
    print(f"[TEST] /api/interview-progress with 0 sessions -> returns count: {len(data)}")
    assert len(data) == 0

    for i in range(12):
        sid = str(uuid.uuid4())
        cur.execute("INSERT INTO interview_sessions (id, session_id, user_email, topic, difficulty, overall_score, qa_history_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                    (db.new_id(), sid, test_email, "System Design", "intermediate", 5.0 + (i*0.2), "[]", int(time.time()*1000) + i*1000))
    conn.commit()

    test_req = MockSessionRequest(test_email)
    res = api_interview_progress(test_req, conn)
    data = json.loads(res.body)
    print(f"[TEST] /api/interview-progress with 10+ data points -> returns count: {len(data)}")
    assert len(data) == 13

    cur.execute("DELETE FROM interview_sessions WHERE user_email IN (?, ?)", (test_email, other_email))
    conn.commit()

    print("\n✅ All programmatic backend verifications passed successfully!")

if __name__ == "__main__":
    verify()
