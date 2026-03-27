from pathlib import Path

from db import backend as db
from features.coding import platform as coding_platform


def _set_temp_sqlite(tmp_path: Path) -> Path:
    db_path = tmp_path / "coding_features.db"
    db.DATABASE_URL = ""
    db.SQLITE_PATH = str(db_path)
    db._USE_SQLITE_FALLBACK = True
    coding_platform.reset_submission_ts_cache()
    coding_platform.init_coding_tables()
    return db_path


def test_judge_queue_and_timeline(tmp_path):
    _set_temp_sqlite(tmp_path)
    code = (
        "def solve(input_data: str) -> str:\n"
        "    s = input_data.strip()\n"
        "    return s[::-1]\n"
    )
    job_id = coding_platform.enqueue_judge_job(
        user_email="u@example.com",
        problem_id="reverse-string",
        language="python",
        mode="submit",
        code_text=code,
    )
    out = coding_platform.process_judge_job(job_id)
    assert out["ok"] is True

    job = coding_platform.get_judge_job(job_id, "u@example.com")
    assert job["status"] == "completed"
    assert (job.get("result") or {}).get("status") == "Accepted"

    timeline = coding_platform.get_problem_timeline("u@example.com", "reverse-string", limit=5)
    assert timeline
    assert timeline[0]["mode"] == "submit"
    assert timeline[0]["status"] == "Accepted"


def test_daily_goal_mastery_and_queue(tmp_path):
    _set_temp_sqlite(tmp_path)
    code = (
        "def solve(input_data: str) -> str:\n"
        "    n = int(input_data.strip())\n"
        "    out = []\n"
        "    for i in range(1, n+1):\n"
        "        if i % 15 == 0:\n"
        "            out.append('FizzBuzz')\n"
        "        elif i % 3 == 0:\n"
        "            out.append('Fizz')\n"
        "        elif i % 5 == 0:\n"
        "            out.append('Buzz')\n"
        "        else:\n"
        "            out.append(str(i))\n"
        "    return '\\n'.join(out)\n"
    )
    result = coding_platform.evaluate_submission(
        coding_platform.get_problem("fizzbuzz"),
        code,
        language="python",
        mode="submit",
    )
    coding_platform.save_submission(
        problem_id="fizzbuzz",
        language="python",
        mode="submit",
        status=result["status"],
        passed=result["passed"],
        total=result["total"],
        runtime_ms=result["runtime_ms"],
        user_email="u@example.com",
    )
    coding_platform.save_attempt_timeline(
        problem_id="fizzbuzz",
        language="python",
        mode="submit",
        status=result["status"],
        passed=result["passed"],
        total=result["total"],
        runtime_ms=result["runtime_ms"],
        code=code,
        user_email="u@example.com",
        result=result,
    )
    coding_platform.save_attempt_timeline(
        problem_id="fizzbuzz",
        language="python",
        mode="hint",
        status="Hint Viewed",
        passed=0,
        total=0,
        runtime_ms=0.0,
        code=code,
        user_email="u@example.com",
        result={},
    )

    daily = coding_platform.daily_goal_progress("u@example.com")
    assert daily["accepted_today"] >= 1
    assert daily["review_today"] >= 1

    mastery = coding_platform.topic_mastery_report("u@example.com")
    assert mastery

    queue = coding_platform.personalized_practice_queue("u@example.com", current_problem_id="fizzbuzz", limit=5)
    assert queue
    assert all(item["id"] != "fizzbuzz" for item in queue)


def test_contest_snapshot_available(tmp_path):
    _set_temp_sqlite(tmp_path)
    snap = coding_platform.contest_snapshot("u@example.com", limit=5)
    assert snap["contest"]["problem_ids"]
    assert "leaderboard" in snap
