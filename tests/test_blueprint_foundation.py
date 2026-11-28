"""CI tests for Layer 1 blueprints, Layer 2 named-field decks, and Layer 4 study plans."""

from services.interview.blueprints import (
    TIER_RANK,
    build_plan,
    list_available_blueprints,
    load_blueprint,
    load_deck,
    validate_blueprint_and_deck,
)
from services.interview.cheatsheet_generator import get_cheatsheet_for_technology


def test_all_blueprints_and_decks_valid():
    techs = list_available_blueprints()
    assert len(techs) >= 17
    for tech in techs:
        bp = load_blueprint(tech)
        dk = load_deck(tech)
        assert bp is not None, f"Missing blueprint for {tech}"
        assert dk is not None, f"Missing deck for {tech}"
        errors = validate_blueprint_and_deck(bp, dk)
        assert errors == [], f"Validation errors for {tech}: {errors}"


def test_cheatsheet_payload_includes_blueprint_and_structured_cards():
    cs = get_cheatsheet_for_technology(
        "PostgreSQL",
        resume_text="Built FastAPI services backed by PostgreSQL with MVCC tuning and indexing.",
        target_role="Backend Engineer",
    )
    assert cs["tech_name"] == "PostgreSQL"
    assert cs["blueprint_summary"]["status"] == "reviewed"
    assert cs["blueprint_summary"]["must_count"] >= 3
    assert len(cs["blueprint_summary"]["areas"]) >= 2
    assert len(cs["structured_cards"]) == len(cs["cards"])
    first = cs["structured_cards"][0]
    assert first["id"]
    assert first["topic_id"]
    assert first["answer_30s"]
    assert first["tier"] in TIER_RANK


def test_build_plan_respects_time_level_and_tier():
    bp = load_blueprint("postgresql")
    assert bp is not None
    # Short 20-minute cram plan should only include a handful of high-priority cards
    short_plan = build_plan(bp, state={}, jd_weights={}, minutes_available=20, level="junior")
    assert 1 <= len(short_plan) <= 3

    # Verify no senior-only topic appears in a junior plan
    senior_ids = {
        t["id"]
        for area in bp["areas"]
        for t in area["topics"]
        if t.get("level") == "senior"
    }
    assert not (set(short_plan) & senior_ids)
