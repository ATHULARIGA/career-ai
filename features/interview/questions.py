INTERVIEW_QUESTION_BANK = {
    "python": [
        "How would you optimize a Python API endpoint that becomes CPU-bound under peak load?",
        "Explain the difference between threading, multiprocessing, and asyncio with one production use case each.",
        "How do you design robust retry logic for external API calls in Python services?",
    ],
    "sql": [
        "How do you debug a slow query in production and validate index strategy changes safely?",
        "Explain window functions with a practical example from analytics reporting.",
        "How would you detect and remove duplicate records without data loss?",
    ],
    "react": [
        "How would you prevent unnecessary re-renders in a React page with multiple data widgets?",
        "Explain how you structure state management for a medium-size product dashboard.",
        "How do you debug hydration mismatch issues in server-rendered React apps?",
    ],
    "system design": [
        "Design a rate-limited URL shortener that supports analytics and high write throughput.",
        "How would you scale a notification system for multi-channel delivery?",
        "Design a logging pipeline with low-latency search and retention controls.",
    ],
    "behavioral": [
        "Tell me about a time you disagreed with a technical direction and how you resolved it.",
        "Describe a high-pressure incident you handled and what you changed afterwards.",
        "Give an example of mentoring someone and measuring the outcome.",
    ],
}

def bank_questions(topic: str, role: str = "", round_type: str = "", limit: int = 2) -> list[str]:
    key = (topic or round_type or "behavioral").strip().lower()
    pool = INTERVIEW_QUESTION_BANK.get(key, INTERVIEW_QUESTION_BANK.get("behavioral", []))
    role = role.strip()
    seeded = []
    for q in pool[: max(1, limit)]:
        if role:
            seeded.append(f"For a {role} role: {q}")
        else:
            seeded.append(q)
    return seeded[:limit]
