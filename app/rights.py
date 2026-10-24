"""Rights module: request catcher, intent classifier, erasure intake, and related endpoints."""
import hashlib
import json
import os
import re
import datetime
from typing import Dict, List, Optional, Tuple

import yaml

from app.db import get_db
from app.detect import hash_value, mask_value, mask_name, scan_file, normalize_phone
from app.config import RESPONSE_DAYS
from app.ledger import append_ledger

# ---------------------------------------------------------------------------
# Load intent rules from YAML
# ---------------------------------------------------------------------------
_RULES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules")


def _load_intents_yaml() -> dict:
    path = os.path.join(_RULES_DIR, "intents.yaml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


_INTENT_RULES = _load_intents_yaml()


# ---------------------------------------------------------------------------
# WhatsApp chat parser (reuse ingest regex)
# ---------------------------------------------------------------------------
_WA_RE = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}\s*[ap]m)\s*-\s*(.+?):\s*(.+)$",
    re.IGNORECASE,
)


def parse_whatsapp_text(text: str) -> List[Dict]:
    """Parse WhatsApp export text into list of {sender, text, timestamp} dicts."""
    messages = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _WA_RE.match(line)
        if m:
            messages.append({
                "sender": m.group(2).strip(),
                "text": m.group(3).strip(),
                "timestamp": m.group(1).strip(),
            })
    return messages


# ---------------------------------------------------------------------------
# classify_message
# ---------------------------------------------------------------------------
def classify_message(text: str) -> Dict:
    """Classify a message text into an intent dict: {intent, confidence, reason}.

    Intents: erase, access, correct, withdraw_consent, complaint, none.
    No LLM — keyword/regex rules only.
    """
    rules = _INTENT_RULES.get("intents", {})
    text_lower = text.lower().strip()

    # Check intents in priority order
    intent_order = ["erase", "access", "correct", "withdraw_consent", "complaint"]

    for intent in intent_order:
        rule = rules.get(intent, {})
        all_keywords = (
            rule.get("keywords_en", []) +
            rule.get("keywords_hinglish", []) +
            rule.get("keywords_kannada_latin", [])
        )
        for kw in all_keywords:
            if kw.lower() in text_lower:
                # For erase intent, check that a personal-data object is present
                # AND that it's not a false-positive object
                if intent == "erase":
                    result = _check_erase_intent(text_lower, rule, kw)
                    if result:
                        return result
                    else:
                        continue
                # For other intents, match is sufficient
                confidence = _keyword_confidence(kw, text_lower)
                return {
                    "intent": intent,
                    "confidence": confidence,
                    "reason": f"matched keyword: '{kw}'",
                }

    return {"intent": "none", "confidence": 1.0, "reason": "no intent keywords matched"}


def _check_erase_intent(text_lower: str, rule: dict, matched_kw: str) -> Optional[Dict]:
    """Validate erase intent: personal-data object required, false-positive objects disqualify."""
    false_positive_objs = [o.lower() for o in rule.get("false_positive_objects", [])]
    personal_data_objs = [o.lower() for o in rule.get("personal_data_objects", [])]

    # If matched keyword already implies personal data (e.g. "hata dijiye" with "number" context)
    # or is a generic "remove me" type, it qualifies.
    # Also: pure-rights keywords like "right to erasure", "right to be forgotten", or
    # Hinglish/Kannada-Latin erasure phrases are self-sufficient — they inherently refer to
    # the requester's own personal data.
    kw_implies_personal = any(p in matched_kw.lower() for p in [
        "number", "detail", "data", "record", "name", "email", "address",
        "nanna", "mera", "meri", "me",
        # self-sufficient erasure rights phrases
        "erasure", "forgotten", "hata", "maadi", "tegedu", "beda",
    ])

    # Find what comes after a delete verb — check for false-positive objects
    fp_hit = False
    for fp_obj in false_positive_objs:
        # Check: "delete/remove <fp_obj>" without a personal data qualifier nearby
        pattern = rf"\b(delete|remove|hata|erase|tegedu)\b[^.!?\n]{{0,30}}\b{re.escape(fp_obj)}\b"
        if re.search(pattern, text_lower):
            # Check if a personal-data object also appears — if so, personal data takes priority
            has_personal = any(re.search(rf"\b{re.escape(p)}\b", text_lower) for p in personal_data_objs)
            if not has_personal:
                fp_hit = True
                break

    if fp_hit:
        return None  # False positive

    # Check personal data object present
    has_personal = kw_implies_personal or any(
        re.search(rf"\b{re.escape(p)}\b", text_lower) for p in personal_data_objs
    )
    if not has_personal:
        # Generic "delete" / "remove" without personal-data object is not erase
        return None

    confidence = _keyword_confidence(matched_kw, text_lower)
    return {
        "intent": "erase",
        "confidence": confidence,
        "reason": f"matched keyword: '{matched_kw}'",
    }


def _keyword_confidence(kw: str, text: str) -> float:
    """Assign confidence based on keyword length/specificity."""
    if len(kw.split()) >= 3:
        return 0.90
    elif len(kw.split()) == 2:
        return 0.80
    else:
        return 0.70


# ---------------------------------------------------------------------------
# Resolve sender -> person_id in DB
# ---------------------------------------------------------------------------
def resolve_sender(sender: str, message_text: str, conn) -> Tuple[Optional[int], str]:
    """
    Resolve a sender name + message text to a person_id.
    Returns (person_id, resolution) where resolution is:
      'strong'    — matched via phone/email/Aadhaar found in message
      'probable'  — matched via name hash
      'ambiguous' — name matches multiple people
      'none'      — no match found
    """
    cur = conn.cursor()

    # --- Strong: look for phone/email/Aadhaar in the message text ---
    phone = normalize_phone(message_text)
    if phone:
        phone_hash = hash_value(phone)
        cur.execute(
            "SELECT DISTINCT pr.person_id FROM findings f "
            "JOIN person_records pr ON f.source_id = pr.source_id AND f.record_key = pr.record_key "
            "WHERE f.category = 'phone' AND f.value_hash = ?",
            (phone_hash,)
        )
        rows = cur.fetchall()
        if len(rows) == 1:
            return rows[0]["person_id"], "strong"

    email_m = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}", message_text)
    if email_m:
        email_hash = hash_value(email_m.group())
        cur.execute(
            "SELECT DISTINCT pr.person_id FROM findings f "
            "JOIN person_records pr ON f.source_id = pr.source_id AND f.record_key = pr.record_key "
            "WHERE f.category = 'email' AND f.value_hash = ?",
            (email_hash,)
        )
        rows = cur.fetchall()
        if len(rows) == 1:
            return rows[0]["person_id"], "strong"

    # Aadhaar in message
    aadhaar_m = re.search(r"([2-9]\d{3})[\s\-.]?(\d{4})[\s\-.]?(\d{4})", message_text)
    if aadhaar_m:
        digits = aadhaar_m.group(1) + aadhaar_m.group(2) + aadhaar_m.group(3)
        aadhaar_hash = hash_value(digits)
        cur.execute(
            "SELECT DISTINCT pr.person_id FROM findings f "
            "JOIN person_records pr ON f.source_id = pr.source_id AND f.record_key = pr.record_key "
            "WHERE f.category = 'aadhaar' AND f.value_hash = ?",
            (aadhaar_hash,)
        )
        rows = cur.fetchall()
        if len(rows) == 1:
            return rows[0]["person_id"], "strong"

    # --- Probable: name hash match ---
    if sender:
        name_hash = hash_value(sender)
        cur.execute(
            "SELECT id FROM people WHERE name_hash = ?",
            (name_hash,)
        )
        rows = cur.fetchall()
        if len(rows) == 1:
            return rows[0]["id"], "probable"
        elif len(rows) > 1:
            return None, "ambiguous"

    return None, "none"


# ---------------------------------------------------------------------------
# Mask message excerpt (run detection and mask identifiers)
# ---------------------------------------------------------------------------
def mask_message_excerpt(text: str, max_len: int = 200) -> str:
    """Mask PII identifiers in a message excerpt using regex."""
    from app.detect import _PHONE_RE, _EMAIL_RE, _AADHAAR_RE
    result = text
    # Mask phones
    result = _PHONE_RE.sub("[PHONE]", result)
    # Mask emails
    result = _EMAIL_RE.sub("[EMAIL]", result)
    # Mask Aadhaar
    result = _AADHAAR_RE.sub("[AADHAAR]", result)
    if len(result) > max_len:
        result = result[:max_len] + "..."
    return result


# ---------------------------------------------------------------------------
# Intake processing
# ---------------------------------------------------------------------------
def process_intake(messages: List[Dict], conn) -> List[Dict]:
    """
    Process a list of {sender, text, timestamp} messages.
    For each non-'none' message, create a rights_request row.
    Returns list of created request dicts.
    """
    created = []
    now = datetime.datetime.utcnow()

    for msg in messages:
        sender = msg.get("sender", "").strip()
        text = msg.get("text", "").strip()
        timestamp_str = msg.get("timestamp", "")

        classification = classify_message(text)
        intent = classification["intent"]
        if intent == "none":
            continue

        confidence = classification["confidence"]
        person_id, resolution = resolve_sender(sender, text, conn)

        # Determine status
        if resolution in ("strong",):
            status = "received"
        elif resolution in ("probable", "ambiguous"):
            status = "identity_pending"
        else:
            status = "received"

        # Parse received_at
        received_at = now
        if timestamp_str:
            for fmt in ("%d/%m/%y, %I:%M %p", "%d/%m/%Y, %I:%M %p",
                        "%d/%m/%y, %I:%M%p", "%d/%m/%Y, %I:%M%p"):
                try:
                    received_at = datetime.datetime.strptime(timestamp_str, fmt)
                    break
                except ValueError:
                    pass

        due_at = received_at + datetime.timedelta(days=RESPONSE_DAYS)

        # Masked sender label
        sender_masked = mask_name(sender) if sender else "[unknown]"

        # Mask excerpt
        excerpt_masked = mask_message_excerpt(text)

        cur = conn.cursor()
        cur.execute("""
            INSERT INTO rights_requests
              (intent, sender_masked, person_id, resolution, confidence,
               received_at, due_at, status, message_excerpt_masked)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            intent,
            sender_masked,
            person_id,
            resolution,
            confidence,
            received_at.isoformat(),
            due_at.isoformat(),
            status,
            excerpt_masked,
        ))
        request_id = cur.lastrowid
        conn.commit()

        append_ledger({
            "event": "intake",
            "request_id": request_id,
            "intent": intent,
            "resolution": resolution,
            "status": status,
        }, conn)

        created.append({
            "id": request_id,
            "intent": intent,
            "sender_masked": sender_masked,
            "person_id": person_id,
            "resolution": resolution,
            "confidence": confidence,
            "status": status,
            "received_at": received_at.isoformat(),
            "due_at": due_at.isoformat(),
        })

    return created
