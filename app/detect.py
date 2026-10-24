"""PII detection module: pure functions, no I/O side effects."""
from datetime import datetime
import hashlib
import logging
import os
import re
import secrets
from typing import List, Dict, Optional

# ---------------------------------------------------------------------------
# Configuration & Salt Management
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
_warned_salt = False


def get_salt() -> str:
    """Read hashing salt from env KAVACH_SALT or data/.salt.

    If unset, generates a random salt, persists it to data/.salt (git-ignored),
    and logs a warning once.
    """
    global _warned_salt
    salt = os.environ.get("KAVACH_SALT")
    if salt:
        return salt.strip()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    salt_file = os.path.join(base_dir, "data", ".salt")
    if os.path.exists(salt_file):
        try:
            with open(salt_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return content
        except OSError:
            pass

    # First run without KAVACH_SALT or data/.salt: generate random salt
    generated = secrets.token_hex(16)
    os.makedirs(os.path.dirname(salt_file), exist_ok=True)
    try:
        with open(salt_file, "w", encoding="utf-8") as f:
            f.write(generated)
    except OSError as e:
        logger.warning("Could not persist generated salt to %s: %s", salt_file, e)

    if not _warned_salt:
        logger.warning(
            "KAVACH_SALT environment variable is unset; generated random salt and saved to data/.salt. "
            "Note: this is pseudonymisation, not anonymisation. In production, use keyed HMAC with a secret kept outside the database."
        )
        _warned_salt = True

    return generated


SALT = get_salt()

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


def mask_name(name: str) -> str:
    """Mask a name like 'R**** K***'."""
    if not name:
        return "****"
    words = name.strip().split()
    masked_words = []
    for w in words:
        if len(w) <= 1:
            masked_words.append(w)
        else:
            masked_words.append(w[0].upper() + "*" * min(4, len(w) - 1))
    return " ".join(masked_words)


def hash_value(value: str, salt: Optional[str] = None) -> str:
    """SHA-256 hash of salt + normalized value."""
    s = salt if salt is not None else get_salt()
    normalized = re.sub(r"\s+", "", value).lower()
    return hashlib.sha256((s + normalized).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Phone normalization
# ---------------------------------------------------------------------------
_PHONE_RE = re.compile(
    r"""(?<!\d)                         # not preceded by digit
    (?:(?:\+91|0091)[\s\-\.]?|91[\s\-\.]?|0[\s\-\.]?)?  # optional country code / trunk prefix
    (?:
        \([6-9]\d{4}\)[\s\-\.]?\d{5}           # (98765) 43210 or (98765)-43210
      | \([6-9]\d{2}\)[\s\-\.]?\d{3}[\s\-\.]?\d{4} # (987)-654-3210 or +91-(987)-654-3210
      | [6-9]\d{4}[\s\-\.]\d{5}               # 98765-43210 or 98765.43210 or 98765 43210
      | [6-9]\d{2}[\s\-\.]\d{3}[\s\-\.]\d{4}   # 987-654-3210 or 987.654.3210
      | [6-9]\d{3}[\s\-\.]\d{3}[\s\-\.]\d{3}   # 9876-543-210
      | [6-9]\d{9}                            # 9876543210
    )
    (?!\d)                             # not followed by digit
    """,
    re.VERBOSE,
)


def normalize_phone(raw: str) -> Optional[str]:
    """Extract and normalize an Indian mobile number to 10 digits, or None."""
    m = _PHONE_RE.search(raw)
    if m:
        d = re.sub(r"\D", "", m.group())
        if d.startswith("0091") and len(d) == 14:
            digits = d[4:]
        elif d.startswith("91") and len(d) == 12:
            digits = d[2:]
        elif d.startswith("0") and len(d) == 11:
            digits = d[1:]
        elif len(d) == 10:
            digits = d
        else:
            return None
        if len(digits) == 10 and digits[0] in "6789":
            return digits
    return None


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}", re.IGNORECASE)

# Aadhaar: 12 digits with optional spaces, dashes or dots; still Verhoeff-validated.
_AADHAAR_RE = re.compile(
    r"(?<!\d)([2-9]\d{3})[\s\-\.]?(\d{4})[\s\-\.]?(\d{4})(?!\d)"
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

# Health terms (sorted longest first to match full phrases before substrings)
HEALTH_TERMS = sorted([
    "diabetes", "hiv positive", "hiv negative", "hiv", "thyroid disorder", "thyroid",
    "pregnancy test", "pregnancy", "hepatitis b", "hepatitis", "hypertension",
    "cancer screening", "cancer", "blood sugar high", "blood sugar",
], key=len, reverse=True)

# Column header hints for name detection
_NAME_HEADERS = {
    "name", "patient_name", "patient name", "staff_name", "staff name",
    "full_name", "full name", "sender", "customer_name", "customer name",
    "applicant", "applicant_name", "applicant name", "candidate", "candidate_name",
}
_BANK_HEADERS = {"bank_account", "bank account", "account_no", "account no",
                 "account_number", "account number", "bank_acc", "acc_no"}

# Free-text name patterns
_NAME_FREE_PATTERNS = [
    r"(?:\bthis is|\bi am|\bi'm|\bmy name is|\bname is|\breferred by (?:dr\.?\s*)?|\battendant\s+name\s*[:\-]?|\bpatient\s+name\s*[:\-]?)",
    r"(?:\bmera naam|\bhumara naam|\bhamara naam)",
    r"(?:\bnanna hesaru)",
]
_NAME_FREE_RE = re.compile(
    r"(?:" + "|".join(_NAME_FREE_PATTERNS) + r")\s+([a-zA-Z\s\.]+)",
    re.IGNORECASE,
)
_NAME_STOPWORDS = {
    "and", "my", "who", "with", "for", "hai", "tha", "a", "an", "the", "is",
    "has", "had", "have", "was", "were",
    "number", "phone", "email", "contact", "from", "here", "please",
    "call", "send", "submitted", "confirmed", "today", "tomorrow",
    "dr", "mr", "mrs", "ms",
}


# ---------------------------------------------------------------------------
# Detection functions — each returns list of findings
# ---------------------------------------------------------------------------
def detect_phone(text: str, source: str, location: str, meta: dict) -> List[Dict]:
    """Detect Indian mobile phone numbers."""
    header = meta.get("header", "").lower()
    if header in _BANK_HEADERS or header in {"aadhaar", "national_id", "order_ref", "order_id"}:
        return []
    findings = []
    for m in _PHONE_RE.finditer(text):
        raw_val = m.group()
        d = re.sub(r"\D", "", raw_val)
        if d.startswith("0091") and len(d) == 14:
            digits = d[4:]
        elif d.startswith("91") and len(d) == 12:
            digits = d[2:]
        elif d.startswith("0") and len(d) == 11:
            digits = d[1:]
        elif len(d) == 10:
            digits = d
        else:
            continue
        if len(digits) == 10 and digits[0] in "6789":
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
        stripped = re.sub(r"[\s\-+.]", "", text)
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


def _compute_is_minor(dob_str: str) -> bool:
    """Compute whether age < 18 as of today without storing raw date."""
    today = datetime.now().date()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%y", "%d-%m-%y"):
        try:
            bdate = datetime.strptime(dob_str.strip(), fmt).date()
            age = today.year - bdate.year - ((today.month, today.day) < (bdate.month, bdate.day))
            return age < 18
        except ValueError:
            continue
    return False


def detect_dob(text: str, source: str, location: str, meta: dict) -> List[Dict]:
    """Detect dates of birth. Use header hints for tabular data."""
    header = meta.get("header", "").lower()
    dob_headers = {"dob", "date_of_birth", "date of birth", "birthday", "birth_date", "birth date"}
    if header not in dob_headers:
        return []
    findings = []
    dob_match = None
    m = _DOB_RE.search(text)
    if m:
        dob_match = m.group()
    elif re.match(r"^\d{4}-\d{2}-\d{2}$", text.strip()):
        dob_match = text.strip()

    if dob_match:
        is_minor = _compute_is_minor(dob_match)
        findings.append(_make_finding(source, location, "dob", dob_match, 0.90, meta={"is_minor": is_minor}))
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


def _extract_free_text_names(text: str) -> List[str]:
    names = []
    for m in _NAME_FREE_RE.finditer(text):
        raw_tail = m.group(1).strip()
        tail_clean = re.split(r"[,;!?\n\r]", raw_tail)[0].strip()
        words = tail_clean.split()
        cand_words = []
        for w in words:
            w_clean = w.strip(".").lower()
            if w_clean in _NAME_STOPWORDS or not w_clean.isalpha():
                break
            cand_words.append(w.strip("."))
            if len(cand_words) == 3:
                break
        if cand_words:
            if len(cand_words) == 1 and (len(cand_words[0]) < 3 or cand_words[0].lower() in {"dr", "mr", "mrs", "ms"}):
                continue
            name_val = " ".join(cand_words)
            name_val = re.sub(r"^(?:dr|mr|mrs|ms)\.?\s+", "", name_val, flags=re.IGNORECASE).strip()
            if len(name_val) >= 3:
                names.append(name_val)
    return names


def detect_name(text: str, source: str, location: str, meta: dict) -> List[Dict]:
    """Detect names from column headers, WhatsApp sender field, or free-text patterns."""
    header = meta.get("header", "").lower()
    sender = meta.get("sender", "")
    findings = []
    seen_names = set()

    # For tabular data, use header hints
    if header in _NAME_HEADERS:
        if text and not text.replace(" ", "").isdigit():
            findings.append(_make_finding(source, location, "name", text, 0.70))
            seen_names.add(text.strip().lower())

    # For WhatsApp, the sender is a name
    if sender:
        findings.append(_make_finding(source, location, "name", sender, 0.65))
        seen_names.add(sender.strip().lower())

    # Free text name patterns (heuristic: confidence 0.6)
    for name_candidate in _extract_free_text_names(text):
        if name_candidate.lower() not in seen_names:
            seen_names.add(name_candidate.lower())
            findings.append(_make_finding(source, location, "name", name_candidate, 0.60))

    return findings


def detect_health_term(text: str, source: str, location: str, meta: dict) -> List[Dict]:
    """Detect health-related terms using whole-word matching, skipping trivial negations."""
    findings = []
    text_lower = text.lower()
    for term in HEALTH_TERMS:
        pattern = r"\b" + re.escape(term) + r"\b"
        m = re.search(pattern, text_lower)
        if m:
            start_idx = m.start()
            prefix = text_lower[:start_idx].strip()
            if re.search(r"\b(?:no|not|without|denies|negative for)\s*$", prefix):
                continue
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
                  confidence: float, meta: Optional[dict] = None) -> Dict:
    sample = mask_name(raw_value) if category == "name" else mask_value(raw_value)
    res = {
        "source": source,
        "location": location,
        "category": category,
        "masked_sample": sample,
        "value_hash": hash_value(raw_value),
        "confidence": confidence,
    }
    if meta is not None:
        res["meta"] = meta
    return res
