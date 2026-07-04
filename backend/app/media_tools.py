"""Helpers for embedding/extracting Genblaze provenance manifests in media files.

Genblaze ships one handler per media format under genblaze_core.media. We pick a
handler by file extension and expose embed()/extract()/verify() that degrade
gracefully if a particular handler isn't available in the installed version.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from genblaze_core import parse_manifest

_HANDLERS: dict[str, Any] = {}


def _load_handlers() -> dict[str, Any]:
    if _HANDLERS:
        return _HANDLERS
    import importlib

    media = importlib.import_module("genblaze_core.media")
    candidates = {
        ".mp4": "Mp4Handler",
        ".png": "PngHandler",
        ".jpg": "JpegHandler",
        ".jpeg": "JpegHandler",
        ".mp3": "Mp3Handler",
        ".wav": "WavHandler",
        ".webp": "WebpHandler",
        ".flac": "FlacHandler",
        ".aac": "AacHandler",
    }
    for ext, cls_name in candidates.items():
        cls = getattr(media, cls_name, None)
        if cls is not None:
            try:
                _HANDLERS[ext] = cls()
            except Exception:
                pass
    return _HANDLERS


def handler_for(filename: str) -> Any | None:
    ext = Path(filename).suffix.lower()
    return _load_handlers().get(ext)


def manifest_from_json(manifest_json: str) -> Any:
    return parse_manifest(manifest_json)


def embed_manifest(path: Path, manifest: Any, output: Path) -> Path:
    handler = handler_for(path.name)
    if handler is None:
        raise ValueError(f"No manifest handler for {path.suffix} files")
    return handler.embed(path, manifest, output)


def extract_and_verify(path: Path) -> dict[str, Any]:
    handler = handler_for(path.name)
    if handler is None:
        return {"found": False, "verified": False, "reason": f"Unsupported file type: {path.suffix}"}
    try:
        manifest = handler.extract(path)
    except Exception as exc:
        return {"found": False, "verified": False, "reason": f"No embedded manifest ({exc})"}
    try:
        verified = bool(manifest.verify())
    except Exception:
        verified = False
    try:
        manifest_dict = manifest.model_dump(mode="json")
    except Exception:
        manifest_dict = {}
    return {
        "found": True,
        "verified": verified,
        "canonical_hash": getattr(manifest, "canonical_hash", None),
        "manifest": manifest_dict,
    }
