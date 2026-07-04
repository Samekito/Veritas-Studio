"""The Veritas hero pipeline — a multi-step, multi-model Genblaze workflow.

Flow ("chain" mode):
    text  ->  keyframe image (Seedream, fallback Gemini)
          ->  image-to-video (Kling, conditioned on the keyframe)
          ->  voiceover (MiniMax TTS via GMI Cloud)

Every run writes its media AND a cryptographic provenance manifest to Backblaze
B2, then we verify the manifest and index everything locally.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from collections import OrderedDict
from typing import Any

from genblaze_core import Modality, Pipeline
from genblaze_core.providers.model_registry import ModelSpec
from genblaze_gmicloud import (
    GMICloudAudioProvider,
    GMICloudImageProvider,
    GMICloudVideoProvider,
)

from . import db
from .config import settings
from .logging_setup import get_logger
from .planner import Plan, make_plan
from .storage import make_sink

log = get_logger("veritas.pipeline")

# Keep recent PipelineResults in-process so a "refine" can link lineage via
# Pipeline.from_result() within the running server. Bounded LRU so it can't grow
# without limit; volatile by design (cleared on restart — lineage is best-effort).
_RECENT_RESULTS_MAX = 32
_recent_results: "OrderedDict[str, Any]" = OrderedDict()
_recent_lock = threading.Lock()


def _remember_result(run_id: str, result: Any) -> None:
    with _recent_lock:
        _recent_results[run_id] = result
        _recent_results.move_to_end(run_id)
        while len(_recent_results) > _RECENT_RESULTS_MAX:
            _recent_results.popitem(last=False)


def _get_result(run_id: str) -> Any | None:
    with _recent_lock:
        return _recent_results.get(run_id)

_STAGE_LABELS = {
    0: "Rendering keyframe image",
    1: "Animating video",
    2: "Generating voiceover",
}


def _audio_provider() -> GMICloudAudioProvider:
    """GMI audio provider with a corrected spec for the TTS model.

    GMI's MiniMax TTS API requires the script under a `text` key, but the model's
    bundled spec allowlists `prompt` (not `text`) with no mapping — so the script
    is silently dropped. We fork the registry and alias `prompt -> text`, adding
    `text` to the allowlist. Falls back to the stock provider if the registry
    internals change in a future SDK version.
    """
    base = GMICloudAudioProvider()
    try:
        reg = base._models.fork()
        spec = reg.get(settings.audio_model)
        allow = set(spec.param_allowlist or ()) | {"text"}
        reg.register(
            ModelSpec(
                model_id=settings.audio_model,
                modality=Modality.AUDIO,
                param_aliases={"prompt": "text"},
                param_allowlist=frozenset(allow),
                extras=dict(spec.extras),
                pricing=spec.pricing,
            ),
            override=True,
        )
        return GMICloudAudioProvider(models=reg)
    except Exception:
        return base


def _on_step_complete(job_id: str):
    state = {"done": 0}

    def cb(event: Any) -> None:  # defensive: event shape varies across versions
        try:
            state["done"] += 1
            nxt = state["done"]
            label = _STAGE_LABELS.get(nxt, "Finalizing")
            db.update_job(job_id, stage=label)
        except Exception:
            pass

    return cb


def _build_pipeline(job_id: str, plan: Plan, parent_result: Any | None) -> Pipeline:
    chain = settings.pipeline_mode == "chain"
    pipe = Pipeline(f"veritas-{job_id}", project_id="veritas-studio", chain=chain)

    if parent_result is not None:
        pipe = pipe.from_result(parent_result)

    if chain:
        # 1) keyframe image (text -> image)
        pipe = pipe.step(
            GMICloudImageProvider(),
            model=settings.image_model,
            prompt=plan.image_prompt,
            modality=Modality.IMAGE,
            fallback_models=settings.image_fallbacks or None,
        )
        # 2) image-to-video, conditioned on the keyframe from step 0
        pipe = pipe.step(
            GMICloudVideoProvider(),
            model=settings.video_model,
            prompt=plan.video_prompt,
            modality=Modality.VIDEO,
            input_from=0,
            fallback_models=settings.video_fallbacks or None,
            duration=settings.video_duration,
            aspect_ratio=settings.aspect_ratio,
        )
    else:
        # text -> video directly
        pipe = pipe.step(
            GMICloudVideoProvider(),
            model=settings.video_fallbacks[0] if settings.video_fallbacks else "Kling-Text2Video-V2.1-Master",
            prompt=plan.video_prompt,
            modality=Modality.VIDEO,
            duration=settings.video_duration,
            aspect_ratio=settings.aspect_ratio,
        )

    # voiceover — pure text-to-speech, NOT chained from the video step
    audio_params: dict[str, Any] = {}
    if settings.voice_id:
        audio_params["voice_id"] = settings.voice_id
    pipe = pipe.step(
        _audio_provider(),
        model=settings.audio_model,
        prompt=plan.voiceover,
        modality=Modality.AUDIO,
        input_from=[],  # explicitly no media input even in chain mode
        fallback_models=settings.audio_fallbacks or None,
        **audio_params,
    )
    return pipe


def _index_result(job_id: str, plan: Plan, result: Any) -> dict[str, Any]:
    run = result.run
    manifest = result.manifest

    cost = 0.0
    asset_count = 0
    steps_detail: list[dict[str, Any]] = []
    now = time.time()
    for i, step in enumerate(run.steps):
        step_assets = getattr(step, "assets", []) or []
        steps_detail.append(
            {
                "index": getattr(step, "step_index", i),
                "provider": str(getattr(step, "provider", "")),
                "model": getattr(step, "model", None),
                "modality": str(getattr(step, "modality", "") or ""),
                "status": str(getattr(step, "status", "") or ""),
                "error": getattr(step, "error", None),
                "error_code": getattr(step, "error_code", None),
                "retries": getattr(step, "retries", 0),
                "cost_usd": getattr(step, "cost_usd", None),
                "url": (getattr(step_assets[0], "url", None) if step_assets else None),
            }
        )
        for asset in step_assets:
            asset_count += 1
            db.add_asset(
                {
                    "id": str(uuid.uuid4()),
                    "job_id": job_id,
                    "run_id": getattr(run, "run_id", None),
                    "step_index": i,
                    "modality": getattr(step, "modality", None) and str(step.modality),
                    "provider": str(getattr(step, "provider", "")),
                    "model": getattr(step, "model", None),
                    "url": getattr(asset, "url", None),
                    "sha256": getattr(asset, "sha256", None),
                    "media_type": getattr(asset, "media_type", None),
                    "created_at": now,
                }
            )
        step_cost = getattr(step, "cost_usd", None)
        if step_cost:
            cost += float(step_cost)

    try:
        verified = bool(manifest.verify())
    except Exception:
        verified = False

    try:
        manifest_json = manifest.model_dump_json()
    except Exception:
        manifest_json = "{}"

    # A run that produced no assets is a failure, even if the SDK returned "ok".
    failed_steps = [s for s in steps_detail if s.get("error") or "fail" in s.get("status", "").lower()]
    status = "completed" if asset_count > 0 else "failed"
    stage = "Completed" if asset_count > 0 else "Failed"

    if asset_count == 0:
        error = failed_steps[0]["error"] if failed_steps else "Pipeline returned no assets"
    elif failed_steps:
        # Partial success: some steps produced assets, but at least one failed.
        s = failed_steps[0]
        error = f"Partial: step {s['index']} ({s['model']}) failed — {s['error']}"
    else:
        error = None

    db.update_job(
        job_id,
        status=status,
        stage=stage,
        error=error,
        steps=json.dumps(steps_detail),
        plan=json.dumps(plan.to_dict()),
        run_id=getattr(run, "run_id", None),
        manifest_uri=getattr(manifest, "manifest_uri", None),
        manifest_hash=getattr(manifest, "canonical_hash", None),
        manifest_json=manifest_json,
        verified=1 if verified else 0,
        cost_usd=round(cost, 4),
    )
    return {"run_id": getattr(run, "run_id", None), "verified": verified,
            "cost_usd": cost, "status": status}


def run_generation(job_id: str, brief: dict[str, Any]) -> None:
    """Blocking: runs the full pipeline. Call from a background thread."""
    try:
        db.update_job(job_id, status="running", stage="Planning")
        plan = make_plan(brief)
        db.update_job(job_id, title=plan.title, plan=json.dumps(plan.to_dict()))

        parent_run_id = brief.get("parent_run_id")
        parent_result = _get_result(parent_run_id) if parent_run_id else None

        pipe = _build_pipeline(job_id, plan, parent_result)
        db.update_job(job_id, stage="Generating media")

        result = pipe.run(
            sink=make_sink(),
            timeout=600,
            pipeline_timeout=1200,
            max_retries=1,
            fail_fast=False,
            on_step_complete=_on_step_complete(job_id),
        )

        summary = _index_result(job_id, plan, result)
        if summary.get("run_id"):
            _remember_result(summary["run_id"], result)
        log.info("job finished", extra={"job_id": job_id, "status": summary.get("status"),
                                        "cost_usd": summary.get("cost_usd")})
    except Exception as exc:
        # Store a generic, non-leaky error for the client; log the detail server-side.
        log.exception("job failed", extra={"job_id": job_id})
        db.update_job(job_id, status="failed", stage="Failed",
                      error=f"Generation failed ({type(exc).__name__})")
