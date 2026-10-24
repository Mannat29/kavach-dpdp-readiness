"""Tests for the detect module."""
import pytest
from app.detect import (
    verhoeff_validate,
    normalize_phone,
    mask_value,
    hash_value,
    detect_aadhaar,
    detect_phone,
    detect_email,
    detect_pan,
    detect_gstin,
    detect_ifsc,
    detect_upi,
    detect_bank_account,
    detect_health_term,
    detect_name,
)


# ---------------------------------------------------------------------------
# Verhoeff checksum
# ---------------------------------------------------------------------------
class TestVerhoeff:
    def test_valid_aadhaar(self):
        """Known valid Verhoeff number."""
        # Generate a valid one using the algorithm
        from scripts.seed import make_aadhaar
        import random
        rng = random.Random(42)
        aadhaar = make_aadhaar(rng)
        assert verhoeff_validate(aadhaar) is True

    def test_invalid_aadhaar(self):
        """A number that fails Verhoeff."""
        from scripts.seed import make_invalid_aadhaar
        import random
        rng = random.Random(42)
        bad = make_invalid_aadhaar(rng)
        assert verhoeff_validate(bad) is False

    def test_known_value(self):
        """Standard Verhoeff test vector: '236' check digit is 3 -> '2363' is valid."""
        assert verhoeff_validate("2363") is True
        assert verhoeff_validate("2364") is False
        from scripts.seed import _verhoeff_checksum
        base = "12345678901"
        check = _verhoeff_checksum(base)
        assert verhoeff_validate(base + str(check)) is True
        wrong = (check + 1) % 10
        assert verhoeff_validate(base + str(wrong)) is False


# ---------------------------------------------------------------------------
# Phone normalization
# ---------------------------------------------------------------------------
class TestPhoneNormalization:
    def test_plain_10_digits(self):
        assert normalize_phone("9876543210") == "9876543210"

    def test_plus91_prefix(self):
        assert normalize_phone("+91 9876543210") == "9876543210"

    def test_plus91_no_space(self):
        assert normalize_phone("+919876543210") == "9876543210"

    def test_zero_prefix(self):
        assert normalize_phone("09876543210") == "9876543210"

    def test_space_in_middle(self):
        assert normalize_phone("98765 43210") == "9876543210"

    def test_91_prefix(self):
        assert normalize_phone("919876543210") == "9876543210"

    def test_not_a_phone_starts_with_5(self):
        """Numbers starting with 0-5 are not Indian mobile."""
        assert normalize_phone("5234567890") is None

    def test_invoice_not_phone(self):
        """INV-2026-0001 should not be detected as phone."""
        assert normalize_phone("INV-2026-0001") is None

    def test_amount_not_phone(self):
        """A large amount like 123456789012 should not match as phone."""
        # The regex should not match because the first digit is 1
        assert normalize_phone("123456789012") is None


# ---------------------------------------------------------------------------
# Decoy detection
# ---------------------------------------------------------------------------
class TestDecoys:
    def test_invoice_not_phone(self):
        """Invoice number INV-2026-0005 should not produce a phone finding."""
        findings = detect_phone("INV-2026-0005", "test", "R1/C1", {})
        assert len(findings) == 0

    def test_failing_12digit_not_aadhaar(self):
        """A 12-digit number failing Verhoeff should not be Aadhaar."""
        from scripts.seed import make_invalid_aadhaar
        import random
        rng = random.Random(99)
        bad = make_invalid_aadhaar(rng)
        findings = detect_aadhaar(bad, "test", "R1/C1", {})
        assert len(findings) == 0

    def test_amount_not_aadhaar(self):
        """An amount like 123456789012 should not be detected as Aadhaar."""
        # Starts with 1, so _AADHAAR_RE won't match (requires first digit 2-9)
        findings = detect_aadhaar("123456789012", "test", "R1/C1", {})
        assert len(findings) == 0


# ---------------------------------------------------------------------------
# Masking
# ---------------------------------------------------------------------------
class TestMasking:
    def test_mask_phone(self):
        masked = mask_value("9876543210")
        assert "9876543210" not in masked
        assert masked.endswith("3210")
        assert masked.startswith("X")

    def test_mask_short(self):
        masked = mask_value("abc")
        assert masked == "XXX"

    def test_mask_never_leaks_raw(self):
        """Masking a value should never return the raw value unchanged."""
        values = ["9876543210", "test@example.com", "ABCDE1234F", "234567890123"]
        for v in values:
            masked = mask_value(v)
            assert masked != v, f"Masking leaked raw value: {v}"


# ---------------------------------------------------------------------------
# Detector specifics
# ---------------------------------------------------------------------------
class TestDetectors:
    def test_email_detection(self):
        findings = detect_email("send to test@gmail.com please", "f.csv", "R2/C3", {})
        assert len(findings) == 1
        assert findings[0]["category"] == "email"

    def test_pan_detection(self):
        findings = detect_pan("PAN is ABCPE1234F", "f.csv", "R2/C2", {})
        assert len(findings) == 1
        assert findings[0]["category"] == "pan"

    def test_gstin_detection(self):
        findings = detect_gstin("GSTIN 29ABCPE1234F1ZA", "f.csv", "R2/C5", {})
        assert len(findings) == 1

    def test_ifsc_detection(self):
        findings = detect_ifsc("SBIN0012345", "f.csv", "R2/C6", {"header": "ifsc"})
        assert len(findings) == 1

    def test_upi_detection(self):
        findings = detect_upi("pay to user@ybl", "chat.txt", "line 5", {})
        assert len(findings) == 1

    def test_bank_account_with_header(self):
        findings = detect_bank_account("123456789012345", "f.csv", "R2/C5",
                                       {"header": "bank_account"})
        assert len(findings) == 1

    def test_bank_account_without_header(self):
        """Should not detect bank account without proper header."""
        findings = detect_bank_account("123456789012345", "f.csv", "R2/C5",
                                       {"header": "amount"})
        assert len(findings) == 0

    def test_name_with_header(self):
        findings = detect_name("Ramesh Kumar", "f.csv", "R2/C1", {"header": "name"})
        assert len(findings) == 1

    def test_name_from_sender(self):
        findings = detect_name("hello", "chat.txt", "line 1",
                              {"sender": "Ramesh Kumar"})
        assert len(findings) == 1

    def test_health_term(self):
        findings = detect_health_term("Patient has diabetes", "f.xlsx", "R2/C7", {})
        assert len(findings) == 1
