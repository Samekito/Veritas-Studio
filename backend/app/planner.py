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


@dataclass
class Plan:
    title: str
    image_prompt: str
    video_prompt: str
    voiceover: str
    tone: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def heuristic_plan(brief: dict[str, Any]) -> Plan:
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

    hook = key_message or f"Meet {subject}."
    voiceover = (
        f"{hook} Designed for {audience}, it delivers exactly what you need. {cta}"
    ).strip()

    title = brief.get("title") or f"{subject.title()} — {tone.title()} Spot"

    return Plan(
        title=title,
        image_prompt=image_prompt,
        video_prompt=video_prompt,
        voiceover=voiceover,
        tone=tone,
    )


def make_plan(brief: dict[str, Any]) -> Plan:
    """Entry point for turning a brief into a concrete generation plan."""
    return heuristic_plan(brief)
