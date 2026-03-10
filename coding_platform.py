import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Tuple

DB_PATH = "bookings.db"

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
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def _json_load(raw: str, fallback: Any):
    try:
        return json.loads(raw or "")
    except Exception:
        return fallback


def _ensure_column(cur, table: str, col: str, ddl: str) -> None:
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    if col not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_coding_tables() -> None:
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
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
    _ensure_column(cur, "coding_problems", "starter_java", "starter_java TEXT")
    _ensure_column(cur, "coding_problems", "starter_cpp", "starter_cpp TEXT")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS coding_submissions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem_id TEXT,
            language TEXT,
            mode TEXT,
            status TEXT,
            passed INTEGER,
            total INTEGER,
            runtime_ms REAL,
            created_ts INTEGER
        )
        """
    )

    conn.commit()
    conn.close()


def get_all_problems(query: str = "", difficulty: str = "") -> List[Dict[str, Any]]:
    problems = list(DEFAULT_PROBLEMS)
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
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
    cur.execute(
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
    cur.execute(
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
    return changed


def delete_custom_problem(problem_id: str) -> bool:
    if not str(problem_id).startswith("custom-"):
        return False
    conn = _conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM coding_problems WHERE id=?", (problem_id,))
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
) -> None:
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO coding_submissions(problem_id,language,mode,status,passed,total,runtime_ms,created_ts)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (problem_id, language, mode, status, int(passed), int(total), float(runtime_ms), int(time.time())),
    )
    conn.commit()
    conn.close()


def get_submission_stats(limit: int = 200) -> Dict[str, Any]:
    conn = _conn()
    cur = conn.cursor()

    cur.execute(
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

    cur.execute("SELECT COUNT(*) FROM coding_submissions")
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
                return False, "", compile_proc.stderr.strip() or "Compilation Error", elapsed
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
                return False, "", compile_proc.stderr.strip() or "Compilation Error", elapsed
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
        return ok, proc.stdout, proc.stderr, elapsed

    except subprocess.TimeoutExpired:
        elapsed = (time.time() - start) * 1000.0
        return False, "", "Time Limit Exceeded", elapsed
    except Exception as e:
        elapsed = (time.time() - start) * 1000.0
        return False, "", f"Execution Error: {e}", elapsed
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
        return {
            "mode": "run_custom",
            "language": language,
            "passed": 1 if ok else 0,
            "total": 1,
            "status": "Ran" if ok else "Runtime Error",
            "runtime_ms": round(elapsed, 1),
            "cases": [
                {
                    "index": 1,
                    "input": custom_input,
                    "expected": "N/A (custom run)",
                    "actual": str(out).strip() if ok else err.strip(),
                    "passed": ok,
                    "time_ms": round(elapsed, 1),
                    "hidden": False,
                }
            ],
        }

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
                "passed": is_pass,
                "time_ms": round(elapsed, 1),
                "hidden": hidden,
            }
        )

    return {
        "mode": mode,
        "language": language,
        "passed": passed,
        "total": len(tests),
        "status": "Accepted" if passed == len(tests) else ("Partial" if passed > 0 else "Failed"),
        "runtime_ms": round(total_time, 1),
        "cases": case_results,
    }


def starter_for_language(problem: Dict[str, Any], language: str) -> str:
    language = (language or "python").lower()
    starters = problem.get("starter_codes", {})
    if language in starters:
        return starters[language]
    return starters.get("python", _starter_defaults()["python"])
