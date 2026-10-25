"""Tests for keyed HMAC-SHA256 identifier hashing in app/detect.py."""
import hashlib
import re
from app.detect import hash_value, get_salt


def test_hmac_deterministic():
    """HMAC-SHA256 is deterministic for identical value and key."""
    key = "secret_test_key_2026"
    val = "9876543210"
    h1 = hash_value(val, salt=key)
    h2 = hash_value(val, salt=key)
    assert h1 == h2
    assert len(h1) == 64
    assert bool(re.match(r"^[0-9a-f]{64}$", h1))


def test_hmac_differs_from_sha256_concatenation():
    """HMAC-SHA256 differs from simple SHA-256 concatenation hashlib.sha256((salt+value).encode())."""
    key = "secret_test_key_2026"
    val = "rajesh.kumar@example.com"
    normalized = re.sub(r"\s+", "", val).lower()

    hmac_result = hash_value(val, salt=key)
    concat_sha256 = hashlib.sha256((key + normalized).encode("utf-8")).hexdigest()

    assert hmac_result != concat_sha256


def test_hmac_changes_when_key_changes():
    """HMAC-SHA256 changes when the key changes."""
    val = "ABCDE1234F"
    h_key1 = hash_value(val, salt="key_alpha")
    h_key2 = hash_value(val, salt="key_beta")
    assert h_key1 != h_key2


def test_hmac_equal_for_different_formats_of_same_value():
    """HMAC-SHA256 normalizes whitespace and casing before hashing."""
    key = "fixed_key_123"
    h1 = hash_value("98765 43210", salt=key)
    h2 = hash_value("  9876543210 \n\t", salt=key)
    h3 = hash_value("9876543210", salt=key)
    assert h1 == h2 == h3

    h_upper = hash_value("Priya Sharma", salt=key)
    h_lower = hash_value("priya sharma", salt=key)
    h_spaces = hash_value("  PRIYA   SHARMA  ", salt=key)
    assert h_upper == h_lower == h_spaces
