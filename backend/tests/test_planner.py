"""Unit tests for the deterministic brief planner (no network, no API cost)."""
from app.planner import make_plan


def test_plan_weaves_brief_details_into_prompts():
    plan = make_plan(
        {
            "subject": "titanium water bottle",
            "audience": "urban commuters",
            "tone": "cinematic",
            "cta": "Stay hydrated.",
        }
    )
    assert "titanium water bottle" in plan.image_prompt
    assert "titanium water bottle" in plan.video_prompt
    assert "urban commuters" in plan.voiceover
    assert plan.voiceover.strip().endswith("Stay hydrated.")
    assert plan.tone == "cinematic"


def test_plan_has_sensible_defaults_for_empty_brief():
    plan = make_plan({})
    assert plan.image_prompt
    assert plan.video_prompt
    assert plan.voiceover
    assert plan.tone


def test_unknown_tone_falls_back_to_cinematic_style():
    plan = make_plan({"subject": "widget", "tone": "not-a-real-tone"})
    assert "widget" in plan.image_prompt
    assert plan.tone == "not-a-real-tone"
