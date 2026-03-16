"""TwelveLabs direct REST API client (v1.3) for video analysis."""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from urllib import request as urllib_request
from urllib.error import HTTPError

logger = logging.getLogger(__name__)

TL_BASE = "https://api.twelvelabs.io/v1.3"
INDEX_NAME = "ad-compliance-analysis"
POLL_INTERVAL = 5
MAX_POLL = 120


def _headers(api_key: str) -> dict:
    return {"x-api-key": api_key, "Content-Type": "application/json"}


def _json_request(url: str, api_key: str, data: dict | None = None, method: str = "GET") -> dict:
    body = json.dumps(data).encode() if data else None
    req = urllib_request.Request(url, data=body, headers=_headers(api_key), method=method)
    try:
        with urllib_request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        logger.error("TwelveLabs API error %s %s: %s", e.code, url, err_body)
        raise RuntimeError(f"TwelveLabs API {e.code}: {err_body}") from e


def _get_or_create_index(api_key: str) -> str:
    # Search all pages for existing index
    page = 1
    while True:
        result = _json_request(f"{TL_BASE}/indexes?page={page}&page_limit=50", api_key)
        for idx in result.get("data", []):
            if idx.get("index_name") == INDEX_NAME:
                logger.info("Found existing index: %s", idx["_id"])
                return idx["_id"]
        page_info = result.get("page_info", {})
        if page >= page_info.get("total_page", 1):
            break
        page += 1
    # Create new index, handle 409 (already exists) gracefully
    data = {
        "index_name": INDEX_NAME,
        "models": [{"model_name": "pegasus1.2", "model_options": ["visual", "audio"]}],
    }
    try:
        result = _json_request(f"{TL_BASE}/indexes", api_key, data, "POST")
        logger.info("Created index: %s", result["_id"])
        return result["_id"]
    except RuntimeError as e:
        if "409" in str(e) or "already_exists" in str(e):
            logger.warning("Index creation 409, re-fetching: %s", e)
            result = _json_request(f"{TL_BASE}/indexes?page=1&page_limit=50", api_key)
            for idx in result.get("data", []):
                if idx.get("index_name") == INDEX_NAME:
                    return idx["_id"]
        raise


def _upload_asset(api_key: str, video_path: Path) -> str:
    """Upload video via POST /assets (multipart/form-data). Returns asset_id."""
    import mimetypes

    boundary = uuid.uuid4().hex
    ct = mimetypes.guess_type(str(video_path))[0] or "video/mp4"
    video_bytes = video_path.read_bytes()

    # Build multipart body
    parts = []
    # method field
    parts.append(
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"method\"\r\n\r\n"
        f"direct"
    )
    # file field
    file_header = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"file\"; filename=\"{video_path.name}\"\r\n"
        f"Content-Type: {ct}\r\n\r\n"
    )

    body = b""
    for p in parts:
        body += p.encode() + b"\r\n"
    body += file_header.encode() + video_bytes + f"\r\n--{boundary}--\r\n".encode()

    headers = {
        "x-api-key": api_key,
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    req = urllib_request.Request(f"{TL_BASE}/assets", data=body, headers=headers, method="POST")
    try:
        with urllib_request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read())
    except HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        logger.error("Asset upload error %s: %s", e.code, err_body)
        raise RuntimeError(f"TwelveLabs upload {e.code}: {err_body}") from e

    asset_id = result.get("_id")
    status = result.get("status", "")
    logger.info("Asset created: %s (status=%s)", asset_id, status)

    # Wait for asset to be ready
    if status != "ready":
        for i in range(60):
            r = _json_request(f"{TL_BASE}/assets/{asset_id}", api_key)
            st = r.get("status", "")
            logger.info("[%d] Asset %s status: %s", i + 1, asset_id, st)
            if st == "ready":
                break
            if st == "failed":
                raise RuntimeError(f"Asset processing failed: {r}")
            time.sleep(3)

    return asset_id


def _index_asset(api_key: str, index_id: str, asset_id: str) -> str:
    """Index an asset via POST /indexes/{id}/indexed-assets. Returns indexed_asset_id."""
    data = {"asset_id": asset_id}
    result = _json_request(f"{TL_BASE}/indexes/{index_id}/indexed-assets", api_key, data, "POST")
    ia_id = result.get("_id")
    logger.info("Indexing started: indexed_asset=%s", ia_id)

    # Poll until ready
    for i in range(MAX_POLL):
        r = _json_request(f"{TL_BASE}/indexes/{index_id}/indexed-assets/{ia_id}", api_key)
        st = r.get("status", "")
        logger.info("[%d/%d] Indexed asset %s status: %s", i + 1, MAX_POLL, ia_id, st)
        if st == "ready":
            return ia_id
        if st == "failed":
            raise RuntimeError(f"Indexing failed: {r}")
        time.sleep(POLL_INTERVAL)

    raise TimeoutError("TwelveLabs indexing timed out")


def _generate_analysis(api_key: str, video_id: str, prompt: str, json_schema: dict) -> dict:
    """Call POST /v1.3/analyze with structured JSON output."""
    data = {
        "video_id": video_id,
        "prompt": prompt,
        "temperature": 0.1,
        "stream": False,
        "response_format": {"type": "json_schema", "json_schema": json_schema},
        "max_tokens": 4096,
    }
    result = _json_request(f"{TL_BASE}/analyze", api_key, data, "POST")
    text = result.get("data", "")
    return json.loads(text) if isinstance(text, str) and text else (text if isinstance(text, dict) else {})


def analyze_video_twelvelabs(
    api_key: str, video_path: Path, region: str = "global"
) -> tuple:
    """Full TwelveLabs direct API pipeline. Returns same signature as analyze_video_bedrock."""
    from prompts.prompt_templates import COMBINED_JSON_SCHEMA, get_regional_prompt
    from core.bedrock_analyzer import _parse_modality, _parse_severity, CATEGORY_MAP
    from shared.constants import RelevanceLabel, RELEVANCE_THRESHOLD
    from shared.schemas import CampaignRelevanceResult, PolicyViolationResult, ViolationEvidence

    prompt = get_regional_prompt(region)
    index_id = _get_or_create_index(api_key)
    asset_id = _upload_asset(api_key, video_path)
    ia_id = _index_asset(api_key, index_id, asset_id)
    data = _generate_analysis(api_key, ia_id, prompt, COMBINED_JSON_SCHEMA)

    logger.info("TwelveLabs raw:\n%s", json.dumps(data, indent=2, ensure_ascii=False))

    # Parse relevance
    rel = data.get("relevance", {})
    score = rel.get("relevance_score", 0.0)
    is_on_brief = rel.get("is_on_brief", False)
    reasoning = rel.get("reasoning", "Analysis unavailable")
    if score >= RELEVANCE_THRESHOLD and is_on_brief:
        label = RelevanceLabel.ON_BRIEF
    elif score < 0.3:
        label = RelevanceLabel.OFF_BRIEF
    else:
        label = RelevanceLabel.BORDERLINE

    relevance = CampaignRelevanceResult(
        score=score, label=label,
        product_visible=rel.get("product_visible"),
        reasoning=reasoning, search_evidence=[],
    )
    description = data.get("description", "Description unavailable.")

    violations = []
    policy_data = data.get("policy_violations", {})
    for cat_key, cat_enum in CATEGORY_MAP.items():
        cat = policy_data.get(cat_key, {})
        severity = _parse_severity(cat.get("severity", "none"))
        items = []
        if cat.get("has_violation", False):
            for v in cat.get("violations", []):
                items.append(ViolationEvidence(
                    description=v.get("description", ""),
                    timestamp_start=float(v.get("timestamp_start", 0)),
                    timestamp_end=float(v.get("timestamp_end", 0)),
                    modality=_parse_modality(v.get("modality", "visual")),
                    evidence=v.get("evidence", ""),
                    evidence_original=v.get("evidence_original"),
                ))
        violations.append(PolicyViolationResult(
            category=cat_enum, severity=severity, violations=items,
        ))

    return relevance, violations, description, data
