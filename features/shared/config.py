import os
from .problem_bank import PROBLEM_BANK_50

# Coding Platform Config
CODING_MAX_CODE_CHARS = 12000
CODING_MAX_CUSTOM_INPUT_CHARS = 2000
CODING_ASYNC_JUDGE = True

DEFAULT_PROBLEMS = [
    {
        "id": "fizzbuzz",
        "title": "FizzBuzz Stream",
        "difficulty": "Easy",
        "acceptance_rate": 87.1,
        "tags": ["Math", "Simulation"],
        "constraints": ["1 <= n <= 10^5"],
        "examples": [
            {"input": "5", "output": "1\n2\nFizz\n4\nBuzz"},
            {"input": "3", "output": "1\n2\nFizz"},
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
            {"input": "2 7 11 15\n9", "output": "0 1"},
            {"input": "3 2 4\n6", "output": "1 2"},
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
]

# Add seeded coding practice bank (50 lightweight interview-style problems).
DEFAULT_PROBLEMS = DEFAULT_PROBLEMS + PROBLEM_BANK_50
