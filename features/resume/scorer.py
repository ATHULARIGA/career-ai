import json
import os
import re
from typing import Any

from features.shared import (
    call_ai_with_fallback, 
    parse_json_object, 
    validate_parsed as shared_validate_parsed, 
    clamp_score,
    safe_list
)


SCORING_KEYS = [
    "Impact", "Skills", "Projects", "ATS", "ActionVerbs", 
    "Alignment", "Quantification", "Clarity", "Formatting", "Keywords"
]

SCORE_WEIGHTS: dict[str, float] = {
    "Impact": 0.20, "Alignment": 0.18, "Quantification": 0.15,
    "Skills": 0.12, "Keywords": 0.10, "ATS": 0.08,
    "Projects": 0.07, "ActionVerbs": 0.04, "Clarity": 0.03, "Formatting": 0.03
}

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
    company_tier: str = "General",
) -> str:
    impact_rubric = """Impact (business/technical outcomes):
  9-10 = Quantified org-level outcomes (revenue, latency, user scale, cost savings)
  6-8  = Team/project-level impact with some numbers
  3-5  = Vague ownership ("worked on", "helped with")
  0-2  = No demonstrable impact"""

    tier_clean = (company_tier or "General").lower()
    if tier_clean == "faang":
        impact_rubric = """Impact (business/technical outcomes):
  9-10 = Org-level outcomes at 10M+ user scale, extreme scale metric improvements (latency in ms, cost in $M)
  6-8  = Team-level outcomes with concrete numbers and specific system scale stated
  3-5  = Vague ownership or missing scale anchors
  0-2  = No demonstrable scale or impact metrics"""
    elif tier_clean == "startup":
        impact_rubric = """Impact (business/technical outcomes):
  9-10 = Shipped features used by real users, measurable retention/revenue delta, high feature velocity
  6-8  = End-to-end ownership with some outcome/metric stated
  3-5  = Rigidly narrow duties, slow product impact signals
  0-2  = No demonstrable product ownership"""
    elif tier_clean == "enterprise":
        impact_rubric = """Impact (business/technical outcomes):
  9-10 = Cross-team process improvement, compliance/security delivered, risk reduced
  6-8  = Project delivered on time with stakeholder sign-off
  3-5  = Simple maintenance without optimization or process ownership
  0-2  = No demonstrable system responsibility"""

    return f"""<evaluation_context>
Target role: {target_role or "Not specified"}
Seniority level: {seniority or "Not specified"}
Region: {region or "India"}
Target company tier: {company_tier or "General"}
Job description provided: {"Yes — match strictly against it" if job_description.strip() else "No — infer from target role"}
</evaluation_context>

<scoring_rubrics>
Score each dimension 0–10 using these anchors (no rounding to whole numbers):

{impact_rubric}

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

<output_schema>
Return exactly this JSON structure:
{{
  "job_match_percent": 0,
  "critical_changes_required": ["..."],
  "score": {{
    "Impact": 0.0, "Skills": 0.0, "Projects": 0.0, "ATS": 0.0, "ActionVerbs": 0.0,
    "Alignment": 0.0, "Quantification": 0.0, "Clarity": 0.0, "Formatting": 0.0, "Keywords": 0.0
  }},
  "evidence": [{{"category": "Impact", "snippet": "...", "issue": "..."}}],
  "keyword_gaps": [{{"keyword": "...", "priority": "Critical|Useful|Optional", "reason": "...", "estimated_score_gain": 0.0}}],
  "targeted_rewrites": [{{"before": "...", "after": "...", "why": "...", "matched_keywords": ["..."]}}],
  "quantification_suggestions": [{{"before": "...", "after": "...", "metric_hint": "..."}}],
  "recruiter_simulation": {{
    "first_impression": "...", "strengths": ["..."], "risks": ["..."], "likely_outcome": "Advance to phone screen|Reject|Hold for later review"
  }},
  "benchmarking": {{
    "matched_requirements": 0, "total_requirements": 0, "missing_critical": [], "summary": "..."
  }},
  "interview_questions": ["..."],
  "region_advice": ["..."],
  "resume_links": [{{"url": "...", "status": "good|needs_fix", "note": "..."}}]
}}
</output_schema>

<job_description>
{job_description or "Not provided"}
</job_description>

<resume>
{text}
</resume>"""

def validate_parsed(parsed: dict) -> None:
    REQUIRED_KEYS = ["job_match_percent", "critical_changes_required", "score", "evidence", "keyword_gaps", "targeted_rewrites", "quantification_suggestions", "recruiter_simulation", "benchmarking", "interview_questions", "region_advice", "resume_links"]
    shared_validate_parsed(parsed, REQUIRED_KEYS)

    if not isinstance(parsed.get("evidence"), list) or len(parsed["evidence"]) < 2:
        raise ValueError("Evidence too sparse — likely model degradation")
    scores = parsed.get("score", {})
    if all(v == scores.get("Impact") for v in scores.values()) and scores:
        raise ValueError("All scores identical — model failed to differentiate")

def normalize_scores(raw_scores: dict[str, Any]) -> dict[str, float]:
    return {key: clamp_score(raw_scores.get(key, 0)) for key in SCORING_KEYS}

def compute_weighted_overall(scores: dict[str, float]) -> float:
    total = sum(scores.get(k, 0.0) * w for k, w in SCORE_WEIGHTS.items())
    return round(total, 1)

def extract_links_from_text(text: str) -> list[str]:
    pattern = re.compile(r"(https?://[^\s)>\]]+|www\.[^\s)>\]]+|github\.com/[^\s)>\]]+|linkedin\.com/[^\s)>\]]+)")
    matches = pattern.findall(text or "")
    unique = []
    seen = set()
    for match in matches:
        candidate = match.strip(".,;:)]}")
        if candidate.lower().startswith("www."): candidate = f"https://{candidate}"
        if candidate.lower().startswith(("github.com/", "linkedin.com/")): candidate = f"https://{candidate}"
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique[:10]

def validate_links(links: list[str]) -> list[dict[str, str]]:
    if not links: return [{"url": "No links found", "status": "missing", "note": "Add LinkedIn/GitHub/portfolio links."}]
    validated = []
    for url in links:
        if url.startswith("https://"): status, note = "format_ok", "Looks well-formed."
        elif url.startswith("http://"): status, note = "insecure_http", "Switch to HTTPS."
        else: status, note = "invalid", "Missing URL protocol."
        validated.append({"url": url, "status": status, "note": note})
    return validated

def default_report(error: str = "") -> dict[str, Any]:
    scores = {key: 0.0 for key in SCORING_KEYS}
    scores["Overall"] = 0.0
    scores["Readiness"] = "0%"
    scores["Status"] = "Needs Review"
    return {
        "error": error, "scores": scores, "evidence": [], "keyword_gaps": [], "targeted_rewrites": [],
        "quantification_suggestions": [], "recruiter_simulation": {"first_impression": "...", "strengths": [], "risks": [], "likely_outcome": "Insufficient data"},
        "benchmarking": {"matched_requirements": 0, "total_requirements": 0, "missing_critical": [], "summary": "..."},
        "interview_questions": [], "region_advice": [], "keyword_coverage": 0, "link_validation": [],
        "job_match_percent": 0, "critical_changes_required": []
    }

def score_resume(
    text: str,
    job_description: str = "",
    target_role: str = "",
    seniority: str = "",
    region: str = "US",
    company_tier: str = "General",
) -> dict[str, Any]:
    links = extract_links_from_text(text)
    local_link_checks = validate_links(links)
    user_prompt = build_evaluation_prompt(text, job_description, target_role, seniority, region, company_tier)

    try:
        parsed = call_ai_with_fallback(SYSTEM_PROMPT, user_prompt)
        validate_parsed(parsed)
        scores = normalize_scores(parsed.get("score", {}))
        overall = compute_weighted_overall(scores)
        scores["Overall"] = overall
        scores["Readiness"] = f"{int((overall / 10) * 100)}%"
        scores["Status"] = "Not Ready" if overall < 5 else "Needs Improvement" if overall < 7 else "Interview Ready"

        keyword_gaps = parsed.get("keyword_gaps", [])
        critical_count = sum(1 for g in keyword_gaps if str((g or {}).get("priority", "")).strip().lower() == "critical")
        useful_count = sum(1 for g in keyword_gaps if str((g or {}).get("priority", "")).strip().lower() == "useful")
        keyword_coverage = max(0, min(100, 100 - (critical_count * 12) - (useful_count * 6)))

        return {
            "error": "", "scores": scores, "job_match_percent": max(0, min(100, int(parsed.get("job_match_percent", 0) or 0))),
            "critical_changes_required": parsed.get("critical_changes_required", [])[:5],
            "evidence": parsed.get("evidence", [])[:8], "keyword_gaps": keyword_gaps[:7],
            "targeted_rewrites": parsed.get("targeted_rewrites", [])[:6], "quantification_suggestions": parsed.get("quantification_suggestions", [])[:6],
            "recruiter_simulation": parsed.get("recruiter_simulation", {}),
            "benchmarking": parsed.get("benchmarking", {}), "interview_questions": parsed.get("interview_questions", [])[:7],
            "region_advice": parsed.get("region_advice", [])[:6], "keyword_coverage": keyword_coverage,
            "link_validation": (parsed.get("resume_links", [])[:3] + local_link_checks)[:8]
        }
    except Exception as e:
        report = default_report(str(e))
        report["link_validation"] = local_link_checks
        return report
