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


def call_ai_with_fallback(prompt: str):
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
                messages=[{"role": "user", "content": prompt}],
            )
            print(f"AI SUCCESS using {model}")
            return response
        except Exception as e:
            print(f"AI FAILED using {model}")
            last_error = e

    raise Exception(f"All AI models failed: {last_error}")


def parse_json_object(raw: str) -> dict[str, Any]:
    cleaned = (raw or "").replace("```json", "").replace("```", "").strip()
    if "{" in cleaned and "}" in cleaned:
        cleaned = cleaned[cleaned.find("{"):cleaned.rfind("}") + 1]
    return json.loads(cleaned)


def clamp_score(value: Any) -> float:
    try:
        n = float(value)
    except Exception:
        n = 0.0
    return round(max(0.0, min(10.0, n)), 1)


def normalize_scores(raw_scores: dict[str, Any]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for key in SCORING_KEYS:
        scores[key] = clamp_score(raw_scores.get(key, 0))
    return scores


def extract_links_from_text(text: str) -> list[str]:
    pattern = re.compile(
        r"(https?://[^\s)>\]]+|www\.[^\s)>\]]+|github\.com/[^\s)>\]]+|linkedin\.com/[^\s)>\]]+)"
    )
    matches = pattern.findall(text or "")
    unique: list[str] = []
    seen = set()
    for match in matches:
        candidate = match.strip(".,;:)]}")
        if candidate.lower().startswith("www."):
            candidate = f"https://{candidate}"
        if candidate.lower().startswith("github.com/") or candidate.lower().startswith("linkedin.com/"):
            candidate = f"https://{candidate}"
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique[:10]


def validate_links(links: list[str]) -> list[dict[str, str]]:
    if not links:
        return [{"url": "No links found", "status": "missing", "note": "Add LinkedIn/GitHub/portfolio links."}]

    validated = []
    for url in links:
        if url.startswith("https://"):
            status = "format_ok"
            note = "Looks well-formed. Live reachability check not performed."
        elif url.startswith("http://"):
            status = "insecure_http"
            note = "Switch to HTTPS if supported."
        else:
            status = "invalid"
            note = "Missing URL protocol."
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
        "benchmarking": {
            "cohort": "N/A",
            "percentile": 0,
            "summary": "Benchmark unavailable.",
        },
        "interview_questions": [],
        "region_advice": [],
        "keyword_coverage": 0,
        "link_validation": [],
    }


def score_resume(
    text: str,
    job_description: str = "",
    target_role: str = "",
    seniority: str = "",
    region: str = "US",
):
    links = extract_links_from_text(text)
    local_link_checks = validate_links(links)

    prompt = f"""
You are an Elite Hiring Manager and Technical Principal with 15+ years of experience vetting talent for {target_role or 'this role'} at Tier-1 companies.
Evaluate this resume with extreme scrutiny. Look beyond keyword match rates: assess technical ownership, system-level impact, and execution scope. Return valid JSON only.

Context:
- Target role: {target_role or "Not provided"}
- Seniority: {seniority or "Not provided"}
- Region mode: {region or "US"}
- Job description provided: {"Yes" if job_description.strip() else "No"}

Return this schema exactly:
{{
  "job_match_percent": 0,
  "critical_changes_required": [
    "..."
  ],
  "score": {{
    "Impact": 0,
    "Skills": 0,
    "Projects": 0,
    "ATS": 0,
    "ActionVerbs": 0,
    "Alignment": 0,
    "Quantification": 0,
    "Clarity": 0,
    "Formatting": 0,
    "Keywords": 0
  }},
  "evidence": [
    {{"category":"Impact","snippet":"...","issue":"..."}}
  ],
  "keyword_gaps": [
    {{"keyword":"...","priority":"Critical|Useful|Optional","reason":"...","estimated_score_gain":0.0}}
  ],
  "targeted_rewrites": [
    {{"before":"...","after":"...","why":"...","matched_keywords":["..."]}}
  ],
  "quantification_suggestions": [
    {{"before":"...","after":"...","metric_hint":"..."}}
  ],
  "recruiter_simulation": {{
    "first_impression":"...",
    "strengths":["..."],
    "risks":["..."],
    "likely_outcome":"..."
  }},
  "benchmarking": {{
    "cohort":"{target_role or "General candidate pool"}",
    "percentile":0,
    "summary":"..."
  }},
  "interview_questions": ["..."],
  "region_advice": ["..."],
  "resume_links": [
    {{"url":"...","status":"good|needs_fix","note":"..."}}
  ]
}}

Rules:
- Act as a senior field expert. Deliver blunt, direct, and constructive criticism. Avoid generic encouraging filler.
- Evaluate bullet items using the Google X-Y-Z formula (Accomplished [X] as measured by [Y], by doing [Z]). Identify if quantifiable impact or system-level ownership is missing.
- Calculate `job_match_percent` as a strict integer 0-100 indicating direct matching with the provided job description (or target role if empty).
- Base `critical_changes_required` on top capability or alignment gaps with high-impact triggers. Define exactly 3 to 5 direct actionable upgrades.
- Use 0-10 scoring scale with one decimal precision for subcategories.
- Provide 4-8 evidence items, each referencing specific resume excerpts or quotes.
- Up to 7 keyword gaps sorted by impact and Up to 6 targeted rewrites.
- Benchmark percentile must be an integer 1-99. Keep all text concise and actionable.

Job Description:
{job_description or "Not provided"}

Resume:
{text}
"""

    try:
        response = call_ai_with_fallback(prompt)
        print("MODEL USED:", response.model)
        parsed = parse_json_object(response.choices[0].message.content)

        scores = normalize_scores(parsed.get("score", {}))
        overall = round(sum(scores.values()) / len(scores), 1)
        scores["Overall"] = overall
        scores["Readiness"] = f"{int((overall / 10) * 100)}%"
        if overall < 5:
            scores["Status"] = "Not Ready"
        elif overall < 7:
            scores["Status"] = "Needs Improvement"
        else:
            scores["Status"] = "Interview Ready"

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
        if not isinstance(ai_links, list):
            ai_links = []
        merged_links = local_link_checks
        if ai_links:
            merged_links = ai_links[:3] + local_link_checks

        benchmark = parsed.get("benchmarking", {})
        if not isinstance(benchmark, dict):
            benchmark = {}
        percentile = benchmark.get("percentile", 0)
        try:
            percentile = int(percentile)
        except Exception:
            percentile = 0
        percentile = max(1, min(99, percentile)) if percentile else 0

        job_match_percent = parsed.get("job_match_percent", 0)
        try:
            job_match_percent = int(job_match_percent)
            job_match_percent = max(0, min(100, job_match_percent))
        except Exception:
            job_match_percent = 0
            
        critical_changes_required = parsed.get("critical_changes_required", [])
        if not isinstance(critical_changes_required, list):
            critical_changes_required = []

        return {
            "error": "",
            "scores": scores,
            "job_match_percent": job_match_percent,
            "critical_changes_required": critical_changes_required[:5],
            "evidence": parsed.get("evidence", [])[:8] if isinstance(parsed.get("evidence", []), list) else [],
            "keyword_gaps": keyword_gaps[:7],
            "targeted_rewrites": parsed.get("targeted_rewrites", [])[:6] if isinstance(parsed.get("targeted_rewrites", []), list) else [],
            "quantification_suggestions": parsed.get("quantification_suggestions", [])[:6] if isinstance(parsed.get("quantification_suggestions", []), list) else [],
            "recruiter_simulation": parsed.get("recruiter_simulation", {}),
            "benchmarking": {
                "cohort": benchmark.get("cohort", target_role or "General candidate pool"),
                "percentile": percentile,
                "summary": benchmark.get("summary", "Benchmark generated from role-level expectations."),
            },
            "interview_questions": parsed.get("interview_questions", [])[:7] if isinstance(parsed.get("interview_questions", []), list) else [],
            "region_advice": parsed.get("region_advice", [])[:6] if isinstance(parsed.get("region_advice", []), list) else [],
            "keyword_coverage": keyword_coverage,
            "link_validation": merged_links[:8],
        }

    except Exception as e:
        report = default_report(str(e))
        report["link_validation"] = local_link_checks
        report["job_match_percent"] = 0
        report["critical_changes_required"] = []
        return report
