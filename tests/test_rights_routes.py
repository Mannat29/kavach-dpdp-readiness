"""Tests for rights desk API routes."""
import json
import pytest
from app import create_app
from app.db import init_db, get_db


@pytest.fixture
def client(isolate_test_database):
    app = create_app({
        "TESTING": True,
        "DATABASE": isolate_test_database,
    })
    with app.test_client() as client:
        with app.app_context():
            init_db(isolate_test_database)
        yield client


class TestRightsClassifyEndpoint:
    def test_classify_erase(self, client):
        r = client.post("/api/rights/classify",
                        data=json.dumps({"text": "please delete my data"}),
                        content_type="application/json")
        assert r.status_code == 200
        body = r.get_json()
        assert body["intent"] == "erase"

    def test_classify_none(self, client):
        r = client.post("/api/rights/classify",
                        data=json.dumps({"text": "hello how are you"}),
                        content_type="application/json")
        assert r.status_code == 200
        body = r.get_json()
        assert body["intent"] == "none"

    def test_classify_false_positive(self, client):
        r = client.post("/api/rights/classify",
                        data=json.dumps({"text": "please delete the old report from the group"}),
                        content_type="application/json")
        assert r.status_code == 200
        body = r.get_json()
        assert body["intent"] == "none"


class TestRightsIntakeEndpoint:
    def test_intake_from_text(self, client):
        wa_text = (
            "20/10/26, 9:05 pm - Ramesh Kumar: Mera number aur details list se hata dijiye\n"
            "21/10/26, 11:30 am - Anita Reddy: can you send me what details you have about me\n"
            "23/10/26, 10:00 am - Deepa Bhat: please delete the old report from the group\n"
        )
        r = client.post("/api/rights/intake",
                        data=json.dumps({"text": wa_text}),
                        content_type="application/json")
        assert r.status_code == 200
        body = r.get_json()
        assert body["success"] is True
        assert body["created"] == 2  # Deepa Bhat is a false positive

    def test_intake_from_messages_list(self, client):
        msgs = [
            {"sender": "Test", "text": "stop sending me reminders", "timestamp": ""},
            {"sender": "Other", "text": "good morning", "timestamp": ""},
        ]
        r = client.post("/api/rights/intake",
                        data=json.dumps({"messages": msgs}),
                        content_type="application/json")
        assert r.status_code == 200
        body = r.get_json()
        assert body["created"] == 1

    def test_intake_empty_text(self, client):
        r = client.post("/api/rights/intake",
                        data=json.dumps({"text": ""}),
                        content_type="application/json")
        assert r.status_code == 200
        body = r.get_json()
        assert body["created"] == 0


class TestRightsListEndpoint:
    def test_list_empty(self, client):
        r = client.get("/api/rights/requests")
        assert r.status_code == 200
        body = r.get_json()
        assert body["requests"] == []

    def test_list_after_intake(self, client):
        client.post("/api/rights/intake",
                    data=json.dumps({"text": "20/10/26, 9:05 pm - X: delete my data please"}),
                    content_type="application/json")
        r = client.get("/api/rights/requests")
        assert r.status_code == 200
        body = r.get_json()
        assert body["total"] >= 1

    def test_filter_by_intent(self, client):
        client.post("/api/rights/intake",
                    data=json.dumps({"messages": [
                        {"sender": "A", "text": "delete my data", "timestamp": ""},
                        {"sender": "B", "text": "I want to complain about data breach", "timestamp": ""},
                    ]}),
                    content_type="application/json")
        r = client.get("/api/rights/requests?intent=complaint")
        body = r.get_json()
        assert all(req["intent"] == "complaint" for req in body["requests"])


class TestRightsDetailEndpoint:
    def test_detail_not_found(self, client):
        r = client.get("/api/rights/requests/9999")
        assert r.status_code == 404

    def test_detail_found(self, client):
        client.post("/api/rights/intake",
                    data=json.dumps({"messages": [
                        {"sender": "A", "text": "erase my details", "timestamp": ""},
                    ]}),
                    content_type="application/json")
        r = client.get("/api/rights/requests")
        req_id = r.get_json()["requests"][0]["id"]
        r2 = client.get(f"/api/rights/requests/{req_id}")
        assert r2.status_code == 200
        body = r2.get_json()
        assert body["id"] == req_id


class TestRightsApproveEndpoint:
    def test_approve_request(self, client):
        # Create a request first
        client.post("/api/rights/intake",
                    data=json.dumps({"messages": [
                        {"sender": "A", "text": "remove my number", "timestamp": ""},
                    ]}),
                    content_type="application/json")
        r = client.get("/api/rights/requests")
        req_id = r.get_json()["requests"][0]["id"]

        r2 = client.post(f"/api/rights/requests/{req_id}/approve")
        assert r2.status_code == 200
        body = r2.get_json()
        assert body["status"] == "approved"

    def test_approve_not_found(self, client):
        r = client.post("/api/rights/requests/9999/approve")
        assert r.status_code == 404

    def test_execute_requires_approved_status(self, client):
        # Create a request without approving
        client.post("/api/rights/intake",
                    data=json.dumps({"messages": [
                        {"sender": "A", "text": "delete my data", "timestamp": ""},
                    ]}),
                    content_type="application/json")
        r = client.get("/api/rights/requests")
        req_id = r.get_json()["requests"][0]["id"]

        r2 = client.post(f"/api/rights/requests/{req_id}/execute",
                         data=json.dumps({"confirm_hash": "abc123"}),
                         content_type="application/json")
        assert r2.status_code == 400
        assert "approved" in r2.get_json()["error"].lower()


class TestRightsDeskPageView:
    def test_rights_desk_page_renders(self, client):
        r = client.get("/rights-desk")
        assert r.status_code == 200
        html = r.data.decode("utf-8")
        assert "Rights Desk" in html
        assert "intake-textarea" in html
        assert "btn-load-demo" in html
        assert "btn-detect" in html
        assert "Not legal advice" in html
        assert "rd-empty-state" in html

    def test_rights_desk_in_nav(self, client):
        r = client.get("/dashboard")
        assert r.status_code == 200
        assert "Rights Desk" in r.data.decode("utf-8")


class TestRightsHinglishFullFlow:
    def test_hinglish_requester_full_acceptance_flow(self, client):
        # 1. Scan demo data
        scan_r = client.post("/api/scan-demo")
        assert scan_r.status_code == 200

        # 2. Get demo text
        demo_r = client.get("/api/rights/demo-text")
        assert demo_r.status_code == 200
        demo_text = demo_r.get_json()["text"]
        assert "Ramesh Kumar" in demo_text

        # 3. Detect requests via intake
        intake_r = client.post(
            "/api/rights/intake",
            data=json.dumps({"text": demo_text}),
            content_type="application/json"
        )
        assert intake_r.status_code == 200
        created = intake_r.get_json()["requests"]
        assert len(created) >= 1

        # Find Ramesh Kumar request (Hinglish erase)
        ramesh_req = next((req for req in created if req["intent"] == "erase" and req["resolution"] == "probable"), None)
        assert ramesh_req is not None
        req_id = ramesh_req["id"]
        assert ramesh_req["status"] == "identity_pending"

        # Check detail endpoint
        detail_r = client.get(f"/api/rights/{req_id}")
        assert detail_r.status_code == 200
        detail = detail_r.get_json()
        assert detail["countdown_seconds"] is not None
        assert len(detail["data_locations"]) > 0

        # 4. Confirm identity
        confirm_r = client.post(
            f"/api/rights/{req_id}/confirm-identity",
            data=json.dumps({"detail": "phone on file"}),
            content_type="application/json"
        )
        assert confirm_r.status_code == 200
        assert confirm_r.get_json()["status"] == "received"

        # 5. Build plan
        plan_r = client.post(f"/api/rights/requests/{req_id}/plan")
        assert plan_r.status_code == 200
        plan_data = plan_r.get_json()
        assert plan_data["success"] is True
        plan_hash = plan_data["plan_hash"]

        # Test plan override
        # Override billing.csv patient name or phone
        plan = plan_data["plan"]
        billing_records = plan["sources"].get("billing.csv", {}).get("records", {})
        if billing_records:
            first_rk = list(billing_records.keys())[0]
            first_field = list(billing_records[first_rk]["fields"].keys())[0]
            override_r = client.post(
                f"/api/rights/{req_id}/plan-override",
                data=json.dumps({
                    "record_key": first_rk,
                    "field": first_field,
                    "decision": "ERASE"
                }),
                content_type="application/json"
            )
            assert override_r.status_code == 200
            plan_hash = override_r.get_json()["plan_hash"]

        # 6. Approve plan
        app_r = client.post(f"/api/rights/requests/{req_id}/approve")
        assert app_r.status_code == 200
        assert app_r.get_json()["status"] == "approved"

        # 7. Execute erasure
        exec_r = client.post(
            f"/api/rights/requests/{req_id}/execute",
            data=json.dumps({"confirm_hash": plan_hash}),
            content_type="application/json"
        )
        assert exec_r.status_code == 200
        receipt = exec_r.get_json()["receipt"]
        assert receipt["request_id"] == req_id
        assert "action_counts" in receipt
        assert "retained_items" in receipt
        assert "residual_report" in receipt

        # 8. Receipt & Download
        receipt_r = client.get(f"/api/rights/{req_id}/receipt")
        assert receipt_r.status_code == 200

        download_r = client.get(f"/api/rights/{req_id}/download")
        assert download_r.status_code == 200
        assert download_r.mimetype == "application/zip"

