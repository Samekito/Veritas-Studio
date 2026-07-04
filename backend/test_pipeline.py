"""Integration test: run the REAL app pipeline (chain mode + audio) end to end.

Exercises exactly what the web app runs — planner -> Genblaze chain (image ->
image-to-video) -> voiceover -> B2 -> manifest verify -> SQLite index — so we
validate the two paths the smoke test didn't: image-to-video chaining and TTS.
"""
from __future__ import annotations

import uuid

from app import db
from app.pipelines import run_generation

BRIEF = {
    "subject": "a minimalist titanium water bottle",
    "audience": "urban commuters who care about design",
    "tone": "cinematic",
    "message": "Meet the bottle that keeps up with your day.",
    "cta": "Stay hydrated. Stay sharp.",
}


def main() -> None:
    db.init_db()
    job_id = uuid.uuid4().hex[:12]
    db.create_job(job_id, title=BRIEF["subject"], brief=BRIEF, parent_run_id=None)
    print(f"[..] Running full pipeline for job {job_id} (this takes a few minutes)…")

    run_generation(job_id, BRIEF)

    job = db.get_job(job_id)
    print("\n=== JOB RESULT ===")
    print(f"Status:   {job['status']}")
    print(f"Stage:    {job['stage']}")
    print(f"Verified: {bool(job['verified'])}")
    print(f"Cost:     ${job['cost_usd']}")
    print(f"Run ID:   {job['run_id']}")
    if job.get("error"):
        print(f"ERROR:    {job['error']}")
    print(f"\nAssets produced: {len(job['assets'])}")
    for a in job["assets"]:
        print(f"  [step {a['step_index']}] {a['modality']:<16} {a['model']}")
        print(f"     url: {a['url']}")
    mods = {(a["modality"] or "").split(".")[-1] for a in job["assets"]}
    print("\n=== VERDICT ===")
    for want in ("image", "video", "audio"):
        print(f"  {want:<6}: {'OK' if want in mods else 'MISSING'}")


if __name__ == "__main__":
    main()
