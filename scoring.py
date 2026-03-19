import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENAI_API_KEY"),
)

SCORING_KEYS = [
    "Impact",
    "Skills",
    "Projects",
    "ATS",
    "ActionVerbs",
    "Alignment",
    "Quantification",
    "Clarity",
    "Formatting",
    "Keywords",
]

# ── WEIGHTED SCORING ────────────────────────────────────────────────────────
SCORE_WEIGHTS: dict[str, float] = {
    "Impact":           0.20,   # System-level outcomes, business value
    "Alignment":        0.18,   # Role/JD match is the #1 screener
    "Quantification":   0.15,   # Measurable proof of claims
    "Skills":           0.12,   # Hard skill breadth and depth
    "Keywords":         0.10,   # ATS keyword density
    "ATS":              0.08,   # Parse-friendliness
    "Projects":         0.07,   # Ownership and complexity
    "ActionVerbs":      0.04,   # Writing quality signal
    "Clarity":          0.03,   # Readability
    "Formatting":       0.03,   # Visual structure
}
assert abs(sum(SCORE_WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"


# ── SYSTEM PROMPT SEPARATION ───────────────────────────────────────────────
SYSTEM_PROMPT = """You are an Elite Hiring Manager and Technical Principal with 15+ years vetting talent at Tier-1 companies (FAANG, top-tier startups, leading consultancies).

Your evaluation approach:
- Technical resumes: probe system ownership, scale, and architectural decisions
- Non-technical resumes: probe cross-functional impact, stakeholder influence, and measurable outcomes
- You apply the Google X-Y-Z formula rigorously: Accomplished [X] as measured by [Y] by doing [Z]
- You benchmark against real hiring bars — not aspirational ones

Output rules (STRICT):
- Return ONLY valid JSON. No markdown fences. No preamble. No trailing commentary.
- All string values must be non-empty.
- All numeric scores: one decimal precision, range 0.0–10.0.
- percentile: integer 1–99.
- job_match_percent: integer 0–100."""


def build_evaluation_prompt(
    text: str,
    job_description: str,
    target_role: str,
    seniority: str,
    region: str,
) -> str:
    # ── EXPLICIT SCORING RUBRICS ───────────────────────────────────────────
    return f"""<evaluation_context>
Target role: {target_role or "Not specified"}
Seniority level: {seniority or "Not specified"}
Region: {region or "India"}
Job description provided: {"Yes — match strictly against it" if job_description.strip() else "No — infer from target role"}
</evaluation_context>

<scoring_rubrics>
Score each dimension 0–10 using these anchors (no rounding to whole numbers):

Impact (business/technical outcomes):
  9-10 = Quantified org-level outcomes (revenue, latency, user scale, cost savings)
  6-8  = Team/project-level impact with some numbers
  3-5  = Vague ownership ("worked on", "helped with")
  0-2  = No demonstrable impact

Alignment (role/JD fit):
  9-10 = Every major JD requirement addressed with evidence
  6-8  = Most requirements covered, minor gaps
  3-5  = Surface-level title match, deep skill mismatch
  0-2  = Wrong domain entirely

Quantification:
  9-10 = 80%+ bullets have specific numbers/percentages/scale
  6-8  = 50-79% quantified
  3-5  = 20-49% quantified
  0-2  = <20% quantified

Skills:
  9-10 = Exact stack match + adjacent skills at appropriate depth
  6-8  = Core skills present, some gaps
  3-5  = Partially relevant skills, outdated tech
  0-2  = Mismatched stack

ATS (parse-ability):
  9-10 = Clean single-column, standard section headers, no tables/graphics
  6-8  = Mostly clean with minor parsing risks
  3-5  = Two-column or embedded tables likely to break parsers
  0-2  = Image-heavy, header/footer text, unparseable

ActionVerbs:
  9-10 = Every bullet opens with strong, specific verb (Architected, Reduced, Migrated)
  6-8  = Most bullets strong, occasional weak verbs
  3-5  = Passive voice, "Responsible for", "Worked on"
  0-2  = No bullets or purely narrative prose

Projects:
  9-10 = Projects show end-to-end ownership, tech choices justified, scale stated
  6-8  = Good projects, missing some ownership/context
  3-5  = Projects listed but shallow (no outcomes, no tech rationale)
  0-2  = No projects or tutorials/clones only

Clarity:
  9-10 = Each bullet is one sentence, ≤2 lines, instantly scannable in 6 seconds
  6-8  = Mostly clear, occasional wall-of-text
  3-5  = Dense paragraphs, buried key info
  0-2  = Unreadable

Formatting:
  9-10 = Consistent font, correct date format, aligned margins, 1 page/2 pages justified
  6-8  = Minor inconsistencies
  3-5  = Noticeable style chaos
  0-2  = Broken layout

Keywords:
  9-10 = All JD keywords appear naturally in context (not stuffed)
  6-8  = Most keywords present
  3-5  = Half the critical keywords missing
  0-2  = Almost no keyword overlap
</scoring_rubrics>

<scoring_example>
Resume snippet: "Worked on improving API performance."
Correct scoring:
  Impact: 2.0 — no outcome stated, no metric, passive ownership
  Quantification: 1.0 — zero numbers
  ActionVerbs: 3.0 — "Worked on" is weak

Resume snippet: "Reduced P99 API latency from 840ms to 120ms by migrating synchronous DB calls to async batch queries, serving 2M RPD."
Correct scoring:
  Impact: 9.5 — org-level outcome, specific metric, scale stated
  Quantification: 9.0 — before/after numbers + scale
  ActionVerbs: 9.0 — "Reduced" + specific action
</scoring_example>

<output_schema>
Return exactly this JSON structure:
{{
  "job_match_percent": 0,
  "critical_changes_required": [
    "..."
  ],
  "score": {{
    "Impact": 0.0,
    "Skills": 0.0,
    "Projects": 0.0,
    "ATS": 0.0,
    "ActionVerbs": 0.0,
    "Alignment": 0.0,
    "Quantification": 0.0,
    "Clarity": 0.0,
    "Formatting": 0.0,
    "Keywords": 0.0
  }},
  "evidence": [
    {{"category": "Impact", "snippet": "exact quote from resume", "issue": "specific problem and fix"}}
  ],
  "keyword_gaps": [
    {{"keyword": "...", "priority": "Critical|Useful|Optional", "reason": "...", "estimated_score_gain": 0.0}}
  ],
  "targeted_rewrites": [
    {{"before": "exact original bullet", "after": "rewritten with X-Y-Z formula", "why": "...", "matched_keywords": ["..."]}}
  ],
  "quantification_suggestions": [
    {{"before": "...", "after": "...", "metric_hint": "what to measure and where to find this number"}}
  ],
  "recruiter_simulation": {{
    "first_impression": "...",
    "strengths": ["..."],
    "risks": ["..."],
    "likely_outcome": "Advance to phone screen|Reject|Hold for later review"
  }},
  "benchmarking": {{
    "cohort": "{target_role or 'General candidate pool'}",
    "percentile": 0,
    "summary": "..."
  }},
  "interview_questions": ["..."],
  "region_advice": ["..."],
  "resume_links": [
    {{"url": "...", "status": "good|needs_fix", "note": "..."}}
  ]
}}
</output_schema>

<constraints>
- critical_changes_required: exactly 3–5 items, each starting with an action verb, specific and non-generic
- evidence: 4–8 items with DIRECT QUOTES from the resume — no paraphrasing
- keyword_gaps: up to 7, sorted by estimated_score_gain descending
- targeted_rewrites: up to 6, the "after" must include at least one metric placeholder if the original had none
- interview_questions: 5–7 questions a technical interviewer would ask based on THIS resume's specific claims
- recruiter_simulation.likely_outcome: pick exactly one of the three options listed
- DO NOT invent skills or experience not present in the resume
- DO NOT give inflated scores — hiring bars are high
- benchmarking.percentile: penalize 10+ points if Quantification < 6.0
- region_advice: 3–5 items specific to THIS resume's gaps in the given region.
  India: focus on FAANG-style quantification gaps, remote-work signals, and GitHub activity.
  US: focus on visa status clarity, location flexibility, and LinkedIn completeness.
  Do NOT give generic formatting advice here — that belongs in critical_changes_required.
</constraints>

<job_description>
{job_description or "Not provided"}
</job_description>

<resume>
{text}
</resume>"""


def call_ai_with_fallback(system: str, user: str) -> dict[str, Any]:
    models = [
        "openai/gpt-4o-mini",
        "meta-llama/llama-3.1-8b-instruct",
        "google/gemma-2-9b-it",
    ]
    last_error = None

    for model in models:
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            parsed = parse_json_object(response.choices[0].message.content)
            validate_parsed(parsed)
            print(f"AI SUCCESS using {model}")
            return parsed
        except Exception as e:
            print(f"AI FAILED using {model}: {e}")
            last_error = e

    raise Exception(f"All AI models failed: {last_error}")


def parse_json_object(raw: str) -> dict[str, Any]:
    cleaned = (raw or "").replace("```json", "").replace("```", "").strip()
    if "{" in cleaned and "}" in cleaned:
        cleaned = cleaned[cleaned.find("{") : cleaned.rfind("}") + 1]
    return json.loads(cleaned)


REQUIRED_KEYS = {"score", "evidence", "keyword_gaps", "targeted_rewrites", "recruiter_simulation", "benchmarking", "interview_questions"}

def validate_parsed(parsed: dict) -> None:
    missing = [k for k in REQUIRED_KEYS if k not in parsed]
    if missing:
        raise ValueError(f"AI response missing keys: {missing}")
    if not isinstance(parsed.get("evidence"), list) or len(parsed["evidence"]) < 2:
        raise ValueError("Evidence too sparse — likely model degradation")
    scores = parsed.get("score", {})
    if all(v == scores.get("Impact") for v in scores.values()) and scores:
        raise ValueError("All scores identical — model failed to differentiate")


def clamp_score(value: Any) -> float:
    try:
        n = float(value)
    except Exception:
        n = 0.0
    return round(max(0.0, min(10.0, n)), 1)


def normalize_scores(raw_scores: dict[str, Any]) -> dict[str, float]:
    return {key: clamp_score(raw_scores.get(key, 0)) for key in SCORING_KEYS}


def compute_weighted_overall(scores: dict[str, float]) -> float:
    """Weighted average using SCORE_WEIGHTS."""
    total = sum(scores.get(k, 0.0) * w for k, w in SCORE_WEIGHTS.items())
    return round(total, 1)


def extract_links_from_text(text: str) -> list[str]:
    pattern = re.compile(
        r"(https?://[^\s)>\]]+|www\.[^\s)>\]]+|github\.com/[^\s)>\]]+|linkedin\.com/[^\s)>\]]+)"
    )
    matches = pattern.findall(text or "")
    unique: list[str] = []
    seen: set[str] = set()
    for match in matches:
        candidate = match.strip(".,;:)]}")
        if candidate.lower().startswith("www."):
            candidate = f"https://{candidate}"
        if candidate.lower().startswith(("github.com/", "linkedin.com/")):
            candidate = f"https://{candidate}"
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique[:10]


def validate_links(links: list[str]) -> list[dict[str, str]]:
    if not links:
        return [
            {
                "url": "No links found",
                "status": "missing",
                "note": "Add LinkedIn/GitHub/portfolio links.",
            }
        ]
    validated = []
    for url in links:
        if url.startswith("https://"):
            status, note = "format_ok", "Looks well-formed. Live check not performed."
        elif url.startswith("http://"):
            status, note = "insecure_http", "Switch to HTTPS if supported."
        else:
            status, note = "invalid", "Missing URL protocol."
        validated.append({"url": url, "status": status, "note": note})
    return validated


def default_report(error: str = "") -> dict[str, Any]:
    scores = {key: 0.0 for key in SCORING_KEYS}
    scores["Overall"] = 0.0
    scores["Readiness"] = "0%"
    scores["Status"] = "Needs Review"
    return {
        "error": error,
        "scores": scores,
        "evidence": [],
        "keyword_gaps": [],
        "targeted_rewrites": [],
        "quantification_suggestions": [],
        "recruiter_simulation": {
            "first_impression": "Could not generate recruiter simulation.",
            "strengths": [],
            "risks": [],
            "likely_outcome": "Insufficient data",
        },
        "benchmarking": {"cohort": "N/A", "percentile": 0, "summary": "Benchmark unavailable."},
        "interview_questions": [],
        "region_advice": [],
        "keyword_coverage": 0,
        "link_validation": [],
        "job_match_percent": 0,
        "critical_changes_required": [],
    }


def score_resume(
    text: str,
    job_description: str = "",
    target_role: str = "",
    seniority: str = "",
    region: str = "US",
) -> dict[str, Any]:
    links = extract_links_from_text(text)
    local_link_checks = validate_links(links)

    user_prompt = build_evaluation_prompt(text, job_description, target_role, seniority, region)

    try:
        parsed = call_ai_with_fallback(SYSTEM_PROMPT, user_prompt)

        scores = normalize_scores(parsed.get("score", {}))

        overall = compute_weighted_overall(scores)
        scores["Overall"] = overall
        scores["Readiness"] = f"{int((overall / 10) * 100)}%"
        scores["Status"] = (
            "Not Ready" if overall < 5
            else "Needs Improvement" if overall < 7
            else "Interview Ready"
        )

        keyword_gaps = parsed.get("keyword_gaps", [])
        if not isinstance(keyword_gaps, list):
            keyword_gaps = []
        critical_count = sum(
            1 for g in keyword_gaps
            if str((g or {}).get("priority", "")).strip().lower() == "critical"
        )
        useful_count = sum(
            1 for g in keyword_gaps
            if str((g or {}).get("priority", "")).strip().lower() == "useful"
        )
        keyword_coverage = max(0, min(100, 100 - (critical_count * 12) - (useful_count * 6)))

        ai_links = parsed.get("resume_links", [])
        merged_links = (ai_links[:3] + local_link_checks) if isinstance(ai_links, list) and ai_links else local_link_checks

        benchmark = parsed.get("benchmarking", {}) or {}
        raw_percentile = int(benchmark.get("percentile", 0) or 0)
        percentile = max(1, min(99, raw_percentile)) if raw_percentile > 0 else 0

        job_match_percent = max(0, min(100, int(parsed.get("job_match_percent", 0) or 0)))

        critical_changes = parsed.get("critical_changes_required", [])
        if not isinstance(critical_changes, list):
            critical_changes = []

        def safe_list(key: str, limit: int) -> list:
            val = parsed.get(key, [])
            return val[:limit] if isinstance(val, list) else []

        return {
            "error": "",
            "scores": scores,
            "job_match_percent": job_match_percent,
            "critical_changes_required": critical_changes[:5],
            "evidence": safe_list("evidence", 8),
            "keyword_gaps": keyword_gaps[:7],
            "targeted_rewrites": safe_list("targeted_rewrites", 6),
            "quantification_suggestions": safe_list("quantification_suggestions", 6),
            "recruiter_simulation": parsed.get("recruiter_simulation", {}),
            "benchmarking": {
                "cohort": benchmark.get("cohort", target_role or "General candidate pool"),
                "percentile": percentile,
                "summary": benchmark.get("summary", ""),
            },
            "interview_questions": safe_list("interview_questions", 7),
            "region_advice": safe_list("region_advice", 6),
            "keyword_coverage": keyword_coverage,
            "link_validation": merged_links[:8],
        }

    except Exception as e:
        report = default_report(str(e))
        report["link_validation"] = local_link_checks
        return report
