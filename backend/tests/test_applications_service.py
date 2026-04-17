"""Tests for the applications_service Lambda handler."""
import json


USER = "user-a"
OTHER_USER = "user-b"


def _event(method, path, user=USER, path_params=None, query=None, body=None):
    return {
        "httpMethod": method,
        "resource": path,
        "path": path,
        "pathParameters": path_params or {},
        "queryStringParameters": query,
        "body": json.dumps(body) if body is not None else None,
        "requestContext": {"authorizer": {"claims": {"sub": user}}},
    }


def _create_app(h, user=USER, **overrides):
    body = {
        "company": "Acme",
        "jobTitle": "Senior Backend Engineer",
        "location": "Remote",
        "status": "Wishlist",
        **overrides,
    }
    resp = h.api_handler(_event("POST", "/applications", user=user, body=body), None)
    assert resp["statusCode"] == 201
    return json.loads(resp["body"])


# ── Auth ──────────────────────────────────────────────────────────────────────

def test_unauthorized_returns_401(applications_handler):
    resp = applications_handler.api_handler(_event("GET", "/applications", user=""), None)
    assert resp["statusCode"] == 401


def test_unknown_route_returns_404(applications_handler):
    resp = applications_handler.api_handler(_event("GET", "/nope"), None)
    assert resp["statusCode"] == 404


# ── Create ────────────────────────────────────────────────────────────────────

def test_create_happy_path_sets_history_and_rounds(applications_handler):
    app = _create_app(applications_handler)
    assert app["userId"] == USER
    assert app["status"] == "Wishlist"
    assert app["interviewRounds"] == []
    assert len(app["statusHistory"]) == 1
    assert app["statusHistory"][0]["status"] == "Wishlist"


def test_create_rejects_missing_required(applications_handler):
    resp = applications_handler.api_handler(
        _event("POST", "/applications", body={"company": "Acme"}),
        None,
    )
    assert resp["statusCode"] == 400


def test_create_rejects_invalid_status(applications_handler):
    resp = applications_handler.api_handler(
        _event("POST", "/applications",
               body={"company": "X", "jobTitle": "Y", "status": "Maybe"}),
        None,
    )
    assert resp["statusCode"] == 400


def test_create_applied_sets_appliedAt(applications_handler):
    app = _create_app(applications_handler, status="Applied")
    assert app["appliedAt"]


# ── Read ──────────────────────────────────────────────────────────────────────

def test_list_returns_only_own_applications(applications_handler):
    _create_app(applications_handler, user=USER, company="A")
    _create_app(applications_handler, user=USER, company="B")
    _create_app(applications_handler, user=OTHER_USER, company="C")

    resp = applications_handler.api_handler(_event("GET", "/applications"), None)
    body = json.loads(resp["body"])
    companies = sorted(a["company"] for a in body["applications"])
    assert companies == ["A", "B"]


def test_list_filters_by_status(applications_handler):
    _create_app(applications_handler, company="A", status="Applied")
    _create_app(applications_handler, company="B", status="Wishlist")

    resp = applications_handler.api_handler(
        _event("GET", "/applications", query={"status": "Applied"}), None,
    )
    items = json.loads(resp["body"])["applications"]
    assert len(items) == 1
    assert items[0]["company"] == "A"


def test_list_rejects_invalid_status_filter(applications_handler):
    resp = applications_handler.api_handler(
        _event("GET", "/applications", query={"status": "Bogus"}), None,
    )
    assert resp["statusCode"] == 400


def test_get_forbids_cross_user_access(applications_handler):
    app = _create_app(applications_handler, user=USER)
    resp = applications_handler.api_handler(
        _event("GET", "/applications/{applicationId}",
               user=OTHER_USER,
               path_params={"applicationId": app["applicationId"]}),
        None,
    )
    assert resp["statusCode"] == 403


def test_get_returns_404_for_unknown_id(applications_handler):
    resp = applications_handler.api_handler(
        _event("GET", "/applications/{applicationId}",
               path_params={"applicationId": "nope"}),
        None,
    )
    assert resp["statusCode"] == 404


# ── Update ────────────────────────────────────────────────────────────────────

def test_patch_updates_fields(applications_handler):
    app = _create_app(applications_handler)
    resp = applications_handler.api_handler(
        _event("PATCH", "/applications/{applicationId}",
               path_params={"applicationId": app["applicationId"]},
               body={"notes": "Heard back from recruiter", "nextAction": "Send thank-you"}),
        None,
    )
    updated = json.loads(resp["body"])
    assert updated["notes"] == "Heard back from recruiter"
    assert updated["nextAction"] == "Send thank-you"
    assert updated["updatedAt"] > app["updatedAt"]


def test_patch_status_change_appends_history(applications_handler):
    app = _create_app(applications_handler)
    assert len(app["statusHistory"]) == 1
    resp = applications_handler.api_handler(
        _event("PATCH", "/applications/{applicationId}",
               path_params={"applicationId": app["applicationId"]},
               body={"status": "Applied", "statusNote": "Submitted via LinkedIn"}),
        None,
    )
    updated = json.loads(resp["body"])
    assert updated["status"] == "Applied"
    assert updated["appliedAt"]
    assert len(updated["statusHistory"]) == 2
    assert updated["statusHistory"][-1]["status"] == "Applied"
    assert updated["statusHistory"][-1]["note"] == "Submitted via LinkedIn"


def test_patch_same_status_does_not_duplicate_history(applications_handler):
    app = _create_app(applications_handler, status="Applied")
    resp = applications_handler.api_handler(
        _event("PATCH", "/applications/{applicationId}",
               path_params={"applicationId": app["applicationId"]},
               body={"status": "Applied", "notes": "still applied"}),
        None,
    )
    updated = json.loads(resp["body"])
    assert len(updated["statusHistory"]) == len(app["statusHistory"])


def test_patch_forbids_other_user(applications_handler):
    app = _create_app(applications_handler, user=USER)
    resp = applications_handler.api_handler(
        _event("PATCH", "/applications/{applicationId}",
               user=OTHER_USER,
               path_params={"applicationId": app["applicationId"]},
               body={"notes": "stolen"}),
        None,
    )
    assert resp["statusCode"] == 403


def test_patch_rejects_invalid_status(applications_handler):
    app = _create_app(applications_handler)
    resp = applications_handler.api_handler(
        _event("PATCH", "/applications/{applicationId}",
               path_params={"applicationId": app["applicationId"]},
               body={"status": "Maybe"}),
        None,
    )
    assert resp["statusCode"] == 400


# ── Delete ────────────────────────────────────────────────────────────────────

def test_delete_removes_application(applications_handler):
    app = _create_app(applications_handler)
    resp = applications_handler.api_handler(
        _event("DELETE", "/applications/{applicationId}",
               path_params={"applicationId": app["applicationId"]}),
        None,
    )
    assert resp["statusCode"] == 200

    resp = applications_handler.api_handler(
        _event("GET", "/applications/{applicationId}",
               path_params={"applicationId": app["applicationId"]}),
        None,
    )
    assert resp["statusCode"] == 404


def test_delete_forbids_other_user(applications_handler):
    app = _create_app(applications_handler, user=USER)
    resp = applications_handler.api_handler(
        _event("DELETE", "/applications/{applicationId}",
               user=OTHER_USER,
               path_params={"applicationId": app["applicationId"]}),
        None,
    )
    assert resp["statusCode"] == 403


# ── Interview rounds ──────────────────────────────────────────────────────────

def test_add_round_appends(applications_handler):
    app = _create_app(applications_handler)
    resp = applications_handler.api_handler(
        _event("POST", "/applications/{applicationId}/rounds",
               path_params={"applicationId": app["applicationId"]},
               body={
                   "roundName": "Phone Screen",
                   "scheduledAt": "2026-04-25T14:00:00Z",
                   "interviewer": "Jane Smith",
                   "notes": "30 min call",
               }),
        None,
    )
    body = json.loads(resp["body"])
    assert resp["statusCode"] == 201
    assert len(body["interviewRounds"]) == 1
    r = body["interviewRounds"][0]
    assert r["roundName"] == "Phone Screen"
    assert r["outcome"] == "PENDING"
    assert r["roundId"]


def test_add_round_requires_name(applications_handler):
    app = _create_app(applications_handler)
    resp = applications_handler.api_handler(
        _event("POST", "/applications/{applicationId}/rounds",
               path_params={"applicationId": app["applicationId"]},
               body={}),
        None,
    )
    assert resp["statusCode"] == 400


def test_update_round_merges_fields(applications_handler):
    app = _create_app(applications_handler)
    add = applications_handler.api_handler(
        _event("POST", "/applications/{applicationId}/rounds",
               path_params={"applicationId": app["applicationId"]},
               body={"roundName": "Tech Screen"}),
        None,
    )
    round_id = json.loads(add["body"])["interviewRounds"][0]["roundId"]

    resp = applications_handler.api_handler(
        _event("PATCH", "/applications/{applicationId}/rounds/{roundId}",
               path_params={"applicationId": app["applicationId"], "roundId": round_id},
               body={"outcome": "PASSED", "notes": "solid candidate"}),
        None,
    )
    body = json.loads(resp["body"])
    r = body["interviewRounds"][0]
    assert r["outcome"] == "PASSED"
    assert r["notes"] == "solid candidate"
    assert r["roundName"] == "Tech Screen"  # preserved


def test_update_round_rejects_bad_outcome(applications_handler):
    app = _create_app(applications_handler)
    add = applications_handler.api_handler(
        _event("POST", "/applications/{applicationId}/rounds",
               path_params={"applicationId": app["applicationId"]},
               body={"roundName": "X"}),
        None,
    )
    round_id = json.loads(add["body"])["interviewRounds"][0]["roundId"]

    resp = applications_handler.api_handler(
        _event("PATCH", "/applications/{applicationId}/rounds/{roundId}",
               path_params={"applicationId": app["applicationId"], "roundId": round_id},
               body={"outcome": "MAYBE"}),
        None,
    )
    assert resp["statusCode"] == 400


def test_delete_round_removes_and_404s_on_unknown(applications_handler):
    app = _create_app(applications_handler)
    add = applications_handler.api_handler(
        _event("POST", "/applications/{applicationId}/rounds",
               path_params={"applicationId": app["applicationId"]},
               body={"roundName": "R1"}),
        None,
    )
    round_id = json.loads(add["body"])["interviewRounds"][0]["roundId"]

    resp = applications_handler.api_handler(
        _event("DELETE", "/applications/{applicationId}/rounds/{roundId}",
               path_params={"applicationId": app["applicationId"], "roundId": round_id}),
        None,
    )
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["interviewRounds"] == []

    resp = applications_handler.api_handler(
        _event("DELETE", "/applications/{applicationId}/rounds/{roundId}",
               path_params={"applicationId": app["applicationId"], "roundId": "nope"}),
        None,
    )
    assert resp["statusCode"] == 404


# ── Stats ─────────────────────────────────────────────────────────────────────

def test_stats_aggregates_counts_and_rates(applications_handler):
    _create_app(applications_handler, company="A", status="Applied")
    _create_app(applications_handler, company="B", status="Applied")
    _create_app(applications_handler, company="C", status="Phone Screen")
    _create_app(applications_handler, company="D", status="Offer")
    _create_app(applications_handler, company="E", status="Rejected")
    _create_app(applications_handler, company="F", status="Wishlist")

    resp = applications_handler.api_handler(_event("GET", "/applications/stats"), None)
    body = json.loads(resp["body"])
    assert body["total"] == 6
    # Active = Applied + Phone Screen + Technical + Onsite
    assert body["active"] == 3
    # Response rate = responded / (active + offer + rejected) = 2 / 5 = 0.4
    assert body["responseRate"] == 0.4
    # Offer rate = 1 / 5 = 0.2
    assert body["offerRate"] == 0.2
    assert body["byStatus"]["Offer"] == 1


def test_stats_returns_zeros_for_empty(applications_handler):
    resp = applications_handler.api_handler(_event("GET", "/applications/stats"), None)
    body = json.loads(resp["body"])
    assert body["total"] == 0
    assert body["active"] == 0
    assert body["responseRate"] == 0.0
    assert body["offerRate"] == 0.0
