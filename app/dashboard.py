"""Streamlit dashboard for Ad Compliance Demo."""

import json
import sys
import tempfile
from datetime import datetime, UTC
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from shared.config import PATHS
from shared.constants import Decision, Region, Severity

_CREDENTIALS_PATH = Path(__file__).resolve().parent.parent / ".credentials.json"

_CREDENTIAL_KEYS = [
    "cred_backend",
    "aws_access_key_id",
    "aws_secret_access_key",
    "aws_region",
    "twelvelabs_api_key",
]


def _load_saved_credentials():
    """Load credentials from file into session state.

    Re-loads on every run so that values saved on the Settings page
    are available even when the Settings widgets are not rendered.
    Only fills keys that are not already present in session state,
    so active widget values are never overwritten.
    """
    if _CREDENTIALS_PATH.exists():
        try:
            saved = json.loads(_CREDENTIALS_PATH.read_text(encoding="utf-8"))
            for k in _CREDENTIAL_KEYS:
                if k in saved and k not in st.session_state:
                    st.session_state[k] = saved[k]
        except (json.JSONDecodeError, OSError):
            pass


def _save_credentials():
    """Persist current credentials to local file."""
    data = {}
    for k in _CREDENTIAL_KEYS:
        val = st.session_state.get(k)
        if val:
            data[k] = val
    try:
        _CREDENTIALS_PATH.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


st.set_page_config(
    page_title="Ad Compliance & Brand Safety",
    page_icon="🛡",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def save_report(report: dict):
    reports_dir = PATHS["reports"]
    reports_dir.mkdir(parents=True, exist_ok=True)
    video_name = Path(report.get("video_file", "video")).stem
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"{ts}_{video_name}.json"
    (reports_dir / filename).write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )


def load_reports():
    reports_dir = PATHS["reports"]
    if not reports_dir.exists():
        return []
    reports = []
    for rp in sorted(reports_dir.glob("*.json"), reverse=True):
        reports.append(json.loads(rp.read_text(encoding="utf-8")))
    return reports



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def decision_color(decision: str) -> str:
    return {"APPROVE": "green", "REVIEW": "orange", "BLOCK": "red"}.get(decision, "gray")


def decision_badge(decision: str) -> str:
    bg = {"APPROVE": "#28a745", "REVIEW": "#fd7e14", "BLOCK": "#dc3545"}.get(decision, "#6c757d")
    return f'<span style="background:{bg};color:white;padding:3px 10px;border-radius:4px;font-weight:bold;font-size:0.85em">{decision}</span>'


def _compliance_badge(decision: str) -> str:
    colors = {"PASS": "#28a745", "BLOCK": "#dc3545"}
    labels = {"PASS": "PASS", "BLOCK": "BLOCK"}
    bg = colors.get(decision, "#6c757d")
    label = labels.get(decision, decision)
    return f'<span style="background:{bg};color:white;padding:3px 10px;border-radius:4px;font-weight:bold;font-size:0.85em">{label}</span>'


def _product_badge(assessment: str) -> str:
    colors = {"CLEAR": "#28a745", "SUPPLEMENT_NEEDED": "#fd7e14", "OFF_BRIEF": "#dc3545"}
    labels = {"CLEAR": "CLEAR", "SUPPLEMENT_NEEDED": "SUPPLEMENT NEEDED", "OFF_BRIEF": "OFF-BRIEF"}
    bg = colors.get(assessment, "#6c757d")
    label = labels.get(assessment, assessment)
    return f'<span style="background:{bg};color:white;padding:3px 10px;border-radius:4px;font-weight:bold;font-size:0.85em">{label}</span>'


def render_violations(violations: list[dict]):
    if not violations:
        st.success("No policy violations detected.")
        return
    for v in violations:
        cat = v.get("category", "?")
        sev = v.get("severity", "?")
        sev_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(sev, "⚪")
        st.markdown(f"{sev_icon} **{cat}** — severity: `{sev}`")

        for i, ev in enumerate(v.get("violations", [])):
            ts_start = ev.get("timestamp_start", 0)
            ts_end = ev.get("timestamp_end", 0)
            ts = f"{ts_start:.1f}s — {ts_end:.1f}s"
            has_thumb = ev.get("thumbnail_b64")
            has_clip = ev.get("clip_b64")

            if has_thumb or has_clip:
                ecol1, ecol2 = st.columns([1, 2])
                with ecol1:
                    if has_thumb:
                        import base64 as _b64
                        thumb_bytes = _b64.b64decode(ev["thumbnail_b64"])
                        st.image(thumb_bytes, caption=f"@ {ts}", use_container_width=True)
                    if has_clip:
                        clip_bytes = _b64.b64decode(ev["clip_b64"])
                        st.video(clip_bytes, format="video/mp4")
                with ecol2:
                    st.markdown(f"**⏱ {ts}** &nbsp; `{ev.get('modality', '?')}`")
                    st.markdown(ev.get("description", ""))
                    if ev.get("evidence"):
                        evidence_text = ev["evidence"]
                        if ev.get("evidence_original"):
                            evidence_text += f"  \n*Original: {ev['evidence_original']}*"
                        st.caption(f"Evidence: {evidence_text}")
                    if ev.get("transcription"):
                        st.code(ev["transcription"], language=None)
            else:
                st.markdown(
                    f"&nbsp;&nbsp;&nbsp;&nbsp;⏱ [{ts}] ({ev.get('modality', '?')}) {ev.get('description', '')}"
                )
                if ev.get("evidence"):
                    evidence_text = ev["evidence"]
                    if ev.get("evidence_original"):
                        evidence_text += f"  \n*Original: {ev['evidence_original']}*"
                    st.caption(f"Evidence: {evidence_text}")
                if ev.get("transcription"):
                    st.code(ev["transcription"], language=None)


def _probe_video(src: Path) -> dict:
    """Return video stream info via ffprobe."""
    import subprocess, json as _json
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", str(src)],
        capture_output=True, text=True,
    )
    if probe.returncode != 0:
        return {}
    return _json.loads(probe.stdout)


def _prepare_video(src: Path) -> tuple[Path, str]:
    """Re-encode video to H.264/AAC MP4 for Bedrock Pegasus compatibility.

    Always re-encodes to guarantee a clean container with faststart,
    H.264 baseline/main profile, AAC audio, and proper metadata.
    Returns (output_path, info_string).
    """
    import subprocess

    info = _probe_video(src)
    streams = info.get("streams", [])
    vs = next((s for s in streams if s.get("codec_type") == "video"), {})
    fmt = info.get("format", {})
    src_info = (
        f"codec={vs.get('codec_name','?')}, "
        f"duration={fmt.get('duration','?')}s, "
        f"size={vs.get('width','?')}x{vs.get('height','?')}, "
        f"file_size={int(fmt.get('size', 0)) / 1024 / 1024:.1f}MB"
    )

    out = src.with_name(src.stem + "_h264.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(src),
            "-c:v", "libx264", "-profile:v", "main", "-level", "4.0",
            "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-ac", "2",
            "-movflags", "+faststart",
            "-f", "mp4",
            str(out),
        ],
        capture_output=True, check=True,
    )

    out_info = _probe_video(out)
    out_fmt = out_info.get("format", {})
    out_size_mb = int(out_fmt.get("size", 0)) / 1024 / 1024
    duration = float(out_fmt.get("duration", 0))

    if duration < 4.0:
        raise ValueError(
            f"Video too short ({duration:.1f}s). Pegasus requires at least 4 seconds of content."
        )
    if out_size_mb > 25:
        raise ValueError(
            f"Video too large after encoding ({out_size_mb:.1f}MB). "
            f"Base64 limit is 25MB. Use a shorter or lower-resolution video."
        )

    return out, src_info


def analyze_uploaded_video(
    video_bytes: bytes,
    filename: str,
    region: Region,
    backend: str,
    credentials: dict | None = None,
) -> dict:
    """Save uploaded video to temp file and run compliance analysis."""
    credentials = credentials or {}
    suffix = Path(filename).suffix or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(video_bytes)
        tmp_path = Path(tmp.name)

    transcoded_path = None
    try:
        if backend == "bedrock":
            transcoded_path, video_info = _prepare_video(tmp_path)

        if backend == "bedrock":
            from core.bedrock_client import get_bedrock_analyzer
            from core.bedrock_analyzer import analyze_video_bedrock

            analyzer = get_bedrock_analyzer(
                region=credentials.get("aws_region", "us-east-1"),
                aws_access_key_id=credentials.get("aws_access_key_id"),
                aws_secret_access_key=credentials.get("aws_secret_access_key"),
            )
            try:
                relevance, violations, description, raw_response = analyze_video_bedrock(analyzer, transcoded_path, region=region.value)
            except Exception as e:
                raise RuntimeError(f"{e}\n\n[Video info] {video_info}") from e
        else:
            from twelvelabs import TwelveLabs
            from core.indexer import get_or_create_index, upload_video
            from core.combined_analyzer import analyze_video_combined

            tl_key = credentials.get("twelvelabs_api_key", "")
            client = TwelveLabs(api_key=tl_key)
            index_id = get_or_create_index(api_key=tl_key)
            video_id = upload_video(index_id, tmp_path, api_key=tl_key)
            relevance, violations, description = analyze_video_combined(client, video_id)
            raw_response = None

        active_violations = [v for v in violations if v.violations]

        from core.decision import make_split_decision
        from shared.schemas import ComplianceReport

        split = make_split_decision(relevance, active_violations, region, description)

        report = ComplianceReport(
            video_id="upload-direct",
            video_file=filename,
            region=region,
            description=description,
            campaign_relevance=relevance,
            policy_violations=active_violations,
            decision=split["decision"],
            decision_reasoning=split["decision_reasoning"],
            compliance=split["compliance"],
            product=split["product"],
            disclosure=split["disclosure"],
            analyzed_at=datetime.now(UTC),
        )
        report_dict = report.model_dump(mode="json")
        if raw_response:
            report_dict["_raw_model_response"] = raw_response

        # Extract visual evidence for BLOCK violations
        if split["compliance"]["status"] == "BLOCK" and active_violations:
            from core.evidence_extractor import extract_violation_evidence

            video_for_evidence = transcoded_path if transcoded_path else tmp_path
            report_dict["policy_violations"] = extract_violation_evidence(
                video_for_evidence,
                report_dict["policy_violations"],
            )

        return report_dict

    finally:
        tmp_path.unlink(missing_ok=True)
        if transcoded_path:
            transcoded_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def page_upload():
    st.header("Upload & Analyze")
    st.caption("Upload a video file to run real-time compliance analysis")

    backend = st.session_state.get("cred_backend", "bedrock")

    ucol1, ucol2 = st.columns([1, 1])
    with ucol1:
        uploaded_file = st.file_uploader(
            "Video file",
            type=["mp4", "mov", "avi", "mkv"],
            help="Max 25MB for Bedrock base64 encoding",
        )
    with ucol2:
        region = st.selectbox(
            "Target Region",
            options=["global", "north_america", "western_europe", "east_asia"],
            format_func=lambda x: {
                "global": "🌍 Global",
                "north_america": "🇺🇸 North America (FTC/FDA)",
                "western_europe": "🇪🇺 Western Europe (ASA/EU)",
                "east_asia": "🇰🇷 East Asia (KR/JP/CN)",
            }.get(x, x),
        )
        backend_label = {"bedrock": "Amazon Bedrock", "twelvelabs": "TwelveLabs API"}.get(backend, backend)
        st.info(f"Backend: **{backend_label}** (change in sidebar)")

    if uploaded_file is not None:
        file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)

        if backend == "bedrock" and file_size_mb > 25:
            st.error("File exceeds 25MB limit for Bedrock base64 encoding. Use a smaller file or TwelveLabs backend.")
            return

        vcol1, vcol2 = st.columns([1, 1])
        with vcol1:
            st.video(uploaded_file)
        with vcol2:
            st.markdown(f"**File:** {uploaded_file.name}")
            st.markdown(f"**Size:** {file_size_mb:.1f} MB")
            st.markdown(f"**Region:** {region}")
            st.markdown(f"**Backend:** {backend}")

        # Check credentials before allowing analysis
        if backend == "bedrock":
            has_creds = bool(
                st.session_state.get("aws_access_key_id")
                and st.session_state.get("aws_secret_access_key")
            )
            if not has_creds:
                st.warning("Please enter AWS credentials in Settings to use Bedrock.")
            credentials = {
                "aws_access_key_id": st.session_state.get("aws_access_key_id", ""),
                "aws_secret_access_key": st.session_state.get("aws_secret_access_key", ""),
                "aws_region": st.session_state.get("aws_region", "us-east-1"),
            }
        else:
            has_creds = bool(st.session_state.get("twelvelabs_api_key"))
            if not has_creds:
                st.warning("Please enter TwelveLabs API Key in Settings.")
            credentials = {
                "twelvelabs_api_key": st.session_state.get("twelvelabs_api_key", ""),
            }

        if st.button(
            "🔍 Run Compliance Analysis",
            type="primary",
            use_container_width=True,
            disabled=not has_creds,
        ):
            with st.spinner("Analyzing video & extracting evidence... (10-60 seconds)"):
                try:
                    report = analyze_uploaded_video(
                        uploaded_file.getvalue(),
                        uploaded_file.name,
                        Region(region),
                        backend,
                        credentials=credentials,
                    )
                    st.session_state["upload_report"] = report
                    save_report(report)
                except Exception as e:
                    err = str(e)
                    if "ServiceUnavailableException" in err or "Too many connections" in err:
                        st.warning(
                            "⏳ **API rate limit reached** — The Bedrock service is temporarily "
                            "overloaded due to too many requests. Please wait 30-60 seconds "
                            "and try again."
                        )
                    elif "ThrottlingException" in err or "Rate exceeded" in err:
                        st.warning(
                            "⏳ **Request throttled** — You have exceeded the API request rate. "
                            "Please wait a moment and try again."
                        )
                    elif "ExpiredTokenException" in err or "InvalidIdentityToken" in err:
                        st.error(
                            "🔑 **Authentication error** — Your AWS credentials may be expired "
                            "or invalid. Please check your credentials in Settings."
                        )
                    elif "AccessDeniedException" in err or "UnauthorizedAccess" in err:
                        st.error(
                            "🔒 **Access denied** — Your AWS account does not have permission "
                            "to use this Bedrock model. Check your IAM permissions."
                        )
                    elif "DailyLimitExhausted" in err:
                        st.warning(
                            "⏳ **Daily quota exhausted** — The TwelveLabs daily API limit "
                            "(50 requests) has been reached. Try again tomorrow or switch "
                            "to Bedrock backend in Settings."
                        )
                    else:
                        st.error(f"Analysis failed: {e}")

    if "upload_report" in st.session_state:
        st.divider()
        r = st.session_state["upload_report"]
        decision = r.get("decision", "APPROVE")

        # --- Campaign Decision Banner ---
        _decision_colors = {"APPROVE": "#28a745", "REVIEW": "#fd7e14", "BLOCK": "#dc3545"}
        st.markdown(
            f'<div style="background:{_decision_colors.get(decision, "#6c757d")}; '
            f'color:white; padding:1rem 1.5rem; border-radius:8px; margin-bottom:1rem">'
            f'<h2 style="margin:0; color:white">Campaign Decision: {decision}</h2>'
            f'<p style="margin:0.3rem 0 0 0; opacity:0.9">{r.get("decision_reasoning", "")}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.markdown("**Description:**")
        st.info(r.get("description", "N/A"))

        # --- Three evaluation axes ---
        compliance = r.get("compliance", {})
        product = r.get("product", {})
        disclosure = r.get("disclosure", {})

        col1, col2, col3 = st.columns(3)

        # Axis 1: Compliance
        with col1:
            comp_status = compliance.get("status", "PASS")
            comp_color = {"PASS": "#28a745", "REVIEW": "#fd7e14", "BLOCK": "#dc3545"}.get(comp_status, "#6c757d")
            st.markdown(
                f'<div style="border-left:4px solid {comp_color};padding:0.5rem 1rem;background:#f8f9fa;border-radius:6px">'
                f'<strong>Compliance</strong><br>'
                f'<span style="color:{comp_color};font-weight:bold;font-size:1.1em">{comp_status}</span></div>',
                unsafe_allow_html=True,
            )
            st.caption(compliance.get("reasoning", ""))

            # Show content violation details
            all_violations = r.get("policy_violations", [])
            content_violations = [v for v in all_violations if v.get("category") != "disclosure"]
            if content_violations:
                st.markdown("**Violation Details**")
                render_violations(content_violations)

        # Axis 2: Product
        with col2:
            prod_status = product.get("status", "ON_BRIEF")
            prod_color = {"ON_BRIEF": "#28a745", "BORDERLINE": "#fd7e14", "NOT_VISIBLE": "#fd7e14", "OFF_BRIEF": "#dc3545"}.get(prod_status, "#6c757d")
            prod_label = {"ON_BRIEF": "ON-BRIEF", "BORDERLINE": "BORDERLINE", "NOT_VISIBLE": "NOT VISIBLE", "OFF_BRIEF": "OFF-BRIEF"}.get(prod_status, prod_status)
            st.markdown(
                f'<div style="border-left:4px solid {prod_color};padding:0.5rem 1rem;background:#f8f9fa;border-radius:6px">'
                f'<strong>Product</strong><br>'
                f'<span style="color:{prod_color};font-weight:bold;font-size:1.1em">{prod_label}</span></div>',
                unsafe_allow_html=True,
            )
            relevance = r.get("campaign_relevance", {})
            st.metric("Relevance Score", f"{relevance.get('score', 0):.2f}")
            st.caption(product.get("reasoning", ""))

        # Axis 3: Disclosure
        with col3:
            disc_status = disclosure.get("status", "PRESENT")
            disc_color = {"PRESENT": "#28a745", "MISSING": "#fd7e14"}.get(disc_status, "#6c757d")
            disc_label = {"PRESENT": "PRESENT", "MISSING": "MISSING"}.get(disc_status, disc_status)
            st.markdown(
                f'<div style="border-left:4px solid {disc_color};padding:0.5rem 1rem;background:#f8f9fa;border-radius:6px">'
                f'<strong>Disclosure</strong><br>'
                f'<span style="color:{disc_color};font-weight:bold;font-size:1.1em">{disc_label}</span></div>',
                unsafe_allow_html=True,
            )
            st.caption(disclosure.get("reasoning", ""))

            # Show disclosure violation details
            disclosure_violations = [v for v in all_violations if v.get("category") == "disclosure"]
            if disclosure_violations:
                render_violations(disclosure_violations)

        report_json = json.dumps(r, indent=2, default=str)
        st.download_button(
            "📥 Download Report (JSON)",
            data=report_json,
            file_name=f"compliance_{r.get('video_file', 'video')}.json",
            mime="application/json",
        )

        # Raw model response for debugging
        raw = r.get("_raw_model_response")
        if raw:
            with st.expander("🔍 Raw Model Response (Debug)"):
                st.json(raw)


def page_history():
    st.header("Analysis History")
    st.caption("Past compliance analysis results")

    reports = load_reports()
    if not reports:
        st.info("No analysis history yet. Upload a video on the Upload & Analyze page to get started.")
        return

    # Filters in main area
    fcol1, fcol2 = st.columns([1, 3])
    with fcol1:
        decisions = sorted(set(r.get("decision", "?") for r in reports))
        selected = st.multiselect("Filter by Decision", decisions, default=decisions)

    filtered = [r for r in reports if r.get("decision") in selected]

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total", len(filtered))
    col2.metric("APPROVE", sum(1 for r in filtered if r["decision"] == "APPROVE"))
    col3.metric("REVIEW", sum(1 for r in filtered if r["decision"] == "REVIEW"))
    col4.metric("BLOCK", sum(1 for r in filtered if r["decision"] == "BLOCK"))

    st.divider()

    for r in filtered:
        decision = r.get("decision", "?")
        color = decision_color(decision)
        video_file = r.get("video_file", "unknown")

        with st.expander(f":{color}[**{decision}**] — {video_file}"):
            st.write(r.get("description", "N/A"))

            compliance = r.get("compliance", {})
            product = r.get("product", {})
            disclosure = r.get("disclosure", {})

            # New format (3 axes)
            if compliance or product or disclosure:
                bc1, bc2, bc3 = st.columns(3)
                with bc1:
                    cs = compliance.get("status", "PASS")
                    st.markdown(f"**Compliance:** `{cs}`")
                    st.caption(compliance.get("reasoning", ""))
                with bc2:
                    ps = product.get("status", "ON_BRIEF")
                    st.markdown(f"**Product:** `{ps}`")
                    st.caption(product.get("reasoning", ""))
                with bc3:
                    ds = disclosure.get("status", "PRESENT")
                    st.markdown(f"**Disclosure:** `{ds}`")
                    st.caption(disclosure.get("reasoning", ""))
            else:
                # Legacy format fallback
                st.caption(r.get("decision_reasoning", "N/A"))
                relevance = r.get("campaign_relevance", {})
                st.write(f"Relevance: **{relevance.get('score', 0):.2f}** ({relevance.get('label', 'N/A')})")

            all_v = r.get("policy_violations", [])
            content_v = [v for v in all_v if v.get("category") != "disclosure"]
            if content_v:
                render_violations(content_v)


def page_settings():
    st.header("Settings")
    st.caption("Configure default API backend and credentials")

    st.subheader("Backend")
    cred_backend = st.radio(
        "Select default backend",
        options=["bedrock", "twelvelabs"],
        format_func=lambda x: {"bedrock": "Amazon Bedrock (Pegasus 1.2)", "twelvelabs": "TwelveLabs API (Direct)"}.get(x, x),
        key="cred_backend",
        horizontal=True,
    )

    st.divider()

    if cred_backend == "bedrock":
        st.subheader("Amazon Bedrock Credentials")
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("AWS Access Key ID", type="password", key="aws_access_key_id")
        with col2:
            st.text_input("AWS Secret Access Key", type="password", key="aws_secret_access_key")
        st.selectbox(
            "AWS Region",
            options=["us-east-1"],
            help="Pegasus 1.2 is currently available in us-east-1 only",
            index=0,
            key="aws_region",
        )
        if st.session_state.get("aws_access_key_id") and st.session_state.get("aws_secret_access_key"):
            st.success("Bedrock credentials configured", icon="✅")
        else:
            st.info("Enter AWS credentials to use Bedrock", icon="ℹ️")
    else:
        st.subheader("TwelveLabs API Credentials")
        st.text_input("TwelveLabs API Key", type="password", key="twelvelabs_api_key")
        if st.session_state.get("twelvelabs_api_key"):
            key_preview = st.session_state["twelvelabs_api_key"][:8] + "..."
            st.success(f"API key set ({key_preview})", icon="✅")
        else:
            st.info("Enter TwelveLabs API key", icon="ℹ️")

    st.divider()

    bcol1, bcol2 = st.columns([1, 1])
    with bcol1:
        if st.button("💾 Save Settings", type="primary", use_container_width=True):
            _save_credentials()
            st.success("Settings saved!")
    with bcol2:
        if st.button("🗑️ Clear All Credentials", use_container_width=True):
            for k in _CREDENTIAL_KEYS:
                st.session_state.pop(k, None)
            if _CREDENTIALS_PATH.exists():
                _CREDENTIALS_PATH.unlink()
            st.rerun()




# ---------------------------------------------------------------------------
# Main — Sidebar navigation
# ---------------------------------------------------------------------------

def main():
    _load_saved_credentials()

    if "page" not in st.session_state:
        st.session_state["page"] = "upload"

    # Global + sidebar CSS
    st.markdown(
        """
        <style>
        /* Sidebar width */
        section[data-testid="stSidebar"] { min-width: 280px; }
        section[data-testid="stSidebar"] > div { padding-top: 1.5rem; }

        /* Nav button overrides */
        section[data-testid="stSidebar"] button[kind="secondary"] {
            font-size: 1.25rem !important;
            padding: 0.85rem 1.1rem !important;
            border-radius: 12px !important;
            border: 2px solid transparent !important;
            text-align: left !important;
            justify-content: flex-start !important;
            transition: all 0.15s ease !important;
        }
        section[data-testid="stSidebar"] button[kind="secondary"]:hover {
            border-color: rgba(255,75,75,0.4) !important;
            background: rgba(255,75,75,0.08) !important;
        }
        /* Active nav button (primary) */
        section[data-testid="stSidebar"] button[kind="primary"] {
            font-size: 1.25rem !important;
            padding: 0.85rem 1.1rem !important;
            border-radius: 12px !important;
            text-align: left !important;
            justify-content: flex-start !important;
            font-weight: 700 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Title
    st.sidebar.markdown("## 🛡️ Ad Compliance")
    st.sidebar.caption("Brand Safety for Social Video Ads")
    st.sidebar.markdown("")

    # Nav buttons — active page uses primary style
    PAGES = [
        ("upload",     "🎬  Upload & Analyze"),
        ("history",    "📋  Analysis History"),

        ("settings",   "⚙️  Settings"),
    ]
    for key, label in PAGES:
        is_active = st.session_state["page"] == key
        btn_type = "primary" if is_active else "secondary"
        if st.sidebar.button(label, key=f"nav_{key}", type=btn_type, use_container_width=True):
            st.session_state["page"] = key
            st.rerun()

    st.sidebar.markdown("")
    st.sidebar.markdown("---")

    # Current backend summary
    backend = st.session_state.get("cred_backend", "bedrock")
    backend_label = {"bedrock": "Amazon Bedrock", "twelvelabs": "TwelveLabs API"}.get(backend, backend)
    has_creds = (
        bool(st.session_state.get("aws_access_key_id") and st.session_state.get("aws_secret_access_key"))
        if backend == "bedrock"
        else bool(st.session_state.get("twelvelabs_api_key"))
    )
    status_icon = "✅" if has_creds else "⚠️"
    st.sidebar.markdown(f"{status_icon} **{backend_label}**")
    if not has_creds:
        st.sidebar.caption("Credentials not set — go to Settings")

    st.sidebar.markdown("---")
    st.sidebar.caption("Built with TwelveLabs Pegasus 1.2\nvia Amazon Bedrock")

    page = st.session_state["page"]

    if page == "upload":
        page_upload()
    elif page == "history":
        page_history()
    elif page == "settings":
        page_settings()


if __name__ == "__main__":
    main()
