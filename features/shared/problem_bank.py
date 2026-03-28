from math import prod
from typing import Any, Callable, Dict, List


def _starter_codes() -> Dict[str, str]:
    return {
        "python": "def solve(input_data: str) -> str:\n    s = input_data.strip()\n    # Write your solution here\n    return \"\"\n",
        "javascript": "function solve(inputData) {\n  const s = inputData.trim();\n  // Write your solution here\n  return \"\";\n}\n",
        "java": "import java.util.*;\n\npublic class Solution {\n  public static String solve(String inputData) {\n    String s = inputData.trim();\n    // Write your solution here\n    return \"\";\n  }\n}\n",
        "cpp": "#include <bits/stdc++.h>\nusing namespace std;\n\nstring solve(const string& inputData) {\n    string s = inputData;\n    while (!s.empty() && (s.back() == '\\n' || s.back() == '\\r' || s.back() == ' ' || s.back() == '\\t')) s.pop_back();\n    // Write your solution here\n    return \"\";\n}\n",
    }


def _yes_no(flag: bool) -> str:
    return "YES" if flag else "NO"


def _is_prime_small(n: int) -> bool:
    if n <= 1:
        return False
    d = 2
    while d * d <= n:
        if n % d == 0:
            return False
        d += 1
    return True


def _fib_clamped(n: int) -> int:
    k = max(0, min(40, n))
    a, b = 0, 1
    for _ in range(k):
        a, b = b, a + b
    return a


def _fact_clamped(n: int) -> int:
    k = max(0, min(10, n))
    return 1 if k == 0 else prod(range(1, k + 1))


def _vowel_count(s: str) -> int:
    return sum(1 for c in s.lower() if c in "aeiou")


def _consonant_count(s: str) -> int:
    return sum(1 for c in s.lower() if c.isalpha() and c not in "aeiou")


def _make_num_problem(
    pid: str,
    title: str,
    difficulty: str,
    tags: List[str],
    description: str,
    transform: Callable[[int], str],
) -> Dict[str, Any]:
    sample_a = 7
    sample_b = -12
    return {
        "id": pid,
        "title": title,
        "difficulty": difficulty,
        "acceptance_rate": 76.0,
        "tags": tags,
        "constraints": ["-10^9 <= n <= 10^9"],
        "description": f"{description} Input: one integer n. Output: result as string.",
        "examples": [
            {"input": str(sample_a), "output": transform(sample_a)},
            {"input": str(sample_b), "output": transform(sample_b)},
        ],
        "starter_codes": _starter_codes(),
        "sample_tests": [
            {"input": str(sample_a), "expected": transform(sample_a)},
            {"input": str(sample_b), "expected": transform(sample_b)},
        ],
        "hidden_tests": [{"input": "0", "expected": transform(0)}],
    }


def _make_str_problem(
    pid: str,
    title: str,
    difficulty: str,
    tags: List[str],
    description: str,
    transform: Callable[[str], str],
) -> Dict[str, Any]:
    sample_a = "Hello World"
    sample_b = "radar"
    return {
        "id": pid,
        "title": title,
        "difficulty": difficulty,
        "acceptance_rate": 73.0,
        "tags": tags,
        "constraints": ["1 <= len(s) <= 10^5"],
        "description": f"{description} Input: one line string s. Output: transformed value.",
        "examples": [
            {"input": sample_a, "output": transform(sample_a)},
            {"input": sample_b, "output": transform(sample_b)},
        ],
        "starter_codes": _starter_codes(),
        "sample_tests": [
            {"input": sample_a, "expected": transform(sample_a)},
            {"input": sample_b, "expected": transform(sample_b)},
        ],
        "hidden_tests": [{"input": "a a a", "expected": transform("a a a")}],
    }


NUMERIC_PROBLEMS = [
    ("num-double", "Double Number", "Easy", ["Math"], "Return 2*n.", lambda n: str(2 * n)),
    ("num-triple", "Triple Number", "Easy", ["Math"], "Return 3*n.", lambda n: str(3 * n)),
    ("num-square", "Square Number", "Easy", ["Math"], "Return n^2.", lambda n: str(n * n)),
    ("num-cube", "Cube Number", "Easy", ["Math"], "Return n^3.", lambda n: str(n * n * n)),
    ("num-abs", "Absolute Value", "Easy", ["Math"], "Return |n|.", lambda n: str(abs(n))),
    ("num-sign", "Sign of Number", "Easy", ["Math"], "Return NEGATIVE, ZERO, or POSITIVE.", lambda n: "NEGATIVE" if n < 0 else ("ZERO" if n == 0 else "POSITIVE")),
    ("num-even-odd", "Even Odd Check", "Easy", ["Math", "Bit Manipulation"], "Return EVEN if n%2==0 else ODD.", lambda n: "EVEN" if n % 2 == 0 else "ODD"),
    ("num-next", "Next Integer", "Easy", ["Math"], "Return n+1.", lambda n: str(n + 1)),
    ("num-prev", "Previous Integer", "Easy", ["Math"], "Return n-1.", lambda n: str(n - 1)),
    ("num-times-ten", "Multiply by Ten", "Easy", ["Math"], "Return 10*n.", lambda n: str(10 * n)),
    ("num-half-floor", "Half Floor", "Easy", ["Math"], "Return floor(n/2).", lambda n: str(n // 2)),
    ("num-mod-10", "Last Digit", "Easy", ["Math"], "Return absolute last digit of n.", lambda n: str(abs(n) % 10)),
    ("num-digit-sum", "Digit Sum", "Easy", ["Math"], "Return sum of digits of |n|.", lambda n: str(sum(int(c) for c in str(abs(n))))),
    ("num-digit-count", "Digit Count", "Easy", ["Math"], "Return number of digits in |n|.", lambda n: str(len(str(abs(n))))),
    ("num-reverse-digits", "Reverse Digits", "Medium", ["Math", "String"], "Reverse digits of |n| and preserve sign.", lambda n: str((-1 if n < 0 else 1) * int(str(abs(n))[::-1]))),
    ("num-is-multiple-3", "Multiple of 3", "Easy", ["Math"], "Return YES if n divisible by 3 else NO.", lambda n: _yes_no(n % 3 == 0)),
    ("num-is-multiple-5", "Multiple of 5", "Easy", ["Math"], "Return YES if n divisible by 5 else NO.", lambda n: _yes_no(n % 5 == 0)),
    ("num-is-prime-small", "Prime Check (Small)", "Medium", ["Math"], "Return YES if n is prime (>1) else NO.", lambda n: _yes_no(_is_prime_small(abs(n)))),
    ("num-fibonacci-n", "Nth Fibonacci", "Medium", ["DP", "Math"], "Return F(n) for 0<=n<=40 (F0=0,F1=1).", lambda n: str(_fib_clamped(n))),
    ("num-factorial-small", "Factorial (Small)", "Medium", ["Math"], "Return n! for 0<=n<=10. Clamp negatives to 0.", lambda n: str(_fact_clamped(n))),
    ("num-sum-1-to-n", "Sum 1 to N", "Easy", ["Math"], "Return 1+2+...+n for n>=0 else 0.", lambda n: str((n * (n + 1)) // 2 if n >= 0 else 0)),
    ("num-power-two-check", "Power of Two", "Medium", ["Bit Manipulation"], "Return YES if n is a power of 2.", lambda n: _yes_no(n > 0 and (n & (n - 1)) == 0)),
    ("num-clamp-0-100", "Clamp 0..100", "Easy", ["Math"], "Return n clamped to [0,100].", lambda n: str(max(0, min(100, n)))),
    ("num-distance-zero", "Distance from Zero", "Easy", ["Math"], "Return distance of n from 0.", lambda n: str(abs(n))),
    ("num-parity-score", "Parity Score", "Easy", ["Math"], "Return 1 for odd, 0 for even.", lambda n: "1" if n % 2 else "0"),
]


STRING_PROBLEMS = [
    ("str-reverse", "Reverse String", "Easy", ["String"], "Return the reversed string.", lambda s: s[::-1]),
    ("str-uppercase", "Uppercase", "Easy", ["String"], "Convert string to uppercase.", lambda s: s.upper()),
    ("str-lowercase", "Lowercase", "Easy", ["String"], "Convert string to lowercase.", lambda s: s.lower()),
    ("str-titlecase", "Title Case", "Easy", ["String"], "Convert each word to title case.", lambda s: s.title()),
    ("str-length", "String Length", "Easy", ["String"], "Return length of s.", lambda s: str(len(s))),
    ("str-trim", "Trim Spaces", "Easy", ["String"], "Trim leading/trailing spaces.", lambda s: s.strip()),
    ("str-remove-spaces", "Remove Spaces", "Easy", ["String"], "Remove all spaces from s.", lambda s: s.replace(" ", "")),
    ("str-replace-space-hyphen", "Spaces to Hyphen", "Easy", ["String"], "Replace spaces with '-'.", lambda s: s.replace(" ", "-")),
    ("str-vowel-count", "Vowel Count", "Easy", ["String"], "Count vowels in s.", lambda s: str(_vowel_count(s))),
    ("str-consonant-count", "Consonant Count", "Easy", ["String"], "Count consonants in s.", lambda s: str(_consonant_count(s))),
    ("str-word-count", "Word Count", "Easy", ["String"], "Return number of words split by whitespace.", lambda s: str(len([w for w in s.split() if w]))),
    ("str-first-char", "First Character", "Easy", ["String"], "Return first character or EMPTY.", lambda s: s[0] if s else "EMPTY"),
    ("str-last-char", "Last Character", "Easy", ["String"], "Return last character or EMPTY.", lambda s: s[-1] if s else "EMPTY"),
    ("str-palindrome-check", "Palindrome Check", "Medium", ["String", "Two Pointers"], "Return YES if alphanumeric lowercase form is palindrome.", lambda s: _yes_no((lambda t: t == t[::-1])("".join(c.lower() for c in s if c.isalnum())))),
    ("str-anagram-self", "Anagram of Reverse", "Medium", ["String", "Hash Map"], "Return YES if s is an anagram of reverse(s).", lambda s: _yes_no(sorted(s) == sorted(s[::-1]))),
    ("str-duplicate", "Duplicate String", "Easy", ["String"], "Return s repeated twice.", lambda s: s + s),
    ("str-prefix-hello", "Add Hello Prefix", "Easy", ["String"], "Return 'Hello ' + s.", lambda s: "Hello " + s),
    ("str-suffix-exclaim", "Add Exclamation", "Easy", ["String"], "Append '!'.", lambda s: s + "!"),
    ("str-alnum-only", "Keep Alnum Only", "Easy", ["String"], "Keep only alphanumeric chars.", lambda s: "".join(c for c in s if c.isalnum())),
    ("str-sorted-chars", "Sort Characters", "Medium", ["String", "Sorting"], "Return characters of s sorted ascending.", lambda s: "".join(sorted(s))),
    ("str-unique-chars", "Unique Characters", "Medium", ["String", "Hash Set"], "Keep first occurrence of each char.", lambda s: "".join(dict.fromkeys(s))),
    ("str-count-a", "Count Letter A", "Easy", ["String"], "Count letter 'a' (case-insensitive).", lambda s: str(sum(1 for c in s.lower() if c == "a"))),
    ("str-reverse-words", "Reverse Words", "Medium", ["String"], "Reverse word order using whitespace split.", lambda s: " ".join(reversed(s.split()))),
    ("str-initials", "Word Initials", "Easy", ["String"], "Return uppercase initials of words.", lambda s: "".join(w[0].upper() for w in s.split() if w)),
    ("str-camel-spaces", "Camel to Spaces", "Medium", ["String"], "Insert spaces before uppercase letters.", lambda s: "".join((" " + c if c.isupper() and i > 0 else c) for i, c in enumerate(s)).strip()),
]


PROBLEM_BANK_50: List[Dict[str, Any]] = [
    _make_num_problem(*spec) for spec in NUMERIC_PROBLEMS
] + [
    _make_str_problem(*spec) for spec in STRING_PROBLEMS
]
