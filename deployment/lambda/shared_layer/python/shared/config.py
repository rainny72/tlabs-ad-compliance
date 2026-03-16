"""Common configuration loaded from environment.

Lambda Layer version: uses environment variables directly (no dotenv, no local paths).
"""

import os

# Backend: "bedrock" (default) or "twelvelabs"
ANALYSIS_BACKEND = os.getenv("ANALYSIS_BACKEND", "bedrock")
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")
