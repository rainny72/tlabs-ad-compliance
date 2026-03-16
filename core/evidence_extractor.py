"""Extract thumbnail frames and video clips for violation evidence using ffmpeg."""

from __future__ import annotations

import base64
import subprocess
import tempfile
from pathlib import Path


def extract_thumbnail(
    video_path: Path,
    timestamp: float,
    width: int = 480,
) -> str | None:
    """Extract a single frame at the given timestamp. Returns base64-encoded JPEG or None."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        out_path = Path(tmp.name)

    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", str(max(0, timestamp)),
                "-i", str(video_path),
                "-frames:v", "1",
                "-vf", f"scale={width}:-1",
                "-q:v", "2",
                str(out_path),
            ],
            capture_output=True,
            check=True,
        )
        if out_path.exists() and out_path.stat().st_size > 0:
            return base64.b64encode(out_path.read_bytes()).decode("utf-8")
        return None
    except subprocess.CalledProcessError:
        return None
    finally:
        out_path.unlink(missing_ok=True)


def extract_clip(
    video_path: Path,
    start: float,
    end: float,
    padding: float = 1.0,
) -> bytes | None:
    """Extract a short video clip. Returns MP4 bytes or None."""
    actual_start = max(0, start - padding)
    duration = (end - start) + 2 * padding

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        out_path = Path(tmp.name)

    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", str(actual_start),
                "-i", str(video_path),
                "-t", str(duration),
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                "-c:a", "aac", "-b:a", "96k",
                "-movflags", "+faststart",
                "-f", "mp4",
                str(out_path),
            ],
            capture_output=True,
            check=True,
        )
        if out_path.exists() and out_path.stat().st_size > 0:
            return out_path.read_bytes()
        return None
    except subprocess.CalledProcessError:
        return None
    finally:
        out_path.unlink(missing_ok=True)


def extract_violation_evidence(
    video_path: Path,
    violations: list[dict],
) -> list[dict]:
    """For each violation with timestamps, extract thumbnail + clip.

    Returns a list matching the input violations, each augmented with:
      - evidence_items[].thumbnail_b64  (JPEG base64)
      - evidence_items[].clip_b64       (MP4 base64)
    """
    results = []
    for v in violations:
        items = []
        for ev in v.get("violations", []):
            ts_start = ev.get("timestamp_start", 0)
            ts_end = ev.get("timestamp_end", 0)
            if ts_end <= ts_start:
                ts_end = ts_start + 2.0

            mid = (ts_start + ts_end) / 2.0
            thumb = extract_thumbnail(video_path, mid)
            clip_bytes = extract_clip(video_path, ts_start, ts_end)
            clip_b64 = base64.b64encode(clip_bytes).decode("utf-8") if clip_bytes else None

            items.append({
                **ev,
                "thumbnail_b64": thumb,
                "clip_b64": clip_b64,
            })

        results.append({**v, "violations": items})
    return results
