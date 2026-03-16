"""Common configuration loaded from environment."""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

TWELVELABS_API_KEY = os.getenv("TWELVELABS_API_KEY", "")
INDEX_NAME = "ad-compliance-beauty-v2"

# Backend: "bedrock" (default) or "twelvelabs"
ANALYSIS_BACKEND = os.getenv("ANALYSIS_BACKEND", "bedrock")
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")

PATHS = {
    "project_root": PROJECT_ROOT,
    "shared": PROJECT_ROOT / "shared",
    "reports": PROJECT_ROOT / "output" / "reports",
}
