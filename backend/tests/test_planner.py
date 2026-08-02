"""Unit tests for the deterministic brief planner (no network, no API cost)."""
from app.planner import _CHARS_PER_SECOND, make_plan

BRIEF = {
    "subject": "titanium water bottle",
    "audience": "urban commuters",
    "tone": "cinematic",
    "cta": "Stay hydrated.",
}


def test_plan_weaves_brief_details_into_prompts():
    plan = make_plan(BRIEF)
    assert "titanium water bottle" in plan.image_prompt
    assert "titanium water bottle" in plan.video_prompt
    assert "titanium water bottle" in plan.voiceover
    assert plan.voiceover.strip().endswith("Stay hydrated.")
    assert plan.tone == "cinematic"


def test_audience_line_yields_to_the_clip_budget():
    """A 5s spot has no room for the audience line; the hook and CTA outrank it."""
    short = make_plan(BRIEF, clip_seconds=5)
    assert "urban commuters" not in short.voiceover
    assert short.voiceover.endswith("Stay hydrated.")

    # Given room, it comes back — the line is dropped for length, not removed.
    roomy = make_plan(BRIEF, clip_seconds=12)
    assert "urban commuters" in roomy.voiceover


def test_plan_has_sensible_defaults_for_empty_brief():
    plan = make_plan({})
    assert plan.image_prompt
    assert plan.video_prompt
    assert plan.voiceover
    assert plan.tone


def test_voiceover_stays_within_the_clip_budget():
    """No brief — however wordy — may produce speech that outruns the video."""
    clip_seconds = 5
    budget = int(clip_seconds * _CHARS_PER_SECOND)
    briefs = [
        {},
        {"subject": "a minimalist titanium water bottle"},
        {"subject": "a sleek noise-cancelling headphone", "audience": "commuters"},
        # Long free-text fields are what used to blow past the clip length.
        {
            "subject": "sneakers",
            "message": "Run further than you ever thought possible on any terrain",
            "audience": "marathon runners training year round",
            "cta": "Find your pair at any store nationwide today.",
        },
        {"subject": "x", "message": "A" * 300, "cta": "Buy now."},
    ]
    for brief in briefs:
        vo = make_plan(brief, clip_seconds=clip_seconds).voiceover
        assert vo, f"{brief} produced an empty voiceover"
        assert len(vo) <= budget, f"{brief} produced {len(vo)} chars (budget {budget})"


def test_longer_clips_get_longer_scripts():
    assert len(make_plan(BRIEF, clip_seconds=15).voiceover) > len(
        make_plan(BRIEF, clip_seconds=5).voiceover
    )


def test_unknown_tone_falls_back_to_cinematic_style():
    plan = make_plan({"subject": "widget", "tone": "not-a-real-tone"})
    assert "widget" in plan.image_prompt
    assert plan.tone == "not-a-real-tone"
