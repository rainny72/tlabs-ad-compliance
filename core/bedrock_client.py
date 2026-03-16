"""Amazon Bedrock client for TwelveLabs Pegasus 1.2 model."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import boto3

# Foundation model ID (리전 무관)
PEGASUS_MODEL_ID = "twelvelabs.pegasus-1-2-v1:0"
DEFAULT_REGION = "ap-northeast-2"


class BedrockAnalyzer:
    """Analyze videos using TwelveLabs Pegasus on Amazon Bedrock."""

    def __init__(
        self,
        region: str = DEFAULT_REGION,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
    ):
        kwargs: dict = {"region_name": region}
        if aws_access_key_id and aws_secret_access_key:
            kwargs["aws_access_key_id"] = aws_access_key_id
            kwargs["aws_secret_access_key"] = aws_secret_access_key
        self._client = boto3.client("bedrock-runtime", **kwargs)
        self._region = region

    def analyze(
        self,
        video_path: Path,
        prompt: str,
        response_format: dict | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        s3_uri: str | None = None,
        bucket_owner: str | None = None,
    ) -> str:
        """Analyze a video with a prompt. Returns the model's text response.

        If s3_uri is provided, the video is read directly from S3 by Bedrock
        (supports up to 1 hour / 2 GB). Otherwise falls back to base64 encoding
        (max 25 MB).
        """
        if s3_uri:
            media_source: dict = {"s3Location": {"uri": s3_uri}}
            if bucket_owner:
                media_source["s3Location"]["bucketOwner"] = bucket_owner
        else:
            video_b64 = base64.b64encode(video_path.read_bytes()).decode("utf-8")
            media_source = {"base64String": video_b64}

        body: dict = {
            "inputPrompt": prompt,
            "mediaSource": media_source,
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }

        if response_format:
            body["responseFormat"] = response_format

        response = self._client.invoke_model(
            modelId=PEGASUS_MODEL_ID,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

        result = json.loads(response["body"].read())
        if result.get("finishReason") == "length":
            import logging
            logging.warning(
                "Pegasus response truncated (finishReason=length). "
                "Consider increasing maxOutputTokens or simplifying the prompt."
            )
        return result.get("message", "")

    def analyze_json(
        self,
        video_path: Path,
        prompt: str,
        json_schema: dict,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        s3_uri: str | None = None,
        bucket_owner: str | None = None,
    ) -> dict:
        """Analyze a video and return structured JSON output."""
        response_format = {
            "jsonSchema": json_schema,
        }
        text = self.analyze(
            video_path=video_path,
            prompt=prompt,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
            s3_uri=s3_uri,
            bucket_owner=bucket_owner,
        )
        return json.loads(text) if text else {}


def get_bedrock_analyzer(
    region: str = DEFAULT_REGION,
    aws_access_key_id: str | None = None,
    aws_secret_access_key: str | None = None,
) -> BedrockAnalyzer:
    return BedrockAnalyzer(
        region=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )
