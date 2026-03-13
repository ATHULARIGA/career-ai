import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import csv
import io
import hashlib
import re
from typing import Any, Dict, List, Tuple
import db_backend as db

DB_PATH = "bookings.db"
_SUBMISSION_TS_COL_CACHE: str = ""
_SUBMISSION_TS_CACHE_READY: bool = False
_SUBMISSION_TS_WARNED: bool = False

SUPPORTED_LANGUAGES = ("python", "java", "cpp", "javascript")
DIFFICULTIES = ("Easy", "Medium", "Hard")

GENERIC_STARTERS = {
    "python": "def solve(input_data: str) -> str:\n    # Parse input_data and return output string\n    return \"\"\n",
    "javascript": "function solve(inputData) {\n  // Parse inputData and return output string\n  return \"\";\n}\n",
    "java": "import java.util.*;\n\npublic class Solution {\n  public static String solve(String inputData) {\n    // Parse inputData and return output string\n    return \"\";\n  }\n}\n",
    "cpp": "#include <bits/stdc++.h>\nusing namespace std;\n\nstring solve(const string& inputData) {\n    // Parse inputData and return output string\n    return \"\";\n}\n",
}


DEFAULT_PROBLEMS: List[Dict[str, Any]] = [
    {
        "id": "fizzbuzz",
        "title": "FizzBuzz Stream",
        "difficulty": "Easy",
        "acceptance_rate": 87.1,
        "tags": ["Math", "Simulation"],
        "constraints": ["1 <= n <= 10^5"],
        "examples": [
            {"input": "5", "output": "1\\n2\\nFizz\\n4\\nBuzz"},
            {"input": "3", "output": "1\\n2\\nFizz"},
        ],
        "description": (
            "Given an integer n in input, print numbers 1..n. "
            "For multiples of 3 print Fizz, for 5 print Buzz, for both print FizzBuzz. "
            "Return lines joined by newline."
        ),
        "starter_codes": {
            "python": "def solve(input_data: str) -> str:\n    n = int(input_data.strip())\n    # Write your solution here\n    return \"\"\n",
            "javascript": "function solve(inputData) {\n  const n = parseInt(inputData.trim(), 10);\n  // Write your solution here\n  return \"\";\n}\n",
            "java": "import java.util.*;\n\npublic class Solution {\n  public static String solve(String inputData) {\n    int n = Integer.parseInt(inputData.trim());\n    // Write your solution here\n    return \"\";\n  }\n}\n",
            "cpp": "#include <bits/stdc++.h>\nusing namespace std;\n\nstring solve(const string& inputData) {\n    // Write your solution here\n    return \"\";\n}\n",
        },
        "sample_tests": [
            {"input": "5", "expected": "1\n2\nFizz\n4\nBuzz"},
            {"input": "3", "expected": "1\n2\nFizz"},
        ],
        "hidden_tests": [
            {"input": "15", "expected": "1\n2\nFizz\n4\nBuzz\nFizz\n7\n8\nFizz\nBuzz\n11\nFizz\n13\n14\nFizzBuzz"},
        ],
    },
    {
        "id": "two-sum-indices",
        "title": "Two Sum Indices",
        "difficulty": "Easy",
        "acceptance_rate": 74.6,
        "tags": ["Array", "Hash Map"],
        "constraints": [
            "2 <= n <= 10^5",
            "-10^9 <= nums[i] <= 10^9",
            "Exactly one valid answer",
        ],
        "examples": [
            {"input": "2 7 11 15\\n9", "output": "0 1"},
            {"input": "3 2 4\\n6", "output": "1 2"},
        ],
        "description": (
            "Input format: first line has integers array space-separated, second line has target. "
            "Return index pair i,j (0-based) as 'i j' where nums[i] + nums[j] = target."
        ),
        "starter_codes": {
            "python": "def solve(input_data: str) -> str:\n    lines = [x.strip() for x in input_data.strip().splitlines() if x.strip()]\n    nums = list(map(int, lines[0].split()))\n    target = int(lines[1])\n    # Write your solution here\n    return \"\"\n",
            "javascript": "function solve(inputData) {\n  const lines = inputData.trim().split(/\\n+/).map(s => s.trim()).filter(Boolean);\n  const nums = lines[0].split(/\\s+/).map(Number);\n  const target = Number(lines[1]);\n  // Write your solution here\n  return \"\";\n}\n",
            "java": "import java.util.*;\n\npublic class Solution {\n  public static String solve(String inputData) {\n    String[] lines = inputData.trim().split(\"\\\\n+\");\n    String[] parts = lines[0].trim().split(\"\\\\s+\");\n    int[] nums = new int[parts.length];\n    for (int i = 0; i < parts.length; i++) nums[i] = Integer.parseInt(parts[i]);\n    int target = Integer.parseInt(lines[1].trim());\n    // Write your solution here\n    return \"\";\n  }\n}\n",
            "cpp": "#include <bits/stdc++.h>\nusing namespace std;\n\nstring solve(const string& inputData) {\n    // Write your solution here\n    return \"\";\n}\n",
        },
        "sample_tests": [
            {"input": "2 7 11 15\n9", "expected": "0 1"},
            {"input": "3 2 4\n6", "expected": "1 2"},
        ],
        "hidden_tests": [
            {"input": "3 3\n6", "expected": "0 1"},
        ],
    },
    {
        "id": "valid-parentheses",
        "title": "Valid Parentheses",
        "difficulty": "Medium",
        "acceptance_rate": 62.4,
        "tags": ["Stack", "String"],
        "constraints": ["1 <= len(s) <= 10^5", "s contains only ()[]{}"],
        "examples": [
            {"input": "()[]{}", "output": "true"},
            {"input": "(]", "output": "false"},
        ],
        "description": "Input is a single string of brackets. Return 'true' if valid and balanced, else 'false'.",
        "starter_codes": {
            "python": "def solve(input_data: str) -> str:\n    s = input_data.strip()\n    # Write your solution here\n    return \"\"\n",
            "javascript": "function solve(inputData) {\n  const s = inputData.trim();\n  // Write your solution here\n  return \"\";\n}\n",
            "java": "import java.util.*;\n\npublic class Solution {\n  public static String solve(String inputData) {\n    String s = inputData.trim();\n    // Write your solution here\n    return \"\";\n  }\n}\n",
            "cpp": "#include <bits/stdc++.h>\nusing namespace std;\n\nstring solve(const string& inputData) {\n    string s = inputData;\n    // Write your solution here\n    return \"\";\n}\n",
        },
        "sample_tests": [
            {"input": "()[]{}", "expected": "true"},
            {"input": "(]", "expected": "false"},
        ],
        "hidden_tests": [
            {"input": "([{}])", "expected": "true"},
            {"input": "(((", "expected": "false"},
        ],
    },
    {
        "id": "reverse-string",
        "title": "Reverse String",
        "difficulty": "Easy",
        "acceptance_rate": 89.4,
        "tags": ["String", "Two Pointers"],
        "constraints": ["1 <= len(s) <= 10^5"],
        "examples": [{"input": "career", "output": "reerac"}],
        "description": "Input is one line string s. Return s reversed.",
        "starter_codes": dict(GENERIC_STARTERS),
        "sample_tests": [{"input": "hello", "expected": "olleh"}],
        "hidden_tests": [{"input": "abcd", "expected": "dcba"}],
    },
    {
        "id": "palindrome-check",
        "title": "Palindrome Check",
        "difficulty": "Easy",
        "acceptance_rate": 84.2,
        "tags": ["String"],
        "constraints": ["1 <= len(s) <= 10^5"],
        "examples": [{"input": "madam", "output": "true"}],
        "description": "Input is one string s. Return true if palindrome else false.",
        "starter_codes": dict(GENERIC_STARTERS),
        "sample_tests": [{"input": "level", "expected": "true"}],
        "hidden_tests": [{"input": "hello", "expected": "false"}],
    },
    {
        "id": "max-of-three",
        "title": "Maximum of Three Numbers",
        "difficulty": "Easy",
        "acceptance_rate": 92.1,
        "tags": ["Math"],
        "constraints": ["-10^9 <= a,b,c <= 10^9"],
        "examples": [{"input": "2 9 5", "output": "9"}],
        "description": "Input has three integers a b c. Return the maximum value.",
        "starter_codes": dict(GENERIC_STARTERS),
        "sample_tests": [{"input": "2 9 5", "expected": "9"}],
        "hidden_tests": [{"input": "-1 -4 -3", "expected": "-1"}],
    },
    {
        "id": "sum-array",
        "title": "Sum of Array",
        "difficulty": "Easy",
        "acceptance_rate": 90.7,
        "tags": ["Array"],
        "constraints": ["1 <= n <= 10^5"],
        "examples": [{"input": "1 2 3 4", "output": "10"}],
        "description": "Input is space-separated integers. Return total sum.",
        "starter_codes": dict(GENERIC_STARTERS),
        "sample_tests": [{"input": "1 2 3 4", "expected": "10"}],
        "hidden_tests": [{"input": "5 5 5", "expected": "15"}],
    },
    {
        "id": "count-vowels",
        "title": "Count Vowels",
        "difficulty": "Easy",
        "acceptance_rate": 83.5,
        "tags": ["String"],
        "constraints": ["1 <= len(s) <= 10^5"],
        "examples": [{"input": "education", "output": "5"}],
        "description": "Input is one line string. Return number of vowels (a,e,i,o,u).",
        "starter_codes": dict(GENERIC_STARTERS),
        "sample_tests": [{"input": "hello", "expected": "2"}],
        "hidden_tests": [{"input": "rhythm", "expected": "0"}],
    },
    {
        "id": "factorial-number",
        "title": "Factorial Number",
        "difficulty": "Easy",
        "acceptance_rate": 79.8,
        "tags": ["Math", "Recursion"],
        "constraints": ["0 <= n <= 12"],
        "examples": [{"input": "5", "output": "120"}],
        "description": "Input integer n. Return n! as integer string.",
        "starter_codes": dict(GENERIC_STARTERS),
        "sample_tests": [{"input": "5", "expected": "120"}],
        "hidden_tests": [{"input": "0", "expected": "1"}],
    },
    {
        "id": "fibonacci-nth",
        "title": "Nth Fibonacci",
        "difficulty": "Easy",
        "acceptance_rate": 74.9,
        "tags": ["DP", "Math"],
        "constraints": ["0 <= n <= 40"],
        "examples": [{"input": "7", "output": "13"}],
        "description": "Input n. Return nth Fibonacci with F(0)=0, F(1)=1.",
        "starter_codes": dict(GENERIC_STARTERS),
        "sample_tests": [{"input": "7", "expected": "13"}],
        "hidden_tests": [{"input": "10", "expected": "55"}],
    },
    {
        "id": "binary-search-index",
        "title": "Binary Search Index",
        "difficulty": "Easy",
        "acceptance_rate": 71.5,
        "tags": ["Binary Search", "Array"],
        "constraints": ["Sorted array"],
        "examples": [{"input": "1 3 5 7 9\n7", "output": "3"}],
        "description": "Line1 sorted nums, line2 target. Return index or -1.",
        "starter_codes": dict(GENERIC_STARTERS),
        "sample_tests": [{"input": "1 3 5 7 9\n7", "expected": "3"}],
        "hidden_tests": [{"input": "1 2 4 8\n3", "expected": "-1"}],
    },
    {
        "id": "merge-two-sorted",
        "title": "Merge Two Sorted Arrays",
        "difficulty": "Medium",
        "acceptance_rate": 68.8,
        "tags": ["Array", "Two Pointers"],
        "constraints": ["Input has two lines of sorted integers"],
        "examples": [{"input": "1 3 5\n2 4 6", "output": "1 2 3 4 5 6"}],
        "description": "Merge two sorted arrays and return sorted merged list space-separated.",
        "starter_codes": dict(GENERIC_STARTERS),
        "sample_tests": [{"input": "1 3 5\n2 4 6", "expected": "1 2 3 4 5 6"}],
        "hidden_tests": [{"input": "1 2 2\n2 2 3", "expected": "1 2 2 2 2 3"}],
    },
    {
        "id": "move-zeroes",
        "title": "Move Zeroes",
        "difficulty": "Easy",
        "acceptance_rate": 72.9,
        "tags": ["Array", "Two Pointers"],
        "constraints": ["1 <= n <= 10^5"],
        "examples": [{"input": "0 1 0 3 12", "output": "1 3 12 0 0"}],
        "description": "Move all zeroes to end preserving non-zero order.",
        "starter_codes": dict(GENERIC_STARTERS),
        "sample_tests": [{"input": "0 1 0 3 12", "expected": "1 3 12 0 0"}],
        "hidden_tests": [{"input": "0 0 1", "expected": "1 0 0"}],
    },
    {
        "id": "anagram-check",
        "title": "Valid Anagram",
        "difficulty": "Easy",
        "acceptance_rate": 80.2,
        "tags": ["Hash Map", "String"],
        "constraints": ["lowercase english letters"],
        "examples": [{"input": "anagram\nnagaram", "output": "true"}],
        "description": "Two lines s and t. Return true if anagrams else false.",
        "starter_codes": dict(GENERIC_STARTERS),
        "sample_tests": [{"input": "anagram\nnagaram", "expected": "true"}],
        "hidden_tests": [{"input": "rat\ncar", "expected": "false"}],
    },
    {
        "id": "first-unique-char",
        "title": "First Unique Character",
        "difficulty": "Easy",
        "acceptance_rate": 66.1,
        "tags": ["Hash Map", "String"],
        "constraints": ["1 <= len(s) <= 10^5"],
        "examples": [{"input": "leetcode", "output": "0"}],
        "description": "Return index of first non-repeating char, else -1.",
        "starter_codes": dict(GENERIC_STARTERS),
        "sample_tests": [{"input": "leetcode", "expected": "0"}],
        "hidden_tests": [{"input": "aabb", "expected": "-1"}],
    },
    {
        "id": "longest-common-prefix",
        "title": "Longest Common Prefix",
        "difficulty": "Easy",
        "acceptance_rate": 64.9,
        "tags": ["String"],
        "constraints": ["Input: words space-separated in one line"],
        "examples": [{"input": "flower flow flight", "output": "fl"}],
        "description": "Return longest common prefix among given words.",
        "starter_codes": dict(GENERIC_STARTERS),
        "sample_tests": [{"input": "flower flow flight", "expected": "fl"}],
        "hidden_tests": [{"input": "dog racecar car", "expected": ""}],
    },
    {
        "id": "product-except-self",
        "title": "Product of Array Except Self",
        "difficulty": "Medium",
        "acceptance_rate": 58.7,
        "tags": ["Array", "Prefix"],
        "constraints": ["No division"],
        "examples": [{"input": "1 2 3 4", "output": "24 12 8 6"}],
        "description": "Return array where each index has product of all other elements.",
        "starter_codes": dict(GENERIC_STARTERS),
        "sample_tests": [{"input": "1 2 3 4", "expected": "24 12 8 6"}],
        "hidden_tests": [{"input": "-1 1 0 -3 3", "expected": "0 0 9 0 0"}],
    },
    {
        "id": "majority-element",
        "title": "Majority Element",
        "difficulty": "Easy",
        "acceptance_rate": 77.6,
        "tags": ["Array", "Voting"],
        "constraints": ["Majority always exists"],
        "examples": [{"input": "3 2 3", "output": "3"}],
        "description": "Return element appearing more than n/2 times.",
        "starter_codes": dict(GENERIC_STARTERS),
        "sample_tests": [{"input": "3 2 3", "expected": "3"}],
        "hidden_tests": [{"input": "2 2 1 1 1 2 2", "expected": "2"}],
    },
    {
        "id": "max-subarray-sum",
        "title": "Maximum Subarray Sum",
        "difficulty": "Medium",
        "acceptance_rate": 61.8,
        "tags": ["Array", "DP"],
        "constraints": ["1 <= n <= 10^5"],
        "examples": [{"input": "-2 1 -3 4 -1 2 1 -5 4", "output": "6"}],
        "description": "Return maximum sum of contiguous subarray.",
        "starter_codes": dict(GENERIC_STARTERS),
        "sample_tests": [{"input": "-2 1 -3 4 -1 2 1 -5 4", "expected": "6"}],
        "hidden_tests": [{"input": "1", "expected": "1"}],
    },
    {
        "id": "climbing-stairs",
        "title": "Climbing Stairs",
        "difficulty": "Easy",
        "acceptance_rate": 73.1,
        "tags": ["DP"],
        "constraints": ["1 <= n <= 45"],
        "examples": [{"input": "3", "output": "3"}],
        "description": "You can climb 1 or 2 steps. Return number of ways to reach n.",
        "starter_codes": dict(GENERIC_STARTERS),
        "sample_tests": [{"input": "3", "expected": "3"}],
        "hidden_tests": [{"input": "5", "expected": "8"}],
    },
    {
        "id": "coin-change-min",
        "title": "Coin Change Minimum Coins",
        "difficulty": "Medium",
        "acceptance_rate": 52.4,
        "tags": ["DP"],
        "constraints": ["Line1 coins, line2 amount"],
        "examples": [{"input": "1 2 5\n11", "output": "3"}],
        "description": "Return fewest number of coins needed to make amount, else -1.",
        "starter_codes": dict(GENERIC_STARTERS),
        "sample_tests": [{"input": "1 2 5\n11", "expected": "3"}],
        "hidden_tests": [{"input": "2\n3", "expected": "-1"}],
    },
    {
        "id": "longest-substring-no-repeat",
        "title": "Longest Substring Without Repeating",
        "difficulty": "Medium",
        "acceptance_rate": 49.6,
        "tags": ["Sliding Window", "String"],
        "constraints": ["0 <= len(s) <= 10^5"],
        "examples": [{"input": "abcabcbb", "output": "3"}],
        "description": "Return length of longest substring without repeated characters.",
        "starter_codes": dict(GENERIC_STARTERS),
        "sample_tests": [{"input": "abcabcbb", "expected": "3"}],
        "hidden_tests": [{"input": "bbbbb", "expected": "1"}],
    },
    {
        "id": "group-anagrams",
        "title": "Group Anagrams",
        "difficulty": "Medium",
        "acceptance_rate": 57.2,
        "tags": ["Hash Map", "String"],
        "constraints": ["Input words space-separated; output groups separated by |"],
        "examples": [{"input": "eat tea tan ate nat bat", "output": "ate eat tea|nat tan|bat"}],
        "description": "Group anagrams. Output each group sorted, groups sorted by first word, joined by '|'.",
        "starter_codes": dict(GENERIC_STARTERS),
        "sample_tests": [{"input": "eat tea tan ate nat bat", "expected": "ate eat tea|nat tan|bat"}],
        "hidden_tests": [{"input": "ab ba abc", "expected": "ab ba|abc"}],
    },
    {
        "id": "kth-largest-element",
        "title": "Kth Largest Element",
        "difficulty": "Medium",
        "acceptance_rate": 63.7,
        "tags": ["Heap", "Array"],
        "constraints": ["Line1 nums, line2 k"],
        "examples": [{"input": "3 2 1 5 6 4\n2", "output": "5"}],
        "description": "Return kth largest element in array.",
        "starter_codes": dict(GENERIC_STARTERS),
        "sample_tests": [{"input": "3 2 1 5 6 4\n2", "expected": "5"}],
        "hidden_tests": [{"input": "3 2 3 1 2 4 5 5 6\n4", "expected": "4"}],
    },
    {
        "id": "lru-cache-ops",
        "title": "LRU Cache Operations",
        "difficulty": "Hard",
        "acceptance_rate": 41.3,
        "tags": ["Design", "Hash Map"],
        "constraints": ["Input format simplified for operations"],
        "examples": [{"input": "2\nput 1 1\nput 2 2\nget 1\nput 3 3\nget 2", "output": "1 -1"}],
        "description": "Line1 capacity. Next lines ops: put k v / get k. Return get outputs space-separated.",
        "starter_codes": dict(GENERIC_STARTERS),
        "sample_tests": [{"input": "2\nput 1 1\nput 2 2\nget 1\nput 3 3\nget 2", "expected": "1 -1"}],
        "hidden_tests": [{"input": "1\nput 1 1\nput 2 2\nget 1\nget 2", "expected": "-1 2"}],
    },
]


def _conn():
    return db.get_conn()


def reset_submission_ts_cache() -> None:
    global _SUBMISSION_TS_COL_CACHE, _SUBMISSION_TS_CACHE_READY, _SUBMISSION_TS_WARNED
    _SUBMISSION_TS_COL_CACHE = ""
    _SUBMISSION_TS_CACHE_READY = False
    _SUBMISSION_TS_WARNED = False


def submission_ts_column(conn=None) -> str:
    global _SUBMISSION_TS_COL_CACHE, _SUBMISSION_TS_CACHE_READY, _SUBMISSION_TS_WARNED
    if _SUBMISSION_TS_CACHE_READY:
        return _SUBMISSION_TS_COL_CACHE

    close_after = False
    if conn is None:
        conn = _conn()
        close_after = True
    try:
        cols = set(db.list_columns(conn, "coding_submissions"))
        if "created_ts" in cols:
            _SUBMISSION_TS_COL_CACHE = "created_ts"
        elif "ts" in cols:
            _SUBMISSION_TS_COL_CACHE = "ts"
        else:
            _SUBMISSION_TS_COL_CACHE = ""
            if not _SUBMISSION_TS_WARNED:
                print("WARN: coding_submissions has neither created_ts nor ts; using safe defaults.")
                _SUBMISSION_TS_WARNED = True
        _SUBMISSION_TS_CACHE_READY = True
        return _SUBMISSION_TS_COL_CACHE
    finally:
        if close_after:
            conn.close()


def _json_load(raw: str, fallback: Any):
    try:
        return json.loads(raw or "")
    except Exception:
        return fallback


def _ensure_column(conn, table: str, col: str, ddl: str) -> None:
    parts = (ddl or "").strip().split(None, 1)
    col_type = parts[1] if len(parts) > 1 else "TEXT"
    db.ensure_column(conn, table, col, col_type)


def init_coding_tables() -> None:
    reset_submission_ts_cache()
    conn = _conn()
    cur = conn.cursor()
    id_col = db.id_pk_col()
    db.execute(cur,
        """
        CREATE TABLE IF NOT EXISTS coding_problems(
            id TEXT PRIMARY KEY,
            title TEXT,
            difficulty TEXT,
            description TEXT,
            tags_json TEXT,
            constraints_json TEXT,
            examples_json TEXT,
            sample_tests_json TEXT,
            hidden_tests_json TEXT,
            starter_py TEXT,
            starter_js TEXT,
            starter_java TEXT,
            starter_cpp TEXT,
            created_ts INTEGER
        )
        """
    )
    _ensure_column(conn, "coding_problems", "starter_java", "starter_java TEXT")
    _ensure_column(conn, "coding_problems", "starter_cpp", "starter_cpp TEXT")

    db.execute(cur,
        f"""
        CREATE TABLE IF NOT EXISTS coding_submissions(
            id {id_col},
            problem_id TEXT,
            language TEXT,
            mode TEXT,
            status TEXT,
            passed INTEGER,
            total INTEGER,
            runtime_ms REAL,
            user_email TEXT,
            created_ts INTEGER
        )
        """
    )
    _ensure_column(conn, "coding_submissions", "user_email", "user_email TEXT")
    _ensure_column(conn, "coding_submissions", "explanation", "explanation TEXT")
    _ensure_column(conn, "coding_submissions", "session_idem", "session_idem TEXT")
    _ensure_column(conn, "coding_submissions", "created_ts", "created_ts INTEGER")
    cols = set(db.list_columns(conn, "coding_submissions"))
    if "created_ts" in cols and "ts" in cols:
        db.execute(
            cur,
            "UPDATE coding_submissions SET created_ts=ts WHERE (created_ts IS NULL OR created_ts=0) AND ts IS NOT NULL",
        )
    db.execute(cur, "CREATE INDEX IF NOT EXISTS idx_coding_submissions_user_created ON coding_submissions(user_email, created_ts)")
    db.execute(cur, "CREATE INDEX IF NOT EXISTS idx_coding_submissions_user_status ON coding_submissions(user_email, status)")
    if "ts" in cols:
        db.execute(cur, "CREATE INDEX IF NOT EXISTS idx_coding_submissions_user_ts ON coding_submissions(user_email, ts)")

    db.execute(
        cur,
        """
        CREATE TABLE IF NOT EXISTS coding_problem_versions(
            id TEXT PRIMARY KEY,
            problem_id TEXT,
            version_no INTEGER,
            changed_ts INTEGER,
            payload_json TEXT
        )
        """,
    )
    db.execute(
        cur,
        """
        CREATE TABLE IF NOT EXISTS coding_idempotency(
            idem_key TEXT PRIMARY KEY,
            user_email TEXT,
            problem_id TEXT,
            language TEXT,
            mode TEXT,
            response_json TEXT,
            created_ts INTEGER
        )
        """,
    )
    db.execute(
        cur,
        f"""
        CREATE TABLE IF NOT EXISTS coding_attempt_timeline(
            id {id_col},
            user_email TEXT,
            problem_id TEXT,
            language TEXT,
            mode TEXT,
            status TEXT,
            passed INTEGER,
            total INTEGER,
            runtime_ms REAL,
            code_hash TEXT,
            code_size INTEGER,
            code_preview TEXT,
            explanation TEXT,
            failure_reason TEXT,
            result_json TEXT,
            created_ts INTEGER
        )
        """,
    )
    _ensure_column(conn, "coding_attempt_timeline", "code_hash", "code_hash TEXT")
    _ensure_column(conn, "coding_attempt_timeline", "code_size", "code_size INTEGER")
    _ensure_column(conn, "coding_attempt_timeline", "code_preview", "code_preview TEXT")
    _ensure_column(conn, "coding_attempt_timeline", "explanation", "explanation TEXT")
    _ensure_column(conn, "coding_attempt_timeline", "failure_reason", "failure_reason TEXT")
    _ensure_column(conn, "coding_attempt_timeline", "result_json", "result_json TEXT")
    _ensure_column(conn, "coding_attempt_timeline", "created_ts", "created_ts INTEGER")
    db.execute(cur, "CREATE INDEX IF NOT EXISTS idx_timeline_user_problem_ts ON coding_attempt_timeline(user_email, problem_id, created_ts)")
    db.execute(cur, "CREATE INDEX IF NOT EXISTS idx_timeline_user_ts ON coding_attempt_timeline(user_email, created_ts)")
    db.execute(cur, "CREATE INDEX IF NOT EXISTS idx_timeline_problem_hash ON coding_attempt_timeline(problem_id, code_hash)")

    db.execute(
        cur,
        """
        CREATE TABLE IF NOT EXISTS coding_judge_jobs(
            job_id TEXT PRIMARY KEY,
            user_email TEXT,
            problem_id TEXT,
            language TEXT,
            mode TEXT,
            code_text TEXT,
            custom_input TEXT,
            explanation TEXT,
            idem_key TEXT,
            timed_mode TEXT,
            status TEXT,
            result_json TEXT,
            error_text TEXT,
            created_ts INTEGER,
            updated_ts INTEGER
        )
        """,
    )
    _ensure_column(conn, "coding_judge_jobs", "custom_input", "custom_input TEXT")
    _ensure_column(conn, "coding_judge_jobs", "explanation", "explanation TEXT")
    _ensure_column(conn, "coding_judge_jobs", "idem_key", "idem_key TEXT")
    _ensure_column(conn, "coding_judge_jobs", "timed_mode", "timed_mode TEXT")
    _ensure_column(conn, "coding_judge_jobs", "status", "status TEXT")
    _ensure_column(conn, "coding_judge_jobs", "result_json", "result_json TEXT")
    _ensure_column(conn, "coding_judge_jobs", "error_text", "error_text TEXT")
    _ensure_column(conn, "coding_judge_jobs", "updated_ts", "updated_ts INTEGER")
    db.execute(cur, "CREATE INDEX IF NOT EXISTS idx_judge_jobs_user_status_ts ON coding_judge_jobs(user_email, status, created_ts)")

    conn.commit()
    conn.close()
    reset_submission_ts_cache()


def get_all_problems(query: str = "", difficulty: str = "") -> List[Dict[str, Any]]:
    problems = list(DEFAULT_PROBLEMS)
    conn = _conn()
    cur = conn.cursor()
    db.execute(cur, 
        """
        SELECT id,title,difficulty,description,tags_json,constraints_json,examples_json,
               sample_tests_json,hidden_tests_json,starter_py,starter_js,starter_java,starter_cpp
        FROM coding_problems ORDER BY created_ts DESC
        """
    )
    rows = cur.fetchall()
    conn.close()

    for r in rows:
        problems.append(
            {
                "id": r[0],
                "title": r[1],
                "difficulty": r[2] or "Easy",
                "acceptance_rate": 0.0,
                "tags": _json_load(r[4], []),
                "constraints": _json_load(r[5], []),
                "examples": _json_load(r[6], []),
                "description": r[3] or "",
                "starter_codes": {
                    "python": r[9] or "def solve(input_data: str) -> str:\n    return \"\"\n",
                    "javascript": r[10] or "function solve(inputData) {\n  return \"\";\n}\n",
                    "java": r[11] or "public class Solution {\n  public static String solve(String inputData) {\n    return \"\";\n  }\n}\n",
                    "cpp": r[12] or "#include <bits/stdc++.h>\nusing namespace std;\n\nstring solve(const string& inputData) {\n    return \"\";\n}\n",
                },
                "sample_tests": _json_load(r[7], []),
                "hidden_tests": _json_load(r[8], []),
                "custom": True,
            }
        )

    q = (query or "").strip().lower()
    d = (difficulty or "").strip().lower()

    if q:
        problems = [
            p for p in problems
            if q in p.get("title", "").lower()
            or q in p.get("description", "").lower()
            or any(q in str(t).lower() for t in p.get("tags", []))
        ]

    if d and d != "all":
        problems = [p for p in problems if p.get("difficulty", "").lower() == d]

    return problems


def get_custom_problems() -> List[Dict[str, Any]]:
    return [p for p in get_all_problems() if p.get("custom")]


def get_problem(problem_id: str) -> Dict[str, Any]:
    all_problems = get_all_problems()
    for p in all_problems:
        if p["id"] == problem_id:
            return p
    return all_problems[0]


def parse_test_lines(raw: str) -> List[Dict[str, str]]:
    tests = []
    for line in (raw or "").splitlines():
        row = line.strip()
        if not row or "|||" not in row:
            continue
        inp, exp = row.split("|||", 1)
        tests.append({"input": inp.strip().replace("\\n", "\n"), "expected": exp.strip().replace("\\n", "\n")})
    return tests


def _starter_defaults() -> Dict[str, str]:
    return {
        "python": "def solve(input_data: str) -> str:\n    # Write your solution here\n    return \"\"\n",
        "javascript": "function solve(inputData) {\n  // Write your solution here\n  return \"\";\n}\n",
        "java": "import java.util.*;\n\npublic class Solution {\n  public static String solve(String inputData) {\n    // Write your solution here\n    return \"\";\n  }\n}\n",
        "cpp": "#include <bits/stdc++.h>\nusing namespace std;\n\nstring solve(const string& inputData) {\n    // Write your solution here\n    return \"\";\n}\n",
    }


def add_custom_problem(
    title: str,
    difficulty: str,
    description: str,
    tags: List[str],
    constraints: List[str],
    examples: List[Dict[str, str]],
    sample_tests: List[Dict[str, str]],
    hidden_tests: List[Dict[str, str]],
    starter_py: str,
    starter_js: str,
    starter_java: str,
    starter_cpp: str,
) -> str:
    problem_id = f"custom-{int(time.time() * 1000)}"
    defaults = _starter_defaults()
    conn = _conn()
    cur = conn.cursor()
    db.execute(cur, 
        """
        INSERT INTO coding_problems(
            id,title,difficulty,description,tags_json,constraints_json,examples_json,
            sample_tests_json,hidden_tests_json,starter_py,starter_js,starter_java,starter_cpp,created_ts
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            problem_id,
            title.strip(),
            difficulty.strip() if difficulty.strip() in DIFFICULTIES else "Easy",
            description.strip(),
            json.dumps(tags),
            json.dumps(constraints),
            json.dumps(examples),
            json.dumps(sample_tests),
            json.dumps(hidden_tests),
            starter_py or defaults["python"],
            starter_js or defaults["javascript"],
            starter_java or defaults["java"],
            starter_cpp or defaults["cpp"],
            int(time.time()),
        ),
    )
    conn.commit()
    conn.close()
    save_problem_version(problem_id)
    return problem_id


def update_custom_problem(
    problem_id: str,
    title: str,
    difficulty: str,
    description: str,
    tags: List[str],
    constraints: List[str],
    examples: List[Dict[str, str]],
    sample_tests: List[Dict[str, str]],
    hidden_tests: List[Dict[str, str]],
    starter_py: str,
    starter_js: str,
    starter_java: str,
    starter_cpp: str,
) -> bool:
    if not str(problem_id).startswith("custom-"):
        return False
    defaults = _starter_defaults()
    conn = _conn()
    cur = conn.cursor()
    db.execute(cur, 
        """
        UPDATE coding_problems
        SET title=?, difficulty=?, description=?, tags_json=?, constraints_json=?, examples_json=?,
            sample_tests_json=?, hidden_tests_json=?, starter_py=?, starter_js=?, starter_java=?, starter_cpp=?
        WHERE id=?
        """,
        (
            title.strip(),
            difficulty.strip() if difficulty.strip() in DIFFICULTIES else "Easy",
            description.strip(),
            json.dumps(tags),
            json.dumps(constraints),
            json.dumps(examples),
            json.dumps(sample_tests),
            json.dumps(hidden_tests),
            starter_py or defaults["python"],
            starter_js or defaults["javascript"],
            starter_java or defaults["java"],
            starter_cpp or defaults["cpp"],
            problem_id,
        ),
    )
    changed = cur.rowcount > 0
    conn.commit()
    conn.close()
    if changed:
        save_problem_version(problem_id)
    return changed


def delete_custom_problem(problem_id: str) -> bool:
    if not str(problem_id).startswith("custom-"):
        return False
    conn = _conn()
    cur = conn.cursor()
    db.execute(cur, "DELETE FROM coding_problems WHERE id=?", (problem_id,))
    changed = cur.rowcount > 0
    conn.commit()
    conn.close()
    return changed


def save_submission(
    problem_id: str,
    language: str,
    mode: str,
    status: str,
    passed: int,
    total: int,
    runtime_ms: float,
    user_email: str = "",
    explanation: str = "",
    session_idem: str = "",
) -> None:
    conn = _conn()
    cur = conn.cursor()
    db.execute(cur, 
        """
        INSERT INTO coding_submissions(problem_id,language,mode,status,passed,total,runtime_ms,user_email,created_ts,explanation,session_idem)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            problem_id,
            language,
            mode,
            status,
            int(passed),
            int(total),
            float(runtime_ms),
            (user_email or "").strip().lower(),
            int(time.time()),
            (explanation or "").strip()[:2000],
            (session_idem or "").strip()[:120],
        ),
    )
    conn.commit()
    conn.close()


def _normalize_code_for_hash(code: str) -> str:
    src = str(code or "")
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"//.*", "", src)
    src = re.sub(r"#.*", "", src)
    src = re.sub(r"\s+", "", src)
    return src[:200000]


def code_fingerprint(code: str) -> str:
    normalized = _normalize_code_for_hash(code)
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _code_preview(code: str, max_len: int = 480) -> str:
    text = str(code or "").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "\n..."


def save_attempt_timeline(
    problem_id: str,
    language: str,
    mode: str,
    status: str,
    passed: int,
    total: int,
    runtime_ms: float,
    code: str = "",
    user_email: str = "",
    explanation: str = "",
    result: Dict[str, Any] = None,
) -> None:
    email = (user_email or "").strip().lower()
    if not email:
        return
    payload = dict(result or {})
    failure_reason = str(payload.get("failure_reason") or "")
    if not failure_reason and payload:
        failure_reason = classify_failure_reason(payload)
    conn = _conn()
    cur = conn.cursor()
    db.execute(
        cur,
        """
        INSERT INTO coding_attempt_timeline(
            user_email,problem_id,language,mode,status,passed,total,runtime_ms,
            code_hash,code_size,code_preview,explanation,failure_reason,result_json,created_ts
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            email,
            (problem_id or "").strip(),
            (language or "python").strip().lower(),
            (mode or "").strip().lower(),
            (status or "").strip(),
            int(passed or 0),
            int(total or 0),
            float(runtime_ms or 0.0),
            code_fingerprint(code),
            len(code or ""),
            _code_preview(code),
            (explanation or "").strip()[:2000],
            failure_reason[:80],
            json.dumps(payload or {}, ensure_ascii=False),
            int(time.time()),
        ),
    )
    conn.commit()
    conn.close()


def get_problem_timeline(user_email: str, problem_id: str, limit: int = 12) -> List[Dict[str, Any]]:
    email = (user_email or "").strip().lower()
    if not email:
        return []
    conn = _conn()
    cur = conn.cursor()
    db.execute(
        cur,
        """
        SELECT mode,status,passed,total,runtime_ms,code_hash,code_size,code_preview,explanation,failure_reason,created_ts
        FROM coding_attempt_timeline
        WHERE user_email=? AND problem_id=?
        ORDER BY created_ts DESC, id DESC
        LIMIT ?
        """,
        (email, (problem_id or "").strip(), max(1, int(limit))),
    )
    rows = cur.fetchall()
    conn.close()
    out = []
    for r in rows:
        out.append(
            {
                "mode": str(r[0] or ""),
                "status": str(r[1] or ""),
                "score": f"{int(r[2] or 0)}/{int(r[3] or 0)}",
                "runtime_ms": round(float(r[4] or 0.0), 1),
                "code_hash": str(r[5] or "")[:12],
                "code_size": int(r[6] or 0),
                "code_preview": str(r[7] or ""),
                "explanation": str(r[8] or ""),
                "failure_reason": str(r[9] or ""),
                "ts": int(r[10] or 0),
            }
        )
    return out


def enqueue_judge_job(
    user_email: str,
    problem_id: str,
    language: str,
    mode: str,
    code_text: str,
    custom_input: str = "",
    explanation: str = "",
    idem_key: str = "",
    timed_mode: str = "",
) -> str:
    now = int(time.time())
    seed = f"{now}:{problem_id}:{language}:{len(code_text or '')}:{os.urandom(6).hex()}"
    job_id = f"job-{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:16]}"
    conn = _conn()
    cur = conn.cursor()
    db.execute(
        cur,
        """
        INSERT INTO coding_judge_jobs(
            job_id,user_email,problem_id,language,mode,code_text,custom_input,explanation,idem_key,timed_mode,
            status,result_json,error_text,created_ts,updated_ts
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            job_id,
            (user_email or "").strip().lower(),
            (problem_id or "").strip(),
            (language or "python").strip().lower(),
            (mode or "submit").strip().lower(),
            str(code_text or ""),
            str(custom_input or ""),
            (explanation or "").strip()[:2000],
            (idem_key or "").strip()[:120],
            (timed_mode or "").strip()[:20],
            "queued",
            "{}",
            "",
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()
    return job_id


def get_judge_job(job_id: str, user_email: str = "") -> Dict[str, Any]:
    job = (job_id or "").strip()
    if not job:
        return {}
    conn = _conn()
    cur = conn.cursor()
    email = (user_email or "").strip().lower()
    if email:
        db.execute(
            cur,
            """
            SELECT job_id,user_email,problem_id,language,mode,code_text,custom_input,explanation,idem_key,timed_mode,
                   status,result_json,error_text,created_ts,updated_ts
            FROM coding_judge_jobs
            WHERE job_id=? AND user_email=?
            """,
            (job, email),
        )
    else:
        db.execute(
            cur,
            """
            SELECT job_id,user_email,problem_id,language,mode,code_text,custom_input,explanation,idem_key,timed_mode,
                   status,result_json,error_text,created_ts,updated_ts
            FROM coding_judge_jobs
            WHERE job_id=?
            """,
            (job,),
        )
    row = cur.fetchone()
    conn.close()
    if not row:
        return {}
    parsed = _json_load(row[11], {})
    return {
        "job_id": row[0],
        "user_email": row[1] or "",
        "problem_id": row[2] or "",
        "language": row[3] or "python",
        "mode": row[4] or "submit",
        "code_text": row[5] or "",
        "custom_input": row[6] or "",
        "explanation": row[7] or "",
        "idem_key": row[8] or "",
        "timed_mode": row[9] or "",
        "status": row[10] or "queued",
        "result": parsed if isinstance(parsed, dict) else {},
        "error_text": row[12] or "",
        "created_ts": int(row[13] or 0),
        "updated_ts": int(row[14] or 0),
    }


def _set_judge_job_state(job_id: str, status: str, result: Dict[str, Any] = None, error_text: str = "") -> None:
    conn = _conn()
    cur = conn.cursor()
    db.execute(
        cur,
        """
        UPDATE coding_judge_jobs
        SET status=?, result_json=?, error_text=?, updated_ts=?
        WHERE job_id=?
        """,
        (
            str(status or ""),
            json.dumps(result or {}, ensure_ascii=False),
            str(error_text or "")[:800],
            int(time.time()),
            (job_id or "").strip(),
        ),
    )
    conn.commit()
    conn.close()


def process_judge_job(job_id: str) -> Dict[str, Any]:
    job = get_judge_job(job_id)
    if not job:
        return {"ok": False, "error": "job_not_found"}
    if job.get("status") in ("completed", "failed"):
        return {"ok": True, "status": job.get("status")}

    # Claim queued jobs. If already running, continue best-effort.
    conn = _conn()
    cur = conn.cursor()
    db.execute(
        cur,
        "UPDATE coding_judge_jobs SET status='running', updated_ts=? WHERE job_id=? AND status='queued'",
        (int(time.time()), job["job_id"]),
    )
    conn.commit()
    conn.close()
    try:
        problem = get_problem(str(job.get("problem_id") or ""))
        result = evaluate_submission(
            problem=problem,
            code=str(job.get("code_text") or ""),
            language=str(job.get("language") or "python"),
            mode=str(job.get("mode") or "submit"),
            custom_input=str(job.get("custom_input") or ""),
        )
        save_submission(
            problem_id=str(job.get("problem_id") or ""),
            language=str(job.get("language") or "python"),
            mode=str(job.get("mode") or "submit"),
            status=str(result.get("status") or ""),
            passed=int(result.get("passed") or 0),
            total=int(result.get("total") or 0),
            runtime_ms=float(result.get("runtime_ms") or 0.0),
            user_email=str(job.get("user_email") or ""),
            explanation=str(job.get("explanation") or ""),
            session_idem=str(job.get("idem_key") or ""),
        )
        save_attempt_timeline(
            problem_id=str(job.get("problem_id") or ""),
            language=str(job.get("language") or "python"),
            mode=str(job.get("mode") or "submit"),
            status=str(result.get("status") or ""),
            passed=int(result.get("passed") or 0),
            total=int(result.get("total") or 0),
            runtime_ms=float(result.get("runtime_ms") or 0.0),
            code=str(job.get("code_text") or ""),
            user_email=str(job.get("user_email") or ""),
            explanation=str(job.get("explanation") or ""),
            result=result,
        )
        if str(job.get("mode") or "").lower() == "submit":
            store_idempotent_response(
                idem_key=str(job.get("idem_key") or ""),
                user_email=str(job.get("user_email") or ""),
                problem_id=str(job.get("problem_id") or ""),
                language=str(job.get("language") or "python"),
                mode="submit",
                response=result,
            )
        _set_judge_job_state(job["job_id"], "completed", result=result, error_text="")
        return {"ok": True, "status": "completed", "result": result}
    except Exception as exc:
        _set_judge_job_state(job["job_id"], "failed", result={}, error_text=str(exc))
        return {"ok": False, "status": "failed", "error": str(exc)}


def get_submission_stats(limit: int = 200) -> Dict[str, Any]:
    conn = _conn()
    cur = conn.cursor()

    db.execute(cur, 
        """
        SELECT problem_id,
               COUNT(*) AS total_runs,
               SUM(CASE WHEN status='Accepted' THEN 1 ELSE 0 END) AS accepted,
               AVG(runtime_ms) AS avg_runtime
        FROM coding_submissions
        GROUP BY problem_id
        ORDER BY total_runs DESC
        LIMIT ?
        """,
        (max(1, int(limit)),),
    )
    rows = cur.fetchall()

    db.execute(cur, "SELECT COUNT(*) FROM coding_submissions")
    total_submissions = int(cur.fetchone()[0])
    conn.close()

    return {
        "total_submissions": total_submissions,
        "by_problem": [
            {
                "problem_id": r[0],
                "total_runs": int(r[1] or 0),
                "accepted": int(r[2] or 0),
                "accept_rate": round((float(r[2] or 0) / float(r[1] or 1)) * 100.0, 1),
                "avg_runtime_ms": round(float(r[3] or 0.0), 1),
            }
            for r in rows
        ],
    }


def get_submission_stats_extended(limit: int = 200) -> Dict[str, Any]:
    base = get_submission_stats(limit=limit)
    conn = _conn()
    cur = conn.cursor()
    db.execute(
        cur,
        """
        SELECT language,
               COUNT(*) AS total_runs,
               SUM(CASE WHEN status='Accepted' THEN 1 ELSE 0 END) AS accepted
        FROM coding_submissions
        GROUP BY language
        ORDER BY total_runs DESC
        """,
    )
    lang_rows = cur.fetchall()
    db.execute(
        cur,
        """
        SELECT p.difficulty,
               COUNT(*) AS total_runs,
               SUM(CASE WHEN s.status='Accepted' THEN 1 ELSE 0 END) AS accepted
        FROM coding_submissions s
        LEFT JOIN coding_problems p ON p.id=s.problem_id
        GROUP BY p.difficulty
        ORDER BY total_runs DESC
        """,
    )
    diff_rows = cur.fetchall()
    conn.close()
    base["by_language"] = [
        {
            "language": str(r[0] or "unknown"),
            "total_runs": int(r[1] or 0),
            "accept_rate": round((float(r[2] or 0) / max(1, float(r[1] or 1))) * 100.0, 1),
        }
        for r in lang_rows
    ]
    base["by_difficulty"] = [
        {
            "difficulty": str(r[0] or "Unknown"),
            "total_runs": int(r[1] or 0),
            "accept_rate": round((float(r[2] or 0) / max(1, float(r[1] or 1))) * 100.0, 1),
        }
        for r in diff_rows
    ]
    return base


def get_user_submission_summary(user_email: str, limit: int = 20) -> Dict[str, Any]:
    email = (user_email or "").strip().lower()
    if not email:
        return {
            "total": 0,
            "accepted": 0,
            "accept_rate": 0.0,
            "avg_runtime_ms": 0.0,
            "by_language": [],
            "recent": [],
        }

    conn = _conn()
    cur = conn.cursor()
    ts_col = submission_ts_column(conn)
    db.execute(cur, 
        """
        SELECT COUNT(*),
               SUM(CASE WHEN status='Accepted' THEN 1 ELSE 0 END),
               AVG(runtime_ms)
        FROM coding_submissions
        WHERE user_email=?
        """,
        (email,),
    )
    agg = cur.fetchone() or (0, 0, 0.0)

    db.execute(cur, 
        """
        SELECT language,
               COUNT(*) AS total,
               SUM(CASE WHEN status='Accepted' THEN 1 ELSE 0 END) AS accepted
        FROM coding_submissions
        WHERE user_email=?
        GROUP BY language
        ORDER BY total DESC
        """,
        (email,),
    )
    lang_rows = cur.fetchall()

    recent_rows = []
    if ts_col:
        db.execute(
            cur,
            f"""
            SELECT problem_id, language, mode, status, passed, total, runtime_ms, {ts_col}
            FROM coding_submissions
            WHERE user_email=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (email, max(1, int(limit))),
        )
        recent_rows = cur.fetchall()
    conn.close()

    total = int(agg[0] or 0)
    accepted = int(agg[1] or 0)
    return {
        "total": total,
        "accepted": accepted,
        "accept_rate": round((accepted / max(1, total)) * 100.0, 1),
        "avg_runtime_ms": round(float(agg[2] or 0.0), 1),
        "by_language": [
            {
                "language": r[0],
                "total": int(r[1] or 0),
                "accepted": int(r[2] or 0),
                "accept_rate": round((float(r[2] or 0) / max(1, float(r[1] or 1))) * 100.0, 1),
            }
            for r in lang_rows
        ],
        "recent": [
            {
                "problem_id": r[0],
                "language": r[1],
                "mode": r[2],
                "status": r[3],
                "score": f"{int(r[4] or 0)}/{int(r[5] or 0)}",
                "runtime_ms": round(float(r[6] or 0.0), 1),
                "ts": int(r[7] or 0),
            }
            for r in recent_rows
        ],
    }


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def normalize_runtime_error(err: str) -> str:
    e = (err or "").strip()
    low = e.lower()
    if "time limit exceeded" in low or "timeout" in low:
        return "Time Limit Exceeded"
    if "memory" in low:
        return "Memory Limit Exceeded"
    if "syntaxerror" in low or "compilation error" in low:
        return "Compilation Error"
    if "traceback" in low or "exception" in low:
        return "Runtime Exception"
    return e[:300] or "Runtime Error"


def first_diff_index(expected: str, actual: str) -> int:
    left = expected or ""
    right = actual or ""
    upto = min(len(left), len(right))
    for i in range(upto):
        if left[i] != right[i]:
            return i
    if len(left) != len(right):
        return upto
    return -1


def classify_failure_reason(result: Dict[str, Any]) -> str:
    status = str(result.get("status", "")).lower()
    cases = result.get("cases", []) or []
    if "accepted" in status:
        return "accepted"
    if "runtime" in status:
        return "runtime_error"
    if "failed" in status and not cases:
        return "unknown_failure"
    fails = [c for c in cases if not c.get("passed")]
    if not fails:
        return "partial"
    first = fails[0]
    actual = str(first.get("actual", "")).lower()
    if "time limit exceeded" in actual:
        return "time_limit"
    if "error" in actual or "exception" in actual:
        return "runtime_error"
    if first_diff_index(str(first.get("expected", "")), str(first.get("actual", ""))) >= 0:
        return "wrong_answer"
    return "wrong_answer"


def _slice_with_cursor(text: str, idx: int, radius: int = 24) -> Dict[str, Any]:
    src = str(text or "")
    if idx < 0:
        idx = 0
    start = max(0, idx - radius)
    end = min(len(src), idx + radius)
    return {
        "snippet": src[start:end],
        "cursor": idx - start,
        "start": start,
        "end": end,
    }


def build_failure_debug(result: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(result or {})
    if str(payload.get("status", "")).lower() == "accepted":
        return {}
    fails = [c for c in (payload.get("cases") or []) if not c.get("passed")]
    if not fails:
        return {}
    case = fails[0]
    expected = str(case.get("expected", ""))
    actual = str(case.get("actual", ""))
    diff_idx = int(case.get("diff_index") if case.get("diff_index") is not None else -1)
    if diff_idx < 0:
        diff_idx = first_diff_index(expected, actual)
    hint = "Check parsing and output formatting."
    reason = str(payload.get("failure_reason") or "")
    if reason == "time_limit":
        hint = "Optimize algorithmic complexity and avoid nested scans."
    elif reason == "runtime_error":
        hint = "Add guard checks for empty input and invalid indexes."
    elif reason == "wrong_answer":
        hint = "Validate edge cases and off-by-one boundaries."
    return {
        "case_index": int(case.get("index") or 1),
        "hidden": bool(case.get("hidden")),
        "mismatch_index": int(diff_idx),
        "expected_ctx": _slice_with_cursor(expected, diff_idx),
        "actual_ctx": _slice_with_cursor(actual, diff_idx),
        "input_preview": str(case.get("input", ""))[:200],
        "hint": hint,
    }


def estimate_complexity(code: str, language: str, constraints: List[str]) -> Dict[str, str]:
    src = (code or "").lower()
    loops = src.count("for ") + src.count("while ")
    nested = src.count("for ") >= 2 or ("for " in src and "while " in src)
    recursion = ("def " in src and "return" in src and "solve(" in src and "solve(" in src[src.find("solve(") + 1:]) or ("solve(" in src and "solve(" in src[src.find("solve(") + 1:])
    big_o = "O(n)"
    if nested:
        big_o = "O(n^2)"
    elif loops >= 2:
        big_o = "O(n^2)"
    elif recursion:
        big_o = "O(2^n)"
    expected = "O(n) or better"
    cons = " ".join(constraints or []).lower()
    if "10^5" in cons or "100000" in cons:
        expected = "O(n log n) or better"
    if "10^3" in cons:
        expected = "O(n^2) is acceptable"
    verdict = "aligned" if ("n^2" in big_o and "n^2" in expected) or ("n^2" not in big_o and "or better" in expected) else "needs_optimization"
    return {"estimated": big_o, "expected": expected, "verdict": verdict}


def _problem_payload(problem: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": problem.get("id"),
        "title": problem.get("title"),
        "difficulty": problem.get("difficulty"),
        "description": problem.get("description"),
        "tags": problem.get("tags", []),
        "constraints": problem.get("constraints", []),
        "examples": problem.get("examples", []),
        "sample_tests": problem.get("sample_tests", []),
        "hidden_tests": problem.get("hidden_tests", []),
        "starter_codes": problem.get("starter_codes", {}),
    }


def _next_problem_version_no(problem_id: str) -> int:
    conn = _conn()
    cur = conn.cursor()
    db.execute(cur, "SELECT COALESCE(MAX(version_no),0) FROM coding_problem_versions WHERE problem_id=?", (problem_id,))
    row = cur.fetchone() or (0,)
    conn.close()
    return int(row[0] or 0) + 1


def save_problem_version(problem_id: str) -> None:
    problem = get_problem(problem_id)
    if not problem:
        return
    version_no = _next_problem_version_no(problem_id)
    conn = _conn()
    cur = conn.cursor()
    version_id = f"{problem_id}-v{version_no}-{int(time.time())}"
    db.execute(
        cur,
        """
        INSERT INTO coding_problem_versions(id,problem_id,version_no,changed_ts,payload_json)
        VALUES (?,?,?,?,?)
        """,
        (version_id, problem_id, version_no, int(time.time()), json.dumps(_problem_payload(problem))),
    )
    conn.commit()
    conn.close()


def coverage_report(problem: Dict[str, Any]) -> Dict[str, Any]:
    sample = len(problem.get("sample_tests", []) or [])
    hidden = len(problem.get("hidden_tests", []) or [])
    tags = len(problem.get("tags", []) or [])
    constraints = len(problem.get("constraints", []) or [])
    score = 0
    score += 30 if sample >= 2 else 10
    score += 30 if hidden >= 2 else 10
    score += 20 if tags >= 2 else 10
    score += 20 if constraints >= 1 else 0
    return {
        "sample_tests": sample,
        "hidden_tests": hidden,
        "tags": tags,
        "constraints": constraints,
        "coverage_score": min(100, score),
        "ready_to_publish": sample >= 1 and hidden >= 1 and constraints >= 1,
    }


def export_problems_json() -> str:
    rows = []
    for p in get_all_problems():
        rows.append(_problem_payload(p))
    return json.dumps(rows, indent=2)


def export_problems_csv() -> str:
    def _esc(v: Any) -> str:
        return str(v or "").replace("\n", "\\n")

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["id", "title", "difficulty", "tags", "description", "constraints", "sample_tests", "hidden_tests"])
    for p in get_all_problems():
        writer.writerow([
            p.get("id", ""),
            p.get("title", ""),
            p.get("difficulty", ""),
            ",".join([str(t) for t in p.get("tags", [])]),
            p.get("description", ""),
            "\\n".join([str(c) for c in p.get("constraints", [])]),
            "\\n".join([f"{_esc(t.get('input',''))}|||{_esc(t.get('expected',''))}" for t in p.get("sample_tests", [])]),
            "\\n".join([f"{_esc(t.get('input',''))}|||{_esc(t.get('expected',''))}" for t in p.get("hidden_tests", [])]),
        ])
    return out.getvalue()


def import_problems_from_json(raw: str) -> Dict[str, int]:
    created = 0
    updated = 0
    failed = 0
    data = json.loads(raw or "[]")
    if not isinstance(data, list):
        return {"created": 0, "updated": 0, "failed": 1}
    for item in data:
        try:
            if not isinstance(item, dict):
                failed += 1
                continue
            pid = str(item.get("id", "")).strip()
            title = str(item.get("title", "")).strip()
            if not title:
                failed += 1
                continue
            existing = None
            if pid:
                for p in get_all_problems():
                    if p.get("id") == pid:
                        existing = p
                        break
            tags = [str(t).strip() for t in (item.get("tags") or []) if str(t).strip()]
            constraints = [str(t).strip() for t in (item.get("constraints") or []) if str(t).strip()]
            examples = item.get("examples") or []
            sample_tests = item.get("sample_tests") or []
            hidden_tests = item.get("hidden_tests") or []
            starters = item.get("starter_codes") or {}
            if existing and str(existing.get("id", "")).startswith("custom-"):
                changed = update_custom_problem(
                    problem_id=existing["id"],
                    title=title,
                    difficulty=str(item.get("difficulty", "Easy")),
                    description=str(item.get("description", "")),
                    tags=tags,
                    constraints=constraints,
                    examples=examples,
                    sample_tests=sample_tests,
                    hidden_tests=hidden_tests,
                    starter_py=str(starters.get("python", "")),
                    starter_js=str(starters.get("javascript", "")),
                    starter_java=str(starters.get("java", "")),
                    starter_cpp=str(starters.get("cpp", "")),
                )
                updated += 1 if changed else 0
            else:
                add_custom_problem(
                    title=title,
                    difficulty=str(item.get("difficulty", "Easy")),
                    description=str(item.get("description", "")),
                    tags=tags,
                    constraints=constraints,
                    examples=examples,
                    sample_tests=sample_tests,
                    hidden_tests=hidden_tests,
                    starter_py=str(starters.get("python", "")),
                    starter_js=str(starters.get("javascript", "")),
                    starter_java=str(starters.get("java", "")),
                    starter_cpp=str(starters.get("cpp", "")),
                )
                created += 1
        except Exception:
            failed += 1
    return {"created": created, "updated": updated, "failed": failed}


def fetch_idempotent_response(idem_key: str) -> Dict[str, Any]:
    key = (idem_key or "").strip()
    if not key:
        return {}
    conn = _conn()
    cur = conn.cursor()
    db.execute(cur, "SELECT response_json FROM coding_idempotency WHERE idem_key=?", (key,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return {}
    try:
        return json.loads(row[0] or "{}")
    except Exception:
        return {}


def store_idempotent_response(
    idem_key: str,
    user_email: str,
    problem_id: str,
    language: str,
    mode: str,
    response: Dict[str, Any],
) -> None:
    key = (idem_key or "").strip()[:120]
    if not key:
        return
    conn = _conn()
    cur = conn.cursor()
    db.execute(
        cur,
        """
        INSERT INTO coding_idempotency(idem_key,user_email,problem_id,language,mode,response_json,created_ts)
        VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(idem_key) DO UPDATE SET
            response_json=excluded.response_json,
            created_ts=excluded.created_ts
        """,
        (
            key,
            (user_email or "").strip().lower(),
            (problem_id or "").strip(),
            (language or "").strip(),
            (mode or "").strip(),
            json.dumps(response or {}),
            int(time.time()),
        ),
    )
    conn.commit()
    conn.close()


def hint_ladder(problem: Dict[str, Any], code: str, result: Dict[str, Any], level: int = 1) -> Dict[str, str]:
    lvl = max(1, min(3, int(level or 1)))
    tags = ", ".join(problem.get("tags", [])[:3]) or "problem decomposition"
    fail = classify_failure_reason(result or {})
    if lvl == 1:
        text = f"Concept hint: focus on {tags}. Start with a clear input/output mapping."
    elif lvl == 2:
        if fail == "wrong_answer":
            text = "Edge-case hint: test empty input, single element, and duplicate values."
        elif fail == "time_limit":
            text = "Edge-case hint: optimize loops and avoid repeated scans of the full input."
        else:
            text = "Edge-case hint: validate parsing and output format exactly."
    else:
        if fail in ("time_limit", "needs_optimization"):
            text = "Approach hint: try hash map / two pointers / prefix strategy to reduce complexity."
        else:
            text = "Approach hint: write small helper steps, assert each step with one sample."
    return {"level": str(lvl), "hint": text}


def coding_followup_questions(problem: Dict[str, Any], code: str, language: str = "python") -> List[str]:
    title = str(problem.get("title", "this problem"))
    return [
        f"What is the time and space complexity of your solution for {title}?",
        "Which edge case was hardest, and how did your code handle it?",
        f"If input size grows 100x, what would you refactor first in your {language} implementation?",
    ]


def review_code_heuristic(problem: Dict[str, Any], code: str, result: Dict[str, Any], language: str = "python") -> Dict[str, Any]:
    src = code or ""
    lines = [ln for ln in src.splitlines() if ln.strip()]
    comments = sum(1 for ln in lines if ln.strip().startswith(("#", "//", "/*", "*")))
    fail_reason = classify_failure_reason(result or {})
    notes = []
    if len(lines) > 120:
        notes.append("Solution is long; consider extracting helper functions.")
    if comments == 0:
        notes.append("Add 1-2 comments for non-obvious logic blocks.")
    if fail_reason == "wrong_answer":
        notes.append("Your logic is close; add targeted edge-case tests.")
    if fail_reason == "time_limit":
        notes.append("Optimize complexity; avoid nested scans where possible.")
    if not notes:
        notes.append("Structure looks clean. Next step: tighten variable naming and add one edge-case guard.")
    complexity = estimate_complexity(src, language, problem.get("constraints", []))
    return {
        "summary": "Heuristic code review",
        "notes": notes[:4],
        "complexity": complexity,
    }


def weak_tags_for_user(user_email: str, window_days: int = 30) -> List[Dict[str, Any]]:
    email = (user_email or "").strip().lower()
    if not email:
        return []
    since = int(time.time()) - (max(1, int(window_days)) * 24 * 60 * 60)
    conn = _conn()
    cur = conn.cursor()
    ts_col = submission_ts_column(conn)
    if ts_col:
        db.execute(
            cur,
            f"""
            SELECT problem_id, status
            FROM coding_submissions
            WHERE user_email=? AND {ts_col}>=?
            ORDER BY {ts_col} DESC
            LIMIT 300
            """,
            (email, since),
        )
        rows = cur.fetchall()
    else:
        rows = []
    conn.close()
    problems = {p["id"]: p for p in get_all_problems()}
    tag_stats: Dict[str, Dict[str, int]] = {}
    for pid, status in rows:
        tags = (problems.get(pid, {}) or {}).get("tags", []) or []
        for t in tags:
            key = str(t)
            bucket = tag_stats.setdefault(key, {"total": 0, "accepted": 0})
            bucket["total"] += 1
            if str(status or "") == "Accepted":
                bucket["accepted"] += 1
    ranked = []
    for tag, st in tag_stats.items():
        total = st["total"]
        acc = st["accepted"]
        rate = (acc / max(1, total)) * 100.0
        ranked.append({"tag": tag, "attempts": total, "accept_rate": round(rate, 1)})
    ranked.sort(key=lambda x: (x["accept_rate"], -x["attempts"]))
    return ranked[:6]


def recommend_next_problem(user_email: str, exclude_problem_id: str = "") -> Dict[str, Any]:
    weak = weak_tags_for_user(user_email)
    weak_tag = weak[0]["tag"] if weak else ""
    problems = get_all_problems()
    if weak_tag:
        for p in problems:
            if p.get("id") == exclude_problem_id:
                continue
            if weak_tag in (p.get("tags") or []):
                return p
    for p in problems:
        if p.get("id") != exclude_problem_id:
            return p
    return {}


def study_plan(user_email: str, days: int = 7) -> List[str]:
    weak = weak_tags_for_user(user_email)
    focus = [w["tag"] for w in weak[:3]] or ["Arrays", "Hash Map", "DP"]
    if days <= 7:
        return [
            f"Day 1-2: Solve 2 Easy problems on {focus[0]}.",
            f"Day 3-4: Solve 2 Medium problems on {focus[1] if len(focus) > 1 else focus[0]}.",
            "Day 5: Review failed submissions and write edge-case checklist.",
            f"Day 6-7: Timed mock set on {focus[-1]} and one mixed revision problem.",
        ]
    return [
        f"Week 1: Foundation refresh on {focus[0]} and {focus[1] if len(focus) > 1 else focus[0]}.",
        "Week 2: Medium difficulty focus + runtime optimization drills.",
        f"Week 3: Problem sets on {focus[-1]} + interview-style explanations.",
        "Week 4: Timed mixed mocks and retrospective on recurring mistakes.",
    ]


def interview_readiness_score(user_email: str) -> Dict[str, Any]:
    summary = get_user_submission_summary(user_email, limit=100)
    total = _safe_int(summary.get("total"))
    accept = _safe_float(summary.get("accept_rate"))
    speed = _safe_float(summary.get("avg_runtime_ms"))
    consistency = min(100.0, total * 5.0)
    speed_score = 100.0 if speed <= 120 else max(20.0, 140.0 - (speed / 2.5))
    score = round((accept * 0.5) + (consistency * 0.25) + (speed_score * 0.25), 1)
    band = "High" if score >= 75 else ("Medium" if score >= 50 else "Low")
    return {"score": score, "band": band, "accept_rate": accept, "consistency": round(consistency, 1), "speed_score": round(speed_score, 1)}


def _day_start(ts: int) -> int:
    t = time.localtime(int(ts or time.time()))
    return int(time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, t.tm_wday, t.tm_yday, t.tm_isdst)))


def topic_mastery_report(user_email: str, window_days: int = 45) -> List[Dict[str, Any]]:
    email = (user_email or "").strip().lower()
    if not email:
        return []
    since = int(time.time()) - max(1, int(window_days)) * 24 * 60 * 60
    conn = _conn()
    cur = conn.cursor()
    ts_col = submission_ts_column(conn)
    if not ts_col:
        conn.close()
        return []
    db.execute(
        cur,
        f"""
        SELECT problem_id, mode, status
        FROM coding_submissions
        WHERE user_email=? AND {ts_col}>=?
        ORDER BY {ts_col} DESC
        LIMIT 1200
        """,
        (email, since),
    )
    rows = cur.fetchall()
    conn.close()
    problems = {p["id"]: p for p in get_all_problems()}
    by_tag: Dict[str, Dict[str, float]] = {}
    for pid, mode, status in rows:
        tags = (problems.get(str(pid), {}) or {}).get("tags", []) or []
        for tag in tags:
            key = str(tag)
            bucket = by_tag.setdefault(key, {"attempts": 0.0, "accepted": 0.0, "submit_attempts": 0.0})
            bucket["attempts"] += 1.0
            if str(mode or "").lower() == "submit":
                bucket["submit_attempts"] += 1.0
            if str(status or "") == "Accepted":
                bucket["accepted"] += 1.0
    ranked = []
    for tag, st in by_tag.items():
        attempts = int(st["attempts"])
        accepted = int(st["accepted"])
        submit_attempts = int(st["submit_attempts"])
        acc_rate = round((accepted / max(1, submit_attempts)) * 100.0, 1)
        volume_score = min(30.0, attempts * 4.5)
        mastery = round((acc_rate * 0.7) + volume_score, 1)
        level = "Building"
        if mastery >= 78 and attempts >= 4:
            level = "Strong"
        elif mastery >= 55:
            level = "Developing"
        ranked.append(
            {
                "tag": tag,
                "attempts": attempts,
                "accepted": accepted,
                "accept_rate": acc_rate,
                "mastery_score": mastery,
                "level": level,
            }
        )
    ranked.sort(key=lambda x: (x["mastery_score"], x["attempts"]), reverse=True)
    return ranked[:12]


def daily_goal_progress(
    user_email: str,
    goal_accepted: int = 1,
    goal_review: int = 1,
    lookback_days: int = 30,
) -> Dict[str, Any]:
    email = (user_email or "").strip().lower()
    if not email:
        return {
            "accepted_today": 0,
            "review_today": 0,
            "goal_accepted": goal_accepted,
            "goal_review": goal_review,
            "goal_met_today": False,
            "streak_days": 0,
            "last_7_days": [],
        }
    now = int(time.time())
    start = _day_start(now) - (max(1, int(lookback_days)) - 1) * 24 * 60 * 60
    conn = _conn()
    cur = conn.cursor()
    db.execute(
        cur,
        """
        SELECT mode, status, created_ts
        FROM coding_attempt_timeline
        WHERE user_email=? AND created_ts>=?
        ORDER BY created_ts DESC
        """,
        (email, start),
    )
    rows = cur.fetchall()
    if not rows:
        ts_col = submission_ts_column(conn)
        if ts_col:
            db.execute(
                cur,
                f"""
                SELECT mode, status, {ts_col}
                FROM coding_submissions
                WHERE user_email=? AND {ts_col}>=?
                ORDER BY {ts_col} DESC
                """,
                (email, start),
            )
            rows = cur.fetchall()
    conn.close()

    per_day: Dict[str, Dict[str, int]] = {}
    for mode, status, ts in rows:
        day = time.strftime("%Y-%m-%d", time.localtime(int(ts or 0)))
        bucket = per_day.setdefault(day, {"accepted": 0, "review": 0})
        if str(mode or "").lower() == "submit" and str(status or "") == "Accepted":
            bucket["accepted"] += 1
        if str(mode or "").lower() in ("run", "submit", "hint", "interviewer"):
            bucket["review"] += 1

    today = time.strftime("%Y-%m-%d", time.localtime(now))
    today_bucket = per_day.get(today, {"accepted": 0, "review": 0})
    goal_met_today = today_bucket["accepted"] >= goal_accepted and today_bucket["review"] >= goal_review

    streak = 0
    cursor = _day_start(now)
    for _ in range(max(1, int(lookback_days))):
        key = time.strftime("%Y-%m-%d", time.localtime(cursor))
        b = per_day.get(key, {"accepted": 0, "review": 0})
        if b["accepted"] >= goal_accepted and b["review"] >= goal_review:
            streak += 1
            cursor -= 24 * 60 * 60
            continue
        break

    spark = []
    cursor = _day_start(now) - (6 * 24 * 60 * 60)
    for _ in range(7):
        key = time.strftime("%Y-%m-%d", time.localtime(cursor))
        b = per_day.get(key, {"accepted": 0, "review": 0})
        spark.append(
            {
                "day": key[5:],
                "accepted": b["accepted"],
                "review": b["review"],
                "met": b["accepted"] >= goal_accepted and b["review"] >= goal_review,
            }
        )
        cursor += 24 * 60 * 60

    return {
        "accepted_today": int(today_bucket["accepted"]),
        "review_today": int(today_bucket["review"]),
        "goal_accepted": int(goal_accepted),
        "goal_review": int(goal_review),
        "goal_met_today": bool(goal_met_today),
        "streak_days": int(streak),
        "last_7_days": spark,
    }


def personalized_practice_queue(user_email: str, current_problem_id: str = "", limit: int = 5) -> List[Dict[str, Any]]:
    problems = get_all_problems()
    if not problems:
        return []
    email = (user_email or "").strip().lower()
    solved = set()
    if email:
        conn = _conn()
        cur = conn.cursor()
        db.execute(
            cur,
            """
            SELECT DISTINCT problem_id
            FROM coding_submissions
            WHERE user_email=? AND status='Accepted' AND mode='submit'
            """,
            (email,),
        )
        solved = {str(r[0]) for r in cur.fetchall()}
        conn.close()
    weak = weak_tags_for_user(email, window_days=45) if email else []
    weak_top = [w["tag"] for w in weak[:3]]

    ranked = []
    for p in problems:
        pid = str(p.get("id") or "")
        if not pid or pid == str(current_problem_id or ""):
            continue
        tags = [str(t) for t in (p.get("tags") or [])]
        difficulty = str(p.get("difficulty") or "Easy")
        score = 0
        reasons = []
        if pid not in solved:
            score += 28
            reasons.append("Not solved yet")
        for i, tag in enumerate(weak_top):
            if tag in tags:
                score += max(6, 24 - (i * 6))
                reasons.append(f"Targets weak tag: {tag}")
                break
        if difficulty == "Easy":
            score += 8
        elif difficulty == "Medium":
            score += 11
        else:
            score += 7
        ranked.append(
            {
                "id": pid,
                "title": str(p.get("title") or pid),
                "difficulty": difficulty,
                "tags": tags,
                "reason": reasons[0] if reasons else "Balanced next-step practice",
                "score": score,
            }
        )
    ranked.sort(key=lambda x: (x["score"], x["difficulty"] == "Medium"), reverse=True)
    return ranked[: max(1, int(limit))]


def editorial_bundle(problem: Dict[str, Any], result: Dict[str, Any], code: str = "", language: str = "python") -> Dict[str, Any]:
    p = dict(problem or {})
    r = dict(result or {})
    difficulty = str(p.get("difficulty") or "Easy")
    tags = [str(t) for t in (p.get("tags") or [])]
    tag_hint = ", ".join(tags[:3]) if tags else "core data structures"
    target_complexity = "O(n)"
    if difficulty == "Medium":
        target_complexity = "O(n log n)"
    elif difficulty == "Hard":
        target_complexity = "O(n log n) or better"
    user_est = ((r.get("complexity") or {}).get("estimated") or "Unknown")
    compare = "Aligned with expected constraints"
    if user_est not in ("Unknown", target_complexity):
        if "n^2" in str(user_est).lower() and "n log n" in target_complexity.lower():
            compare = "Likely slower than ideal. Consider hash/prefix/heap strategy."
        elif "2^n" in str(user_est).lower():
            compare = "Brute-force complexity detected; optimize with memoization/dp."
    pitfalls = [
        "Input parsing edge cases (empty line, trailing spaces).",
        "Off-by-one conditions around loops or pointers.",
        "Output formatting must exactly match expected result.",
    ]
    return {
        "approach": f"Use {tag_hint} to build a deterministic solution with clear state transitions.",
        "optimal_complexity": target_complexity,
        "user_complexity": str(user_est),
        "comparison": compare,
        "pitfalls": pitfalls,
        "checklist": [
            "Cover empty/single-element input.",
            "Validate one negative/edge sample manually.",
            "Confirm final output format and separators.",
        ],
        "next_step": f"Refactor your {language} solution into small helper blocks, then rerun hidden-style tests.",
    }


def weekly_contest_set(reference_ts: int = 0) -> Dict[str, Any]:
    now = int(reference_ts or time.time())
    t = time.localtime(now)
    week = int(time.strftime("%W", t))
    year = int(t.tm_year)
    contest_id = f"{year}-W{week:02d}"
    all_probs = get_all_problems()
    easies = [p for p in all_probs if str(p.get("difficulty")) == "Easy"]
    mediums = [p for p in all_probs if str(p.get("difficulty")) == "Medium"]
    hards = [p for p in all_probs if str(p.get("difficulty")) == "Hard"]
    seed = year * 100 + week

    def _pick(rows: List[Dict[str, Any]], offset: int) -> Dict[str, Any]:
        if not rows:
            return {}
        idx = abs(seed + offset) % len(rows)
        return rows[idx]

    chosen = []
    for i, bucket in enumerate((easies, mediums, hards)):
        p = _pick(bucket, i * 17)
        if p:
            chosen.append(p)
    if not chosen:
        return {"id": contest_id, "title": "Weekly Contest", "problem_ids": [], "problems": [], "start_ts": 0, "end_ts": 0}

    week_start = _day_start(now) - (t.tm_wday * 24 * 60 * 60)
    week_end = week_start + (7 * 24 * 60 * 60)
    return {
        "id": contest_id,
        "title": f"Weekly Contest · {contest_id}",
        "problem_ids": [str(p.get("id")) for p in chosen],
        "problems": [{"id": p.get("id"), "title": p.get("title"), "difficulty": p.get("difficulty")} for p in chosen],
        "start_ts": int(week_start),
        "end_ts": int(week_end),
    }


def contest_snapshot(user_email: str = "", limit: int = 10) -> Dict[str, Any]:
    contest = weekly_contest_set()
    pids = list(contest.get("problem_ids") or [])
    if not pids:
        return {"contest": contest, "leaderboard": [], "user_rank": 0, "user_percentile": 0.0}
    conn = _conn()
    cur = conn.cursor()
    ts_col = submission_ts_column(conn)
    if not ts_col:
        conn.close()
        return {"contest": contest, "leaderboard": [], "user_rank": 0, "user_percentile": 0.0}
    placeholders = ",".join(["?"] * len(pids))
    params: List[Any] = list(pids)
    params.extend([int(contest.get("start_ts") or 0), int(contest.get("end_ts") or 0)])
    db.execute(
        cur,
        f"""
        SELECT user_email, problem_id, status, runtime_ms, {ts_col}
        FROM coding_submissions
        WHERE mode='submit' AND problem_id IN ({placeholders}) AND {ts_col}>=? AND {ts_col}<?
        ORDER BY {ts_col} DESC
        LIMIT 4000
        """,
        tuple(params),
    )
    rows = cur.fetchall()
    conn.close()

    board: Dict[str, Dict[str, Any]] = {}
    for user_email_row, pid, status, runtime_ms, ts in rows:
        user = str(user_email_row or "").strip().lower()
        if not user:
            continue
        bucket = board.setdefault(user, {"user_email": user, "by_problem": {}, "last_ts": int(ts or 0)})
        bucket["last_ts"] = max(bucket["last_ts"], int(ts or 0))
        best = bucket["by_problem"].get(pid)
        current = {"accepted": str(status or "") == "Accepted", "runtime_ms": float(runtime_ms or 0.0), "ts": int(ts or 0)}
        if best is None:
            bucket["by_problem"][pid] = current
        else:
            if current["accepted"] and (not best["accepted"] or current["runtime_ms"] < best["runtime_ms"]):
                bucket["by_problem"][pid] = current

    leaderboard = []
    for user, data in board.items():
        solved = 0
        penalty = 0.0
        for pid in pids:
            best = data["by_problem"].get(pid)
            if best and best["accepted"]:
                solved += 1
                penalty += max(1.0, best["runtime_ms"])
            elif best:
                penalty += 4500.0
        leaderboard.append(
            {
                "user_email": user,
                "solved": solved,
                "penalty": round(penalty, 1),
                "last_ts": int(data["last_ts"]),
            }
        )
    leaderboard.sort(key=lambda x: (x["solved"], -x["penalty"], -x["last_ts"]), reverse=True)
    top = leaderboard[: max(1, int(limit))]
    for idx, row in enumerate(top, start=1):
        row["rank"] = idx
    email = (user_email or "").strip().lower()
    user_rank = 0
    user_percentile = 0.0
    if email and leaderboard:
        for idx, row in enumerate(leaderboard, start=1):
            if row["user_email"] == email:
                user_rank = idx
                break
        if user_rank:
            user_percentile = round((1.0 - ((user_rank - 1) / max(1, len(leaderboard)))) * 100.0, 1)
    return {
        "contest": contest,
        "leaderboard": top,
        "user_rank": user_rank,
        "user_percentile": user_percentile,
    }


def plagiarism_alerts(limit: int = 20) -> List[Dict[str, Any]]:
    conn = _conn()
    cur = conn.cursor()
    db.execute(
        cur,
        """
        SELECT problem_id, code_hash, COUNT(*) AS total_rows, COUNT(DISTINCT user_email) AS user_count, MAX(created_ts) AS last_ts
        FROM coding_attempt_timeline
        WHERE mode='submit' AND code_hash IS NOT NULL AND code_hash<>''
        GROUP BY problem_id, code_hash
        HAVING COUNT(*) >= 2
        ORDER BY user_count DESC, total_rows DESC, last_ts DESC
        LIMIT ?
        """,
        (max(1, int(limit)),),
    )
    groups = cur.fetchall()
    alerts = []
    for problem_id, code_hash, total_rows, user_count, last_ts in groups:
        db.execute(
            cur,
            """
            SELECT user_email, code_preview, created_ts
            FROM coding_attempt_timeline
            WHERE problem_id=? AND code_hash=? AND mode='submit'
            ORDER BY created_ts DESC
            LIMIT 4
            """,
            (problem_id, code_hash),
        )
        samples = cur.fetchall()
        alerts.append(
            {
                "problem_id": str(problem_id or ""),
                "code_hash": str(code_hash or "")[:12],
                "total_rows": int(total_rows or 0),
                "user_count": int(user_count or 0),
                "last_ts": int(last_ts or 0),
                "samples": [
                    {
                        "user_email": str(s[0] or ""),
                        "code_preview": str(s[1] or ""),
                        "ts": int(s[2] or 0),
                    }
                    for s in samples
                ],
            }
        )
    conn.close()
    return alerts


def _runner_script_python(user_code: str) -> str:
    return f"""{user_code}

if __name__ == "__main__":
    import sys
    data = sys.stdin.read()
    result = solve(data)
    if result is None:
        result = ""
    sys.stdout.write(str(result))
"""


def _runner_script_js(user_code: str) -> str:
    return f"""{user_code}

const fs = require("fs");
const data = fs.readFileSync(0, "utf8");
try {{
  const out = solve(data);
  Promise.resolve(out)
    .then((val) => process.stdout.write(String(val ?? "")))
    .catch((err) => {{
      console.error(String(err));
      process.exit(1);
    }});
}} catch (e) {{
  console.error(String(e));
  process.exit(1);
}}
"""


def _runner_script_java(user_code: str) -> Tuple[str, str]:
    runner = """
import java.io.*;

public class Main {
  public static void main(String[] args) throws Exception {
    StringBuilder sb = new StringBuilder();
    BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
    String line;
    while ((line = br.readLine()) != null) {
      sb.append(line);
      sb.append("\\n");
    }
    String data = sb.toString();
    String out = Solution.solve(data);
    if (out == null) out = "";
    System.out.print(out);
  }
}
"""
    return user_code, runner


def _runner_script_cpp(user_code: str) -> str:
    return f"""{user_code}

int main() {{
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);
    std::string input((std::istreambuf_iterator<char>(std::cin)), std::istreambuf_iterator<char>());
    std::string out = solve(input);
    std::cout << out;
    return 0;
}}
"""


def run_code_once(
    code: str,
    input_data: str,
    language: str = "python",
    timeout_sec: float = 2.0,
) -> Tuple[bool, str, str, float]:
    language = (language or "python").lower()
    start = time.time()
    temp_dir = None

    try:
        temp_dir = tempfile.mkdtemp(prefix="coding-")

        if language == "javascript":
            if shutil.which("node") is None:
                return False, "", "Node.js runtime not found on server.", (time.time() - start) * 1000.0
            script_path = os.path.join(temp_dir, "main.js")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(_runner_script_js(code))
            cmd = ["node", script_path]

        elif language == "java":
            if shutil.which("javac") is None or shutil.which("java") is None:
                return False, "", "Java runtime/compiler not found on server.", (time.time() - start) * 1000.0
            solution_src, main_src = _runner_script_java(code)
            solution_path = os.path.join(temp_dir, "Solution.java")
            main_path = os.path.join(temp_dir, "Main.java")
            with open(solution_path, "w", encoding="utf-8") as f:
                f.write(solution_src)
            with open(main_path, "w", encoding="utf-8") as f:
                f.write(main_src)

            compile_proc = subprocess.run(
                ["javac", "Solution.java", "Main.java"],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=max(2.5, timeout_sec),
            )
            if compile_proc.returncode != 0:
                elapsed = (time.time() - start) * 1000.0
                return False, "", normalize_runtime_error(compile_proc.stderr.strip() or "Compilation Error"), elapsed
            cmd = ["java", "-cp", temp_dir, "Main"]

        elif language == "cpp":
            if shutil.which("g++") is None:
                return False, "", "g++ compiler not found on server.", (time.time() - start) * 1000.0
            source_path = os.path.join(temp_dir, "main.cpp")
            bin_path = os.path.join(temp_dir, "main.out")
            with open(source_path, "w", encoding="utf-8") as f:
                f.write(_runner_script_cpp(code))

            compile_proc = subprocess.run(
                ["g++", source_path, "-std=c++17", "-O2", "-o", bin_path],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=max(3.0, timeout_sec),
            )
            if compile_proc.returncode != 0:
                elapsed = (time.time() - start) * 1000.0
                return False, "", normalize_runtime_error(compile_proc.stderr.strip() or "Compilation Error"), elapsed
            cmd = [bin_path]

        else:
            script_path = os.path.join(temp_dir, "main.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(_runner_script_python(code))
            cmd = [sys.executable, script_path]

        proc = subprocess.run(
            cmd,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            cwd=temp_dir,
        )
        elapsed = (time.time() - start) * 1000.0
        ok = proc.returncode == 0
        return ok, proc.stdout, normalize_runtime_error(proc.stderr), elapsed

    except subprocess.TimeoutExpired:
        elapsed = (time.time() - start) * 1000.0
        return False, "", normalize_runtime_error("Time Limit Exceeded"), elapsed
    except Exception as e:
        elapsed = (time.time() - start) * 1000.0
        return False, "", normalize_runtime_error(f"Execution Error: {e}"), elapsed
    finally:
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass


def evaluate_submission(
    problem: Dict[str, Any],
    code: str,
    language: str = "python",
    mode: str = "run",
    custom_input: str = "",
) -> Dict[str, Any]:
    language = (language or "python").lower()
    if language not in SUPPORTED_LANGUAGES:
        language = "python"

    if mode == "run" and str(custom_input or "").strip():
        ok, out, err, elapsed = run_code_once(code, custom_input, language=language)
        actual = str(out).strip() if ok else err.strip()
        out = {
            "mode": "run_custom",
            "language": language,
            "passed": 1 if ok else 0,
            "total": 1,
            "status": "Ran" if ok else "Runtime Error",
            "runtime_ms": round(elapsed, 1),
            "failure_reason": "" if ok else "runtime_error",
            "cases": [
                {
                    "index": 1,
                    "input": custom_input,
                    "expected": "N/A (custom run)",
                    "actual": actual,
                    "diff_index": first_diff_index("N/A (custom run)", actual),
                    "passed": ok,
                    "time_ms": round(elapsed, 1),
                    "hidden": False,
                }
            ],
        }
        out["failure_reason"] = "" if ok else "runtime_error"
        out["failure_debug"] = build_failure_debug(out) if not ok else {}
        return out

    tests = list(problem.get("sample_tests", []))
    if mode == "submit":
        tests = tests + list(problem.get("hidden_tests", []))

    case_results = []
    passed = 0
    total_time = 0.0
    sample_count = len(problem.get("sample_tests", []))

    for i, case in enumerate(tests, start=1):
        ok, out, err, elapsed = run_code_once(code, case["input"], language=language)
        total_time += elapsed
        expected = str(case["expected"]).strip()
        actual = str(out).strip()
        is_pass = ok and actual == expected
        hidden = mode == "submit" and i > sample_count
        if is_pass:
            passed += 1
        case_results.append(
            {
                "index": i,
                "input": case["input"] if not hidden else "Hidden test case",
                "expected": expected if not hidden else "Hidden expected output",
                "actual": actual if ok else err.strip(),
                "diff_index": first_diff_index(expected if not hidden else "", actual if ok else err.strip()),
                "passed": is_pass,
                "time_ms": round(elapsed, 1),
                "hidden": hidden,
            }
        )

    result = {
        "mode": mode,
        "language": language,
        "passed": passed,
        "total": len(tests),
        "status": "Accepted" if passed == len(tests) else ("Partial" if passed > 0 else "Failed"),
        "runtime_ms": round(total_time, 1),
        "cases": case_results,
    }
    result["failure_reason"] = classify_failure_reason(result)
    result["complexity"] = estimate_complexity(code, language, problem.get("constraints", []))
    result["failure_debug"] = build_failure_debug(result)
    return result


def starter_for_language(problem: Dict[str, Any], language: str) -> str:
    language = (language or "python").lower()
    starters = problem.get("starter_codes", {})
    if language in starters:
        return starters[language]
    return starters.get("python", _starter_defaults()["python"])


COMPANY_SETS = {
    "Amazon": ["two-sum-indices", "merge-two-sorted", "product-except-self", "coin-change-min", "lru-cache-ops"],
    "Google": ["longest-substring-no-repeat", "group-anagrams", "kth-largest-element", "max-subarray-sum"],
    "Meta": ["valid-parentheses", "anagram-check", "first-unique-char", "climbing-stairs"],
    "Vercel": ["fizzbuzz", "reverse-string", "binary-search-index", "move-zeroes"],
}


def company_sets() -> Dict[str, List[str]]:
    return dict(COMPANY_SETS)


def get_company_problems(company: str) -> List[Dict[str, Any]]:
    name = (company or "").strip()
    if not name:
        return []
    wanted = set(COMPANY_SETS.get(name, []))
    if not wanted:
        return []
    return [p for p in get_all_problems() if p.get("id") in wanted]
