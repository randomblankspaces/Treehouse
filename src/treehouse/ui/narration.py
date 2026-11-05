"""Deterministic plain-language narration text for a run, spoken by the narrator.

The same text is stored beside the audio (with its sha256) so the UI can verify that a pre-rendered MP3
matches the summary it shows before playing it. Built from the public snapshot only — no hidden reasoning,
no grading key — so it is safe to publish and reproducible offline.
"""
from __future__ import annotations

from treehouse.canon import sha256_bytes


def _pct(value):
    return "unavailable" if value is None else f"{round(value * 100)} percent"


def narration_text(snapshot: dict) -> str:
    """One short spoken summary of the run: ask, scale choice, findings, earned confidence, limits."""
    goal = snapshot.get("input", {}).get("goal") or "the task"
    decisions = snapshot.get("decisions") or []
    markers = snapshot.get("markers") or []
    scale = next((d for d in decisions if d.get("tool") == "build_index"), None)
    present = [m for m in markers if m.get("status") in ("present", "intact")]
    cannot = [m for m in markers if m.get("status") == "cannot_assess"]
    absent = [m for m in markers if m.get("status") == "absent"]
    confidences = [m["confidence"] for m in present if m.get("confidence") is not None]
    avg = sum(confidences) / len(confidences) if confidences else None
    earned = sum(1 for m in present if (m.get("confidence_provenance") or {}).get("label") == "earned")

    parts = [f"Here is what the agent did. It was asked to {goal.rstrip('.').lower()}."]
    if scale:
        parts.append(f"To see the area it chose {scale.get('tool')}. {scale.get('rationale', '').rstrip('.')}.")
    else:
        parts.append("No foundation-model or cell-size decision was recorded.")
    found = f"It marked {len(present)} site{'' if len(present) == 1 else 's'} present"
    if cannot:
        found += f", {len(cannot)} it could not assess"
    if absent:
        found += f", and judged {len(absent)} absent"
    parts.append(found + ". These are the agent's own reports, not confirmed ground truth.")
    if avg is not None:
        parts.append(f"Average stated confidence on present sites was about {_pct(avg)}.")
    if present:
        if earned == len(present):
            parts.append("Every present site rested on a passed independent check, so that confidence was earned.")
        elif earned == 0:
            parts.append("No present site rested on a passed independent check, so that confidence is not yet earned.")
        else:
            parts.append(f"{earned} of {len(present)} present sites rested on a passed independent check; the rest did not.")
    limits = snapshot.get("provenance", {}).get("limitations") or []
    if limits:
        parts.append("It could not check: " + "; ".join(limit.rstrip(".") for limit in limits[:3]) + ".")
    return " ".join(parts)


def text_sha256(text: str) -> str:
    """sha256 of the UTF-8 narration text, without the ``sha256:`` prefix (matches the UI's hashing)."""
    return sha256_bytes(text.encode("utf-8")).removeprefix("sha256:")
