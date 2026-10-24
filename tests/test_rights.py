"""Tests for app.rights: classify_message, parse_whatsapp_text, process_intake, resolve_sender."""
import pytest
from app.db import init_db, get_db
from app.rights import classify_message, parse_whatsapp_text, process_intake, resolve_sender, mask_message_excerpt


# ---------------------------------------------------------------------------
# classify_message
# ---------------------------------------------------------------------------
class TestClassifyMessage:
    def test_hinglish_erase(self):
        r = classify_message("Mera number aur details list se hata dijiye")
        assert r["intent"] == "erase"
        assert r["confidence"] >= 0.7

    def test_kannada_latin_erase(self):
        r = classify_message("Nanna details delete maadi, please")
        assert r["intent"] == "erase"

    def test_english_access(self):
        r = classify_message("can you send me what details you have about me")
        assert r["intent"] == "access"

    def test_english_correct(self):
        r = classify_message("my phone number is wrong, please update it")
        assert r["intent"] == "correct"

    def test_withdraw_consent(self):
        r = classify_message("stop sending me reminders please")
        assert r["intent"] == "withdraw_consent"

    def test_complaint(self):
        r = classify_message("I want to complain about how my data is being shared")
        assert r["intent"] == "complaint"

    def test_false_positive_delete_report(self):
        r = classify_message("please delete the old report from the group")
        assert r["intent"] == "none", f"Expected none, got {r['intent']}"

    def test_false_positive_delete_message(self):
        r = classify_message("delete this message, wrong chat")
        assert r["intent"] == "none", f"Expected none, got {r['intent']}"

    def test_english_erase_delete_my_data(self):
        r = classify_message("please delete my data from your system")
        assert r["intent"] == "erase"

    def test_english_erase_right_to_be_forgotten(self):
        r = classify_message("I am invoking my right to be forgotten")
        assert r["intent"] == "erase"

    def test_none_for_random_text(self):
        r = classify_message("Good morning! See you at 10am")
        assert r["intent"] == "none"

    def test_confidence_multi_word_keyword(self):
        r = classify_message("right to erasure please")
        assert r["intent"] == "erase"
        assert r["confidence"] == 0.90  # 3-word keyword

    def test_confidence_two_word_keyword(self):
        r = classify_message("hata dijiye please")
        assert r["intent"] == "erase"
        assert r["confidence"] == 0.80  # 2-word keyword

    def test_erase_priority_over_complaint(self):
        # A message that could match both erase and complaint; erase checked first
        r = classify_message("remove my data, I want to complain about data breach")
        assert r["intent"] == "erase"

    def test_empty_string(self):
        r = classify_message("")
        assert r["intent"] == "none"


# ---------------------------------------------------------------------------
# parse_whatsapp_text
# ---------------------------------------------------------------------------
class TestParseWhatsappText:
    def test_parse_8_messages(self):
        import os
        demo_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "demo", "demo_requests.txt"
        )
        with open(demo_file, encoding="utf-8") as f:
            text = f.read()
        messages = parse_whatsapp_text(text)
        assert len(messages) == 8

    def test_parse_sender_and_text(self):
        text = "20/10/26, 9:05 pm - Ramesh Kumar: Mera number aur details list se hata dijiye"
        messages = parse_whatsapp_text(text)
        assert len(messages) == 1
        assert messages[0]["sender"] == "Ramesh Kumar"
        assert "hata dijiye" in messages[0]["text"]
        assert messages[0]["timestamp"] == "20/10/26, 9:05 pm"

    def test_skip_non_message_lines(self):
        text = "This is a system line\n20/10/26, 9:05 pm - Alice: hello"
        messages = parse_whatsapp_text(text)
        assert len(messages) == 1
        assert messages[0]["sender"] == "Alice"

    def test_empty_text(self):
        assert parse_whatsapp_text("") == []


# ---------------------------------------------------------------------------
# process_intake (uses isolate_test_database fixture from conftest)
# ---------------------------------------------------------------------------
class TestProcessIntake:
    def test_intake_from_demo_requests(self, isolate_test_database):
        import os
        conn = get_db(isolate_test_database)
        demo_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "demo", "demo_requests.txt"
        )
        with open(demo_file, encoding="utf-8") as f:
            text = f.read()
        messages = parse_whatsapp_text(text)
        created = process_intake(messages, conn)
        # 6 real intents: erase(2), access(1), correct(1), withdraw_consent(1), complaint(1)
        # 2 false positives -> none -> skipped
        assert len(created) == 6

    def test_erase_request_created(self, isolate_test_database):
        conn = get_db(isolate_test_database)
        msgs = [{"sender": "Test User", "text": "please delete my data", "timestamp": "20/10/26, 9:00 am"}]
        created = process_intake(msgs, conn)
        assert len(created) == 1
        assert created[0]["intent"] == "erase"

    def test_none_messages_skipped(self, isolate_test_database):
        conn = get_db(isolate_test_database)
        msgs = [
            {"sender": "A", "text": "delete this message, wrong chat", "timestamp": ""},
            {"sender": "B", "text": "Good morning!", "timestamp": ""},
        ]
        created = process_intake(msgs, conn)
        assert len(created) == 0

    def test_request_stored_in_db(self, isolate_test_database):
        conn = get_db(isolate_test_database)
        msgs = [{"sender": "Priya Sharma", "text": "stop sending me reminders", "timestamp": "22/10/26, 3:30 pm"}]
        created = process_intake(msgs, conn)
        assert len(created) == 1
        cur = conn.cursor()
        cur.execute("SELECT * FROM rights_requests WHERE id = ?", (created[0]["id"],))
        row = cur.fetchone()
        assert row is not None
        assert row["intent"] == "withdraw_consent"
        assert row["status"] in ("received", "identity_pending")

    def test_due_at_set(self, isolate_test_database):
        from app.config import RESPONSE_DAYS
        conn = get_db(isolate_test_database)
        msgs = [{"sender": "X", "text": "remove my number", "timestamp": "20/10/26, 9:00 am"}]
        created = process_intake(msgs, conn)
        assert created[0]["due_at"] is not None
        import datetime
        received = datetime.datetime.fromisoformat(created[0]["received_at"])
        due = datetime.datetime.fromisoformat(created[0]["due_at"])
        assert (due - received).days == RESPONSE_DAYS

    def test_sender_masked_in_output(self, isolate_test_database):
        conn = get_db(isolate_test_database)
        msgs = [{"sender": "Ramesh Kumar", "text": "erase my data", "timestamp": ""}]
        created = process_intake(msgs, conn)
        assert "Ramesh" not in created[0]["sender_masked"] or created[0]["sender_masked"].startswith("R")
        # Must not store the full raw name
        assert created[0]["sender_masked"] != "Ramesh Kumar"

    def test_ledger_entry_created(self, isolate_test_database):
        conn = get_db(isolate_test_database)
        msgs = [{"sender": "A", "text": "delete my details please", "timestamp": ""}]
        process_intake(msgs, conn)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as c FROM ledger")
        assert cur.fetchone()["c"] >= 1


# ---------------------------------------------------------------------------
# resolve_sender
# ---------------------------------------------------------------------------
class TestResolveSender:
    def test_no_match_returns_none(self, isolate_test_database):
        conn = get_db(isolate_test_database)
        pid, res = resolve_sender("Nobody Known", "some text", conn)
        assert pid is None
        assert res == "none"

    def test_name_match_probable(self, isolate_test_database):
        """If DB has a person with the same name hash, resolution is 'probable'."""
        from app.detect import hash_value
        conn = get_db(isolate_test_database)
        cur = conn.cursor()
        # Insert a person with name_hash matching "Test Person"
        name_hash = hash_value("Test Person")
        cur.execute(
            "INSERT INTO people (id, label, masked_name, name_hash) VALUES (?, ?, ?, ?)",
            (99, "Person 99 (T**** P****)", "T**** P****", name_hash)
        )
        conn.commit()
        pid, res = resolve_sender("Test Person", "hello", conn)
        assert pid == 99
        assert res == "probable"


# ---------------------------------------------------------------------------
# mask_message_excerpt
# ---------------------------------------------------------------------------
class TestMaskMessageExcerpt:
    def test_masks_phone(self):
        result = mask_message_excerpt("call me at 9876543210 please")
        assert "9876543210" not in result
        assert "[PHONE]" in result

    def test_masks_email(self):
        result = mask_message_excerpt("my email is test@example.com ok")
        assert "test@example.com" not in result
        assert "[EMAIL]" in result

    def test_truncates_long_text(self):
        long_text = "x" * 300
        result = mask_message_excerpt(long_text, max_len=200)
        assert len(result) <= 204  # 200 + "..."
        assert result.endswith("...")

    def test_plain_text_unchanged(self):
        text = "hata dijiye meri details"
        result = mask_message_excerpt(text)
        assert result == text
