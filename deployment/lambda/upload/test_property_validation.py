"""Property-based test for upload input validation.

Feature: amplify-serverless-migration, Property 4: 업로드 입력 검증

Validates: Requirements 3.5, 3.6
"""

import os
import sys

# Ensure handler module is importable from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from handler import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE,
    ValidationError,
    validate_file_size,
    validate_filename,
)

# --- Strategies ---

# Allowed extensions
allowed_ext_strategy = st.sampled_from(sorted(ALLOWED_EXTENSIONS))

# Disallowed extensions (common file types that are NOT in ALLOWED_EXTENSIONS)
disallowed_ext_strategy = st.sampled_from([
    "jpg", "png", "gif", "pdf", "txt", "exe", "zip", "html", "doc", "wav",
    "flv", "wmv", "webm", "3gp", "ts", "m4v", "bmp", "svg", "csv", "xml",
])

# Base filename: alphanumeric, 1-50 chars
base_name_strategy = st.text(
    alphabet=st.sampled_from(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    ),
    min_size=1,
    max_size=50,
)

# Valid filename (allowed extension)
valid_filename_strategy = st.builds(
    lambda base, ext: f"{base}.{ext}", base_name_strategy, allowed_ext_strategy
)

# Invalid filename (disallowed extension)
invalid_filename_strategy = st.builds(
    lambda base, ext: f"{base}.{ext}", base_name_strategy, disallowed_ext_strategy
)

# Valid file size: 1 byte to 25MB inclusive
valid_size_strategy = st.integers(min_value=1, max_value=MAX_FILE_SIZE)

# Oversized file: just above 25MB to 100MB
oversized_strategy = st.integers(min_value=MAX_FILE_SIZE + 1, max_value=100 * 1024 * 1024)

# Non-positive file size: 0 and negative
non_positive_size_strategy = st.integers(min_value=-100 * 1024 * 1024, max_value=0)


@given(filename=valid_filename_strategy, file_size=valid_size_strategy)
@settings(max_examples=100)
def test_valid_upload_accepted(filename: str, file_size: int):
    """Property 4: For any filename with allowed extension (mp4/mov/avi/mkv)
    and file size between 1 byte and 25MB, both validations must pass
    without raising ValidationError.

    **Validates: Requirements 3.5, 3.6**
    """
    # Should not raise
    validate_filename(filename)
    validate_file_size(file_size)


@given(filename=invalid_filename_strategy)
@settings(max_examples=100)
def test_disallowed_extension_rejected(filename: str):
    """Property 4: For any filename with a disallowed extension,
    validate_filename must raise ValidationError.

    **Validates: Requirements 3.5**
    """
    with pytest.raises(ValidationError):
        validate_filename(filename)


@given(file_size=oversized_strategy)
@settings(max_examples=100)
def test_oversized_file_rejected(file_size: int):
    """Property 4: For any file size exceeding 25MB (up to 100MB),
    validate_file_size must raise ValidationError.

    **Validates: Requirements 3.6**
    """
    with pytest.raises(ValidationError):
        validate_file_size(file_size)


@given(file_size=non_positive_size_strategy)
@settings(max_examples=100)
def test_non_positive_size_rejected(file_size: int):
    """Property 4: For any file size <= 0,
    validate_file_size must raise ValidationError.

    **Validates: Requirements 3.6**
    """
    with pytest.raises(ValidationError):
        validate_file_size(file_size)
