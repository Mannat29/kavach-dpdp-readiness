"""PII detection module: pure functions, no I/O side effects."""
import hashlib
import re
from typing import List, Dict, Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SALT = "kavach-dpdp-2026"

# ---------------------------------------------------------------------------
# Verhoeff algorithm
# ---------------------------------------------------------------------------
_VERHOEFF_D = [
    [0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],
    [3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],
    [6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],
    [9,8,7,6,5,4,3,2,1,0],
]
_VERHOEFF_P = [
    [0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],
    [8,9,1,6,0,4,3,5,2,7],[9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],
    [2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8],
]


def verhoeff_validate(num_str: str) -> bool:
    """Validate a number string using the Verhoeff checksum algorithm."""
    c = 0
    for i, ch in enumerate(reversed(num_str)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(ch)]]
    return c == 0


# ---------------------------------------------------------------------------
# Masking & hashing helpers
# ---------------------------------------------------------------------------
def mask_value(value: str, show_last: int = 4) -> str:
    """Mask a value, showing only the last N characters."""
    if len(value) <= show_last:
        return "X" * len(value)
    return "X" * (len(value) - show_last) + value[-show_last:]


def hash_value(value: str) -> str:
    """SHA-256 hash of salt + normalized value."""
    normalized = re.sub(r"\s+", "", value).lower()
    return hashlib.sha256((SALT + normalized).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Phone normalization
# ---------------------------------------------------------------------------
_PHONE_RE = re.compile(
    r"""(?<!\d)             # not preceded by digit
    (?:\+91[\s-]?|91[\s-]?|0)?  # optional country code / leading 0
    ([6-9]\d{4})            # first 5 digits (starts 6-9)
    [\s-]?                  # optional separator
    (\d{5})                 # last 5 digits
    (?!\d)                  # not followed by digit
    """,
    re.VERBOSE,
)


def normalize_phone(raw: str) -> Optional[str]:
    """Extract and normalize an Indian mobile number to 10 digits, or None."""
    m = _PHONE_RE.search(raw)
    if m:
        return m.group(1) + m.group(2)
    return None


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}", re.IGNORECASE)

# Aadhaar: 12 digits with optional spaces (groups of 4)
_AADHAAR_RE = re.compile(
    r"(?<!\d)([2-9]\d{3})[\s-]?(\d{4})[\s-]?(\d{4})(?!\d)"
)

# PAN: 5 uppercase + 4 digits + 1 uppercase
_PAN_RE = re.compile(r"(?<![A-Z0-9])[A-Z]{3}[ABCFGHLJPT][A-Z]\d{4}[A-Z](?![A-Z0-9])")

# GSTIN: 2 digits + PAN + 1 digit/char + Z + 1 alphanumeric
_GSTIN_RE = re.compile(r"(?<![A-Z0-9])\d{2}[A-Z]{3}[ABCFGHLJPT][A-Z]\d{4}[A-Z]\d[Z][A-Z0-9](?![A-Z0-9])")

# IFSC: 4 uppercase letters + 0 + 6 digits/uppercase
_IFSC_RE = re.compile(r"(?<![A-Z0-9])[A-Z]{4}0[A-Z0-9]{6}(?![A-Z0-9])")

# UPI ID: alphanumeric@provider
_UPI_RE = re.compile(r"[a-zA-Z0-9_.+-]+@(?:ok(?:axis|sbi|hdfc|icici)|ybl|paytm|ibl|upi|apl|freecharge)\b", re.IGNORECASE)

# Date of birth patterns
_DOB_RE = re.compile(
    r"(?<!\d)"
    r"(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}|\d{1,2}[-/]\d{1,2}[-/]\d{2})"
    r"(?!\d)"
)

# Health terms
HEALTH_TERMS = [
    "diabetes", "hiv", "hiv positive", "hiv negative", "thyroid", "thyroid disorder",
    "pregnancy", "pregnancy test", "hepatitis", "hepatitis b", "hypertension",
    "cancer", "cancer screening", "blood sugar high", "blood sugar",
]

# Column header hints for name detection
_NAME_HEADERS = {"name", "patient_name", "patient name", "staff_name", "staff name",
                 "full_name", "full name", "sender", "customer_name", "customer name"}
_BANK_HEADERS = {"bank_account", "bank account", "account_no", "account no",
                 "account_number", "account number", "bank_acc", "acc_no"}


# ---------------------------------------------------------------------------
# Detection functions — each returns list of findings
# ---------------------------------------------------------------------------
def detect_phone(text: str, source: str, location: str, meta: dict) -> List[Dict]:
    """Detect Indian mobile phone numbers."""
    findings = []
    for m in _PHONE_RE.finditer(text):
        digits = m.group(1) + m.group(2)
        # Check it's not part of a longer number sequence
        start = m.start()
        end = m.end()
        full = text
        # Get the full match including prefix
        prefix_match = re.match(r"(?:\+91[\s-]?|91[\s-]?|0)?", full[max(0, start-5):start+1])
        findings.append(_make_finding(source, location, "phone", digits, 0.95))
    return findings


def detect_email(text: str, source: str, location: str, meta: dict) -> List[Dict]:
    findings = []
    for m in _EMAIL_RE.finditer(text):
        findings.append(_make_finding(source, location, "email", m.group(), 0.98))
    return findings


def detect_aadhaar(text: str, source: str, location: str, meta: dict) -> List[Dict]:
    # Skip if header indicates this is a phone column
    header = meta.get("header", "").lower()
    if header in {"phone", "mobile", "contact", "phone_number", "mobile_number",
                  "contact_number", "phone number", "mobile number"}:
        return []
    findings = []
    for m in _AADHAAR_RE.finditer(text):
        digits = m.group(1) + m.group(2) + m.group(3)
        # Skip if preceded by +91 or +, which indicates a phone number
        start = m.start()
        prefix = text[max(0, start - 4):start].strip()
        if prefix.endswith("+91") or prefix.endswith("+") or prefix.endswith("91"):
            continue
        # Skip if the whole text looks like a phone with country code
        stripped = re.sub(r"[\s\-+]", "", text)
        if re.match(r"^(91|0)?[6-9]\d{9}$", stripped):
            continue
        if verhoeff_validate(digits):
            findings.append(_make_finding(source, location, "aadhaar", digits, 0.97))
    return findings


def detect_pan(text: str, source: str, location: str, meta: dict) -> List[Dict]:
    findings = []
    for m in _PAN_RE.finditer(text):
        val = m.group()
        # Avoid matching GSTIN substrings or IFSC codes
        start = m.start()
        if start >= 2 and re.match(r"\d{2}", text[start-2:start]):
            continue  # likely GSTIN
        findings.append(_make_finding(source, location, "pan", val, 0.95))
    return findings


def detect_gstin(text: str, source: str, location: str, meta: dict) -> List[Dict]:
    findings = []
    for m in _GSTIN_RE.finditer(text):
        findings.append(_make_finding(source, location, "gstin", m.group(), 0.95))
    return findings


def detect_ifsc(text: str, source: str, location: str, meta: dict) -> List[Dict]:
    findings = []
    for m in _IFSC_RE.finditer(text):
        val = m.group()
        # Skip if it looks like it's part of a GSTIN
        if _GSTIN_RE.search(text):
            # Check if this IFSC match overlaps with any GSTIN match
            overlaps = False
            for gm in _GSTIN_RE.finditer(text):
                if not (m.end() <= gm.start() or m.start() >= gm.end()):
                    overlaps = True
                    break
            if overlaps:
                continue
        findings.append(_make_finding(source, location, "ifsc", val, 0.90))
    return findings


def detect_upi(text: str, source: str, location: str, meta: dict) -> List[Dict]:
    findings = []
    for m in _UPI_RE.finditer(text):
        findings.append(_make_finding(source, location, "upi_id", m.group(), 0.95))
    return findings


def detect_dob(text: str, source: str, location: str, meta: dict) -> List[Dict]:
    """Detect dates of birth. Use header hints for tabular data."""
    header = meta.get("header", "").lower()
    dob_headers = {"dob", "date_of_birth", "date of birth", "birthday", "birth_date", "birth date"}
    if header not in dob_headers:
        return []
    findings = []
    m = _DOB_RE.search(text)
    if m:
        findings.append(_make_finding(source, location, "dob", m.group(), 0.90))
    elif re.match(r"^\d{4}-\d{2}-\d{2}$", text.strip()):
        findings.append(_make_finding(source, location, "dob", text.strip(), 0.90))
    return findings


def detect_bank_account(text: str, source: str, location: str, meta: dict) -> List[Dict]:
    """Detect bank account numbers only when column header suggests it."""
    header = meta.get("header", "").lower()
    if header not in _BANK_HEADERS:
        return []
    # Must be a numeric string of 9-18 digits
    digits = re.sub(r"\s+", "", text)
    if re.match(r"^\d{9,18}$", digits):
        return [_make_finding(source, location, "bank_account", digits, 0.85)]
    return []


def detect_name(text: str, source: str, location: str, meta: dict) -> List[Dict]:
    """Detect names from column headers or WhatsApp sender field."""
    header = meta.get("header", "").lower()
    sender = meta.get("sender", "")

    # For tabular data, use header hints
    if header in _NAME_HEADERS:
        # Simple heuristic: non-empty text that's not purely numeric
        if text and not text.replace(" ", "").isdigit():
            return [_make_finding(source, location, "name", text, 0.70)]

    # For WhatsApp, the sender is a name
    if sender:
        return [_make_finding(source, location, "name", sender, 0.65)]

    return []


def detect_health_term(text: str, source: str, location: str, meta: dict) -> List[Dict]:
    """Detect health-related terms."""
    findings = []
    text_lower = text.lower()
    for term in HEALTH_TERMS:
        if term in text_lower:
            findings.append(_make_finding(source, location, "health_term", term, 0.80))
            break  # one finding per cell/line
    return findings


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
ALL_DETECTORS = [
    detect_phone,
    detect_email,
    detect_aadhaar,
    detect_pan,
    detect_gstin,
    detect_ifsc,
    detect_upi,
    detect_dob,
    detect_bank_account,
    detect_name,
    detect_health_term,
]


def detect_all(text: str, source: str, location: str, meta: dict) -> List[Dict]:
    """Run all detectors on a text unit."""
    findings = []
    for detector in ALL_DETECTORS:
        findings.extend(detector(text, source, location, meta))
    return findings


def scan_file(path: str) -> List[Dict]:
    """Scan a file and return all findings."""
    import os
    from app.ingest import read_source

    source = os.path.basename(path)
    findings = []
    seen = set()  # deduplicate (source, location, category)

    for location, text, meta in read_source(path):
        for f in detect_all(text, source, location, meta):
            key = (f["source"], f["location"], f["category"])
            if key not in seen:
                seen.add(key)
                findings.append(f)

    return findings


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _make_finding(source: str, location: str, category: str, raw_value: str,
                  confidence: float) -> Dict:
    return {
        "source": source,
        "location": location,
        "category": category,
        "masked_sample": mask_value(raw_value),
        "value_hash": hash_value(raw_value),
        "confidence": confidence,
    }
