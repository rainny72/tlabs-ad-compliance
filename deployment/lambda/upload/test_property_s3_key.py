"""Property-based test for S3 key generation.

Feature: amplify-serverless-migration, Property 3: Presigned URL 생성 및 S3 키 형식

Validates: Requirements 3.2, 3.3
"""

import os
import re
import sys
import uuid

# Ensure handler module is importable from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypothesis import given, settings
from hypothesis import strategies as st

from handler import ALLOWED_EXTENSIONS, generate_s3_key

# Strategy: valid UUID strings
uuid_strategy = st.uuids().map(str)

# Strategy: alphanumeric filenames with allowed extensions
alphanumeric_base = st.text(
    alphabet=st.sampled_from(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    ),
    min_size=1,
    max_size=50,
)
extension_strategy = st.sampled_from(sorted(ALLOWED_EXTENSIONS))
filename_strategy = st.builds(lambda base, ext: f"{base}.{ext}", alphanumeric_base, extension_strategy)


@given(user_id=uuid_strategy, filename=filename_strategy)
@settings(max_examples=100)
def test_s3_key_format_property(user_id: str, filename: str):
    """Property 3: For any valid user_id (UUID) and filename (alphanumeric + extension),
    generate_s3_key must produce a key matching uploads/{user_id}/{digits}_{filename}.

    - The key starts with "uploads/"
    - The key contains the user_id
    - The key ends with the original filename
    - The key matches format: uploads/{user_id}/{digits}_{filename}
    - The timestamp portion is a valid integer (digits only)

    **Validates: Requirements 3.2, 3.3**
    """
    key = generate_s3_key(user_id, filename)

    # Key starts with "uploads/"
    assert key.startswith("uploads/"), f"Key must start with 'uploads/', got: {key}"

    # Key contains the user_id
    assert user_id in key, f"Key must contain user_id '{user_id}', got: {key}"

    # Key ends with the original filename
    assert key.endswith(f"_{filename}"), f"Key must end with '_{filename}', got: {key}"

    # Key matches exact format: uploads/{user_id}/{digits}_{filename}
    pattern = re.compile(r"^uploads/" + re.escape(user_id) + r"/(\d+)_" + re.escape(filename) + r"$")
    match = pattern.match(key)
    assert match is not None, f"Key must match 'uploads/{{user_id}}/{{digits}}_{{filename}}', got: {key}"

    # Timestamp portion is a valid positive integer
    timestamp_str = match.group(1)
    timestamp = int(timestamp_str)
    assert timestamp > 0, f"Timestamp must be positive, got: {timestamp}"
