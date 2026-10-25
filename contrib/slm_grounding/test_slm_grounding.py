import http.server, json, threading
import pytest
from app import slm

T = "Client has diabetes and is a 15-year-old student. Call 9876543210."
LOC = {"filename": "c.xlsx", "sheet_name": "S1", "column_name": "Notes", "row_index": 3}


def span(text, sub, cat="health", nth=0):
    i = -1
    for _ in range(nth + 1):
        i = text.index(sub, i + 1)
    return {"category": cat, "start": i, "end": i + len(sub), "verbatim_text": sub}


def live(items, text=T):
    out = json.dumps({"findings": items})
    return slm.scan_chunk(text, LOC, mode="live", _transport=lambda *a: out)


# ---------- grounding rule 1: verbatim offset check ----------
def test_positive_verbatim_offset_check():
    r = live([span(T, "diabetes")])
    assert r["chunk_status"] == "ok" and r["needs_review"] == []
    f = r["findings"][0]
    assert f["category"] == "health"
    assert T[f["start"]:f["end"]] == "diabetes"      # consumer re-slices on demand


def test_text_mismatch_routed_to_needs_review():
    bad = span(T, "diabetes")
    bad["verbatim_text"] = "cancer"                   # offsets valid, text differs
    r = live([bad])
    assert r["findings"] == []
    assert r["chunk_status"] == "needs_review"
    assert r["needs_review"][0]["reason"] == "not_verbatim"
    assert "cancer" not in json.dumps(r)


def test_wrong_offsets_unique_text_recovered():
    bad = span(T, "diabetes")
    bad["start"] += 1; bad["end"] += 1                # text exists once, offsets shifted
    r = live([bad])
    assert r["chunk_status"] == "ok" and r["needs_review"] == []
    f = r["findings"][0]
    assert T[f["start"]:f["end"]] == "diabetes"
    assert r["repairs"] == [{"category": "health", "start": f["start"], "end": f["end"],
                             "repair": "exact_match_recovered", "locator": LOC}]
    assert set(f) == {"category", "start", "end", "locator"}   # repair kept out of finding
    assert "diabetes" not in json.dumps(r)


def test_correct_offsets_not_marked_repaired():
    assert live([span(T, "diabetes")])["repairs"] == []


def test_ambiguous_text_not_repaired():
    t2 = "diabetes noted; family history of diabetes"
    bad = {"category": "health", "start": 0, "end": 3, "verbatim_text": "diabetes"}
    r = live([bad], text=t2)
    assert r["findings"] == [] and r["repairs"] == []
    assert r["needs_review"][0]["reason"] == "not_verbatim"
    assert r["chunk_status"] == "needs_review"


def test_overlapping_occurrences_count_as_ambiguous():
    bad = {"category": "health", "start": 2, "end": 3, "verbatim_text": "aa"}
    assert live([bad], text="aaa")["needs_review"][0]["reason"] == "not_verbatim"


def test_absent_text_not_repaired():
    bad = {**span(T, "diabetes"), "verbatim_text": "cancer"}
    r = live([bad])
    assert r["repairs"] == [] and r["needs_review"][0]["reason"] == "not_verbatim"


def test_empty_text_not_repaired():
    bad = {"category": "health", "start": 0, "end": 1, "verbatim_text": ""}
    assert live([bad])["needs_review"][0]["reason"] == "not_verbatim"


def test_repaired_span_still_checked_against_masked_regions():
    bad = {"category": "name", "start": 0, "end": 4, "verbatim_text": "9876543210"}
    assert live([bad])["needs_review"][0]["reason"] == "overlaps_masked_identifier"


@pytest.mark.parametrize("patch", [{"start": None}, {"end": "9"}, {"start": 1.5},
                                   {"start": True}])
def test_non_numeric_offsets_rejected_no_repair(patch):
    r = live([{**span(T, "diabetes"), **patch}])
    assert r["findings"] == [] and r["repairs"] == []
    assert r["needs_review"][0]["reason"] == "not_verbatim"


@pytest.mark.parametrize("patch", [{"start": -1}, {"end": 10_000},
                                   {"start": 10, "end": 10}, {"start": 12, "end": 5}])
def test_out_of_bounds_int_offsets_recovered_when_unique(patch):
    r = live([{**span(T, "diabetes"), **patch}])
    assert r["chunk_status"] == "ok" and len(r["repairs"]) == 1
    f = r["findings"][0]
    assert T[f["start"]:f["end"]] == "diabetes"


@pytest.mark.parametrize("patch", [{"start": -1}, {"end": 10_000}])
def test_out_of_bounds_offsets_ambiguous_rejected(patch):
    s = {"category": "health", "start": 0, "end": 8, "verbatim_text": "diabetes", **patch}
    r = live([s], text="diabetes and diabetes")
    assert r["findings"] == [] and r["needs_review"][0]["reason"] == "not_verbatim"


def test_missing_offsets_rejected():
    r = live([{"category": "health", "verbatim_text": "diabetes"}])
    assert r["needs_review"][0]["reason"] == "not_verbatim"


# ---------- rule 2: zero-text storage ----------
def test_no_text_stored_anywhere():
    r = live([span(T, "diabetes"), {**span(T, "diabetes"), "verbatim_text": "cancer"}])
    dump = json.dumps(r)
    assert "diabetes" not in dump and "cancer" not in dump
    for f in r["findings"]:
        assert set(f) == {"category", "start", "end", "locator"}
        assert f["locator"] == LOC and f["start"] >= 0 and f["end"] > f["start"]


def test_extra_keys_stripped_from_output():
    s = {**span(T, "diabetes"), "advice": "x", "legal_basis": "y"}
    r = live([s])
    assert set(r["findings"][0]) == {"category", "start", "end", "locator"}


# ---------- rule 3: pre-masking ----------
def test_masking_identical_length_hash_safe():
    m = slm.mask_identifiers(T)
    assert len(m) == len(T) and "9876543210" not in m
    h = "a" * 20 + "9876543210" + "b" * 34
    assert slm.mask_identifiers(h) == h


def test_masked_text_sent_to_model():
    seen = {}
    def tr(masked, *a):
        seen["m"] = masked; return json.dumps({"findings": []})
    slm.scan_chunk(T, LOC, mode="live", _transport=tr)
    assert "9876543210" not in seen["m"] and len(seen["m"]) == len(T)


def test_span_overlapping_masked_region_rejected():
    s = span(T, "9876543210", cat="name")             # text matches source, but masked
    r = live([s])
    assert r["findings"] == []
    assert r["needs_review"][0]["reason"] == "overlaps_masked_identifier"
    s2 = span(T, "Call 98765", cat="name")            # partial overlap
    assert live([s2])["needs_review"][0]["reason"] == "overlaps_masked_identifier"


# ---------- rule 4: routing and failure containment ----------
def test_unapproved_category_routed_not_dropped():
    r = live([{**span(T, "diabetes"), "category": "religion"}])
    assert r["findings"] == []
    assert r["needs_review"][0]["reason"] == "unapproved_category"
    assert "category" not in r["needs_review"][0]


def test_non_dict_item_routed():
    r = live(["junk", 5, None])
    assert [x["reason"] for x in r["needs_review"]] == ["malformed_item"] * 3


def test_mixed_chunk_keeps_good_and_flags_chunk():
    r = live([span(T, "diabetes"), {**span(T, "student", "minor"), "verbatim_text": "x"}])
    assert len(r["findings"]) == 1
    assert r["chunk_status"] == "needs_review"


def test_too_many_findings_routed():
    items = [span(T, "diabetes")] * 25
    r = live(items)
    assert any(x["reason"] == "too_many_findings" for x in r["needs_review"])


def test_malformed_output_no_crash():
    r = slm.scan_chunk(T, LOC, mode="live", _transport=lambda *a: "not json")
    assert r["chunk_status"] == "needs_review" and r["error"] == "malformed_output"
    r = slm.scan_chunk(T, LOC, mode="live", _transport=lambda *a: '{"findings": 5}')
    assert r["chunk_status"] == "needs_review"


def test_live_failure_never_falls_back_to_mock():
    def boom(*a): raise TimeoutError()
    r = slm.scan_chunk(T, LOC, mode="live", _transport=boom)
    assert r["mode"] == "live" and r["chunk_status"] == "needs_review"
    assert r["findings"] == [] and "demo_data" not in r
    assert r["needs_review"][0]["reason"] == "model_unavailable"


def test_oversize_chunk_to_review():
    r = slm.scan_chunk("a" * 5000, mode="mock")
    assert r["error"] == "chunk_too_large" and r["chunk_status"] == "needs_review"


# ---------- modes ----------
def test_off_by_default(monkeypatch):
    monkeypatch.delenv("SLM_MODE", raising=False)
    assert slm.scan_chunk(T)["chunk_status"] == "off"


def test_mock_marked_grounded_and_clean():
    r = slm.scan_chunk(T, LOC, mode="mock")
    assert r["demo_data"] and r["chunk_status"] == "ok"
    assert {f["category"] for f in r["findings"]} >= {"health", "minor"}
    for f in r["findings"]:
        assert T[f["start"]:f["end"]]


# ---------- network isolation ----------
@pytest.mark.parametrize("u", ["http://example.com", "http://localhost:11434",
                               "https://127.0.0.1", "http://10.0.0.5:11434",
                               "http://127.0.0.1.evil.com"])
def test_remote_urls_refused(u):
    with pytest.raises(slm.SLMConfigError):
        slm._parse_loopback_url(u)
    r = slm.scan_chunk(T, LOC, mode="live", url=u)
    assert r["chunk_status"] == "needs_review"


def test_redirect_not_followed():
    hits = []
    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path == "/api/chat":
                self.send_response(302); self.send_header("Location", "/x"); self.end_headers()
            else:
                hits.append(self.path); self.send_response(200); self.end_headers()
        def log_message(self, *a): pass
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    r = slm.scan_chunk(T, LOC, mode="live", url=f"http://127.0.0.1:{srv.server_port}")
    srv.shutdown()
    assert r["error"].startswith("live_failed") and hits == []


def test_proxy_env_ignored(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://evil:1"); monkeypatch.setenv("http_proxy", "http://evil:1")
    r = slm.scan_chunk(T, LOC, mode="live", url="http://127.0.0.1:9", timeout=1)
    assert "evil" not in json.dumps(r)


# ---------- ledger gate ----------
def test_is_clean_for_ledger_true_only_when_fully_ok():
    assert slm.is_clean_for_ledger(live([span(T, "diabetes")])) is True
    assert slm.is_clean_for_ledger(live([])) is True
    repaired = live([{**span(T, "diabetes"), "start": 0, "end": 3}])
    assert slm.is_clean_for_ledger(repaired) is True            # grounded after repair


def test_is_clean_for_ledger_false_otherwise():
    assert not slm.is_clean_for_ledger(live([{**span(T, "diabetes"), "verbatim_text": "x"}]))
    assert not slm.is_clean_for_ledger(live([span(T, "diabetes"), "junk"]))
    assert not slm.is_clean_for_ledger(slm.scan_chunk(T, LOC, mode="live",
                                                       _transport=lambda *a: "bad"))
    assert not slm.is_clean_for_ledger(slm.scan_chunk(T, LOC, mode="off"))
    assert not slm.is_clean_for_ledger(slm.scan_chunk(T, LOC, mode="mock"))   # demo data
    for junk in (None, {}, [], "ok", {"chunk_status": "ok"},
                 {"chunk_status": "ok", "needs_review": None},
                 {"chunk_status": "ok", "needs_review": [{"reason": "x"}]}):
        assert slm.is_clean_for_ledger(junk) is False
