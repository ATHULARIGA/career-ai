"""
Blueprint (syllabus) and named-field card deck loader, validator, and study plan builder.

Layer 1: Blueprints define the reviewed topic map per technology (areas, tier, level, weight).
Layer 2: Named-field card decks store one card per blueprint topic, validated before use.
Layer 4: build_plan() computes time-boxed study plans from blueprint weights and card states.
"""

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Optional

DATA_DIR = Path(__file__).resolve().parent / "data"
BLUEPRINTS_DIR = DATA_DIR / "blueprints"
DECKS_DIR = DATA_DIR / "decks"

TIER_RANK: dict[str, int] = {"must": 3, "common": 2, "advanced": 1}
LEVEL_RANK: dict[str, int] = {"junior": 1, "mid": 2, "senior": 3}

DEFAULT_LANG_BY_TECH: dict[str, str] = {
    "python": "python",
    "fastapi": "python",
    "django": "python",
    "postgresql": "sql",
    "sql": "sql",
    "react": "javascript",
    "nodejs": "javascript",
    "typescript": "typescript",
    "docker": "dockerfile",
    "kubernetes": "yaml",
    "aws": "bash",
    "git": "bash",
    "redis": "bash",
    "kafka": "bash",
    "mongodb": "javascript",
    "graphql": "graphql",
    "system_design": "text",
}


def compute_topic_id(tech_key: str, category: str, title: str) -> str:
    """Stable short topic/card ID derived from category and title."""
    raw = f"{(category or '').strip().lower()}::{(title or '').strip().lower()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10]
    prefix = re.sub(r"[^a-z0-9]+", "", (tech_key or "tech").lower())[:6] or "tech"
    return f"{prefix}-{digest}"


def infer_tier_level_weight(category: str, title: str, idx: int) -> tuple[str, str, int]:
    """Determines sensible default tier, level, and weight when migrating curated cards."""
    cat_l = (category or "").strip().lower()
    title_l = (title or "").strip().lower()

    if cat_l in ("basics", "architecture", "validation", "core") or idx < 5:
        tier = "must"
        weight = 9 if idx < 3 else 8
    elif cat_l in ("q&a", "performance", "concurrency", "security", "reliability"):
        tier = "must" if idx < 8 else "common"
        weight = 8 if tier == "must" else 6
    elif cat_l in ("system design", "scaling", "ops"):
        tier = "advanced"
        weight = 5
    else:
        tier = "common"
        weight = 6

    if any(k in title_l for k in ("sharding", "distributed", "mvcc", "consensus", "zero-downtime", "canary", "backpressure")):
        level = "senior"
    elif cat_l in ("basics",):
        level = "junior"
    else:
        level = "mid"

    return tier, level, weight


def list_available_blueprints() -> list[str]:
    """Returns sorted technology keys that have blueprint JSON files."""
    if not BLUEPRINTS_DIR.exists():
        return []
    return sorted(p.stem for p in BLUEPRINTS_DIR.glob("*.json"))


def load_blueprint(tech_key: str) -> Optional[dict[str, Any]]:
    """Loads a technology blueprint JSON file if it exists."""
    key = re.sub(r"[^a-z0-9_]+", "", (tech_key or "").lower().strip())
    if not key:
        return None
    path = BLUEPRINTS_DIR / f"{key}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_deck(tech_key: str) -> Optional[dict[str, Any]]:
    """Loads a technology named-field card deck JSON file if it exists."""
    key = re.sub(r"[^a-z0-9_]+", "", (tech_key or "").lower().strip())
    if not key:
        return None
    path = DECKS_DIR / f"{key}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def card_to_legacy_row(card: dict[str, Any]) -> list[str]:
    """Converts a named-field card dict into the legacy 6-element list format."""
    code_obj = card.get("code") or {}
    code_body = code_obj.get("body", "") if isinstance(code_obj, dict) else str(code_obj)
    pitfalls = card.get("pitfalls") or []
    pitfall_text = pitfalls[0] if isinstance(pitfalls, list) and pitfalls else str(pitfalls or "")
    return [
        str(card.get("category", "Core")),
        str(card.get("title") or card.get("question", "")),
        str(card.get("answer_30s", "")),
        str(code_body),
        str(card.get("typical_use", "")),
        str(pitfall_text),
    ]


def summarize_blueprint(blueprint: dict[str, Any], deck: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Returns coverage summary metadata for UI trust signals and dashboards."""
    areas = blueprint.get("areas") or []
    total_topics = 0
    must_count = 0
    common_count = 0
    advanced_count = 0
    area_summaries: list[dict[str, Any]] = []

    for area in areas:
        topics = area.get("topics") or []
        total_topics += len(topics)
        for t in topics:
            tier = t.get("tier", "common")
            if tier == "must":
                must_count += 1
            elif tier == "advanced":
                advanced_count += 1
            else:
                common_count += 1
        area_summaries.append({
            "id": area.get("id", ""),
            "name": area.get("name", ""),
            "topic_count": len(topics),
            "topic_ids": [t.get("id", "") for t in topics],
        })

    cards = (deck or {}).get("cards") or []
    reviewed_count = sum(1 for c in cards if c.get("status") == "reviewed")
    status = "reviewed" if cards and reviewed_count == len(cards) else "ai_unreviewed"

    return {
        "tech": blueprint.get("tech", ""),
        "version": blueprint.get("version", ""),
        "total_topics": total_topics,
        "must_count": must_count,
        "common_count": common_count,
        "advanced_count": advanced_count,
        "areas": area_summaries,
        "status": status,
    }


def validate_blueprint_and_deck(blueprint: dict[str, Any], deck: dict[str, Any]) -> list[str]:
    """
    Validates schema completeness, must-topic coverage, non-empty answers,
    absence of known fabricated metric strings, and Python code syntax.
    Returns a list of error strings (empty means valid).
    """
    errors: list[str] = []
    if not isinstance(blueprint, dict) or not blueprint.get("areas"):
        return ["Blueprint missing areas"]
    if not isinstance(deck, dict) or not deck.get("cards"):
        return ["Deck missing cards"]

    cards = deck["cards"]
    cards_by_topic: dict[str, dict[str, Any]] = {}
    for idx, card in enumerate(cards):
        cid = card.get("id")
        tid = card.get("topic_id")
        if not cid or not tid:
            errors.append(f"Card {idx} missing id or topic_id")
            continue
        cards_by_topic[tid] = card
        answer_30s = (card.get("answer_30s") or "").strip()
        if not answer_30s:
            errors.append(f"Card {cid} missing answer_30s")

        # Guard against known fabricated metrics
        use_text = (card.get("typical_use") or "").lower()
        for banned in ("320ms to 42ms", "45m+ rows", "40+ containerized", "mttr) by 60%"):
            if banned in use_text:
                errors.append(f"Card {cid} contains fabricated metric: {banned}")

        # Validate Python code snippets when complete statements are provided
        code_obj = card.get("code") or {}
        if isinstance(code_obj, dict) and code_obj.get("lang") == "python":
            body = (code_obj.get("body") or "").strip()
            if body and not body.startswith("#"):
                try:
                    ast.parse(body)
                except SyntaxError as exc:
                    errors.append(f"Card {cid} has invalid Python syntax: {exc}")

    for area in blueprint["areas"]:
        for topic in area.get("topics") or []:
            tid = topic.get("id", "")
            tier = topic.get("tier", "common")
            level = topic.get("level", "mid")
            if tier not in TIER_RANK:
                errors.append(f"Topic {tid} has invalid tier: {tier}")
            if level not in LEVEL_RANK:
                errors.append(f"Topic {tid} has invalid level: {level}")
            if tier == "must" and tid not in cards_by_topic:
                errors.append(f"Must-know topic {tid} has no matching card in deck")

    return errors


def build_plan(
    blueprint: dict[str, Any],
    state: Optional[dict[str, str]] = None,
    jd_weights: Optional[dict[str, float]] = None,
    minutes_available: int = 60,
    level: str = "senior",
) -> list[str]:
    """
    Computes an ordered list of topic_ids fitting within minutes_available,
    prioritizing must-tier items, JD relevance weights, and unmastered cards.
    """
    state = state or {}
    jd_weights = jd_weights or {}
    max_level = LEVEL_RANK.get(level, 3)

    candidates: list[tuple[int, float, str, int]] = []
    for area in blueprint.get("areas") or []:
        for topic in area.get("topics") or []:
            tid = topic.get("id", "")
            t_level = LEVEL_RANK.get(topic.get("level", "mid"), 2)
            if t_level > max_level:
                continue
            tier = topic.get("tier", "common")
            weight = float(topic.get("weight", 5))
            card_state = state.get(tid, "new")
            state_mult = 2.0 if card_state in ("new", "missed") else (1.2 if card_state == "shaky" else 0.5)
            score = weight * float(jd_weights.get(tid, 1.0)) * state_mult
            cost = 6 if tier == "must" else 8
            candidates.append((TIER_RANK.get(tier, 2), score, tid, cost))

    candidates.sort(key=lambda item: (-item[0], -item[1]))
    plan: list[str] = []
    used = 0
    for _tier_rank, _score, tid, cost in candidates:
        if used + cost > minutes_available:
            continue
        plan.append(tid)
        used += cost
    return plan
