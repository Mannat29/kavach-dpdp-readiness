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


# ---------------------------------------------------------------------------
# Format bug fix tests (Task 3a)
# ---------------------------------------------------------------------------
class TestFixedFormats:
    def test_phone_formats(self):
        """Test varied separators: dash, dot, brackets, prefixes +91, 0091, 91, 0."""
        cases = [
            ("+91-98765-43210", "9876543210"),
            ("(98765) 43210", "9876543210"),
            ("+91-(987)-654-3210", "9876543210"),
            ("987.654.3210", "9876543210"),
            ("+91.9876543210", "9876543210"),
            ("(98765)-43210", "9876543210"),
            ("0091-98765-43210", "9876543210"),
            ("0-98765-43210", "9876543210"),
            ("91-98765-43210", "9876543210"),
        ]
        for raw, expected in cases:
            norm = normalize_phone(raw)
            assert norm == expected, f"Failed normalize_phone on {raw}: got {norm}"
            findings = detect_phone(f"call me at {raw} thanks", "test.csv", "R1/C1", {})
            assert len(findings) == 1, f"Failed detect_phone on {raw}"
            assert findings[0]["masked_sample"].endswith("3210")

    def test_phone_no_match_in_longer_digit_runs(self):
        """Must not match digits inside longer digit runs (order numbers, Aadhaar, account numbers)."""
        bad_cases = [
            "ORD-987654321012",
            "98765432101234",
            "123456789012",
        ]
        for raw in bad_cases:
            assert normalize_phone(raw) is None, f"Should not match {raw}"
            findings = detect_phone(raw, "test.csv", "R1/C1", {})
            assert len(findings) == 0, f"detect_phone should not match {raw}"

    def test_aadhaar_with_dots_dashes_spaces(self):
        """Aadhaar with spaces, dashes, or dots; Verhoeff validated."""
        from scripts.seed import make_aadhaar
        import random
        rng = random.Random(42)
        valid = make_aadhaar(rng)
        # 12 digits
        assert len(valid) == 12

        dotted = f"{valid[:4]}.{valid[4:8]}.{valid[8:]}"
        dashed = f"{valid[:4]}-{valid[4:8]}-{valid[8:]}"
        spaced = f"{valid[:4]} {valid[4:8]} {valid[8:]}"

        for v in [dotted, dashed, spaced, valid]:
            findings = detect_aadhaar(f"Aadhaar: {v}", "doc.csv", "R1/C1", {})
            assert len(findings) == 1, f"Failed to detect Aadhaar format: {v}"
            assert findings[0]["category"] == "aadhaar"

    def test_health_term_whole_word_and_negation(self):
        """health_term must use whole-word matching and skip trivial negations."""
        # False positive fix: 'Archived record' contains 'hiv' but is not a whole-word match
        f_archived = detect_health_term("Archived record", "patients.xlsx", "Archived/R2/C4", {})
        assert len(f_archived) == 0

        # Positive case
        f_positive = detect_health_term("Patient diagnosed with diabetes", "patients.xlsx", "R2/C7", {})
        assert len(f_positive) == 1
        assert f_positive[0]["masked_sample"] == "XXXXetes"

        # Negations should be skipped
        negations = [
            "Patient has no diabetes",
            "Negative for HIV",
            "Patient denies hypertension",
            "without diabetes history",
        ]
        for neg in negations:
            findings = detect_health_term(neg, "doc.csv", "R1/C1", {})
            assert len(findings) == 0, f"Negation not skipped for '{neg}'"

    def test_name_in_free_text(self):
        """Free-text name patterns with confidence 0.6."""
        cases = [
            ("hi this is ramesh, my number is 9876543210", "ramesh"),
            ("Hello, I am Priya Sharma and my email is test@mail.com", "Priya Sharma"),
            ("my name is Suresh Gowda please note", "Suresh Gowda"),
            ("mera naam Rajesh Shetty hai", "Rajesh Shetty"),
            ("nanna hesaru Deepa Bhat", "Deepa Bhat"),
            ("Referred by Dr. Harish Nayak", "Harish Nayak"),
            ("Attendant name: Pooja Kulkarni", "Pooja Kulkarni"),
        ]
        for text, expected in cases:
            findings = detect_name(text, "chat.txt", "line 1", {})
            assert len(findings) >= 1, f"Failed to detect name in '{text}'"
            names = [f["masked_sample"] for f in findings]
            # Check confidence is 0.6
            free_findings = [f for f in findings if f["confidence"] == 0.6]
            assert len(free_findings) >= 1, f"Expected 0.6 confidence for free text: {text}"
