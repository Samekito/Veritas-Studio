"""Turn a creative brief into a concrete, multi-step generation plan.

The planner is deliberately deterministic (no external LLM required) so the app
is reliable for judging. It expands a short brief into three production-ready
prompts: a keyframe image prompt, a motion/video prompt, and a voiceover script.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

_TONE_STYLE = {
    "cinematic": "cinematic, dramatic lighting, shallow depth of field, film grain, 35mm",
    "energetic": "vibrant, high-contrast, dynamic composition, bold colors, punchy",
    "elegant": "elegant, minimal, soft natural light, premium product photography",
    "playful": "playful, bright pastel palette, fun, whimsical, friendly",
    "corporate": "clean, professional, modern, neutral palette, polished",
    "futuristic": "futuristic, neon accents, sleek, high-tech, cyberpunk lighting",
}

_TONE_MOTION = {
    "cinematic": "slow cinematic dolly-in, gentle parallax, atmospheric",
    "energetic": "fast dynamic camera moves, quick push-in, lively motion",
    "elegant": "smooth slow orbit, graceful slow motion, refined",
    "playful": "bouncy playful camera, light handheld motion",
    "corporate": "steady controlled pan, confident reveal",
    "futuristic": "sweeping fly-through, sci-fi camera glide",
}


# Voiceover length budget. Calibrated against this pipeline's own MiniMax TTS
# output: 158 chars -> 9.89s and 119 chars -> 8.19s. Two samples can't separate a
# per-character speaking rate (~14.5-16 chars/s) from fixed lead-in/out silence
# (a linear fit suggests ~3s + 22.9 chars/s), so the budget is deliberately
# conservative — it lands a 5s script at roughly 4.1-5.6s under either reading,
# a range the player's rate-matching absorbs without sounding rushed.
_CHARS_PER_SECOND = 12.0
_MIN_VOICEOVER_CHARS = 30
DEFAULT_CLIP_SECONDS = 5.0


def _clamp_to_budget(text: str, budget: int) -> str:
    """Trim an over-long lead line at a word boundary rather than mid-word."""
    if len(text) <= budget:
        return text
    room = budget - 1  # the trailing period has to fit inside the budget too
    head = text[:room].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return f"{head or text[:room]}."


def _fit_voiceover(lead: str, audience_line: str, cta: str, clip_seconds: float) -> str:
    """Longest version of the script that still fits the clip.

    Drops the audience line first, then the CTA — the lead always survives, since
    a spot with no hook is worse than a short one.
    """
    budget = max(_MIN_VOICEOVER_CHARS, int(clip_seconds * _CHARS_PER_SECOND))
    for candidate in ([lead, audience_line, cta], [lead, cta], [lead]):
        line = " ".join(part for part in candidate if part).strip()
        if len(line) <= budget:
            return line
    return _clamp_to_budget(lead, budget)


@dataclass
class Plan:
    title: str
    image_prompt: str
    video_prompt: str
    voiceover: str
    tone: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def heuristic_plan(brief: dict[str, Any], clip_seconds: float = DEFAULT_CLIP_SECONDS) -> Plan:
    subject = (brief.get("subject") or "the product").strip()
    audience = (brief.get("audience") or "everyone").strip()
    tone = (brief.get("tone") or "cinematic").strip().lower()
    key_message = (brief.get("message") or "").strip()
    cta = (brief.get("cta") or "Learn more today.").strip()

    style = _TONE_STYLE.get(tone, _TONE_STYLE["cinematic"])
    motion = _TONE_MOTION.get(tone, _TONE_MOTION["cinematic"])

    image_prompt = (
        f"A striking hero shot of {subject}, {style}, professional advertising photography, "
        f"highly detailed, crisp focus, studio-grade composition, no text, no watermark"
    )

    video_prompt = (
        f"{subject} presented in a short ad, {motion}, {style}, seamless looping motion, "
        f"high production value"
    )

    # Sized to the clip, not to the page. A script that outruns the video has to
    # be sped up to fit, which makes the read sound rushed.
    lead = f"{(key_message or f'Meet {subject}').rstrip(' .')}."
    voiceover = _fit_voiceover(lead, f"Made for {audience}.", cta, clip_seconds)

    title = brief.get("title") or f"{subject.title()} — {tone.title()} Spot"

    return Plan(
        title=title,
        image_prompt=image_prompt,
        video_prompt=video_prompt,
        voiceover=voiceover,
        tone=tone,
    )


def make_plan(brief: dict[str, Any], clip_seconds: float = DEFAULT_CLIP_SECONDS) -> Plan:
    """Entry point for turning a brief into a concrete generation plan.

    `clip_seconds` is the configured video length; it bounds the voiceover so the
    two tracks come out roughly the same duration.
    """
    return heuristic_plan(brief, clip_seconds)
