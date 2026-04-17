"""Tests for the jobs_service Lambda handler."""
import json
from unittest.mock import patch


USER = "user-a"
OTHER_USER = "user-b"
RESULT_ID = "res-1"


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


def _seed_result(results_table, top_roles=None, skills_to_develop=None):
    results_table.put_item(Item={
        "userId": USER,
        "resultId": RESULT_ID,
        "uploadId": "up-1",
        "topRoles": top_roles or [
            {"title": "Senior Backend Engineer", "match_percentage": 88,
             "resume_gaps": ["distributed systems", "kafka"]},
            {"title": "Platform Engineer", "match_percentage": 80,
             "resume_gaps": ["kubernetes"]},
        ],
        "skillsToDevelop": skills_to_develop or ["Rust", "Kubernetes"],
    })


# ── Auth ──────────────────────────────────────────────────────────────────────

def test_unauthorized_returns_401(jobs_handler):
    evt = _event("GET", "/jobs", user="")
    resp = jobs_handler.api_handler(evt, None)
    assert resp["statusCode"] == 401


# ── /jobs/search ──────────────────────────────────────────────────────────────

def _fake_adzuna(role, country, results_per_page=3):
    return [
        {
            "title": f"{role} at Acme",
            "company": {"display_name": "Acme"},
            "location": {"display_name": "Remote"},
            "description": "Build distributed systems with kubernetes and python.",
            "redirect_url": "https://acme.example/job/1",
            "salary_min": 150000, "salary_max": 200000,
            "created": "2026-04-10T00:00:00Z",
        },
        {
            "title": f"{role} at Globex",
            "company": {"display_name": "Globex"},
            "location": {"display_name": "New York"},
            "description": "Senior role requiring Go, kafka, and rust expertise.",
            "redirect_url": "https://globex.example/job/2",
            "salary_min": None, "salary_max": None,
            "created": "2026-04-09T00:00:00Z",
        },
    ]


def test_search_jobs_populates_table(jobs_handler, jobs_tables):
    _seed_result(jobs_tables["results"])

    with patch.object(jobs_handler, "adzuna_search", side_effect=_fake_adzuna):
        resp = jobs_handler.api_handler(
            _event("POST", "/jobs/search", body={"resultId": RESULT_ID, "country": "us"}),
            None,
        )

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["cached"] is False
    # 2 roles × 2 jobs = 4 items
    assert len(body["jobs"]) == 4
    # Each item is scoped to the user + result
    for j in body["jobs"]:
        assert j["userId"] == USER
        assert j["resultId"] == RESULT_ID
        assert j["roleTitle"] in {"Senior Backend Engineer", "Platform Engineer"}


def test_search_jobs_returns_cached_on_repeat(jobs_handler, jobs_tables):
    _seed_result(jobs_tables["results"])

    with patch.object(jobs_handler, "adzuna_search", side_effect=_fake_adzuna):
        jobs_handler.api_handler(
            _event("POST", "/jobs/search", body={"resultId": RESULT_ID}), None,
        )

    with patch.object(jobs_handler, "adzuna_search") as mock_fn:
        resp = jobs_handler.api_handler(
            _event("POST", "/jobs/search", body={"resultId": RESULT_ID}), None,
        )
        mock_fn.assert_not_called()

    body = json.loads(resp["body"])
    assert body["cached"] is True
    assert len(body["jobs"]) == 4


def test_search_jobs_forbids_other_users_result(jobs_handler, jobs_tables):
    _seed_result(jobs_tables["results"])
    resp = jobs_handler.api_handler(
        _event("POST", "/jobs/search", user=OTHER_USER,
               body={"resultId": RESULT_ID}),
        None,
    )
    assert resp["statusCode"] == 404


def test_search_jobs_requires_resultId(jobs_handler):
    resp = jobs_handler.api_handler(_event("POST", "/jobs/search", body={}), None)
    assert resp["statusCode"] == 400


# ── /jobs list + get ──────────────────────────────────────────────────────────

def test_list_jobs_filters_by_user(jobs_handler, jobs_tables):
    _seed_result(jobs_tables["results"])
    with patch.object(jobs_handler, "adzuna_search", side_effect=_fake_adzuna):
        jobs_handler.api_handler(
            _event("POST", "/jobs/search", body={"resultId": RESULT_ID}), None,
        )
    resp = jobs_handler.api_handler(
        _event("GET", "/jobs", query={"resultId": RESULT_ID}), None,
    )
    body = json.loads(resp["body"])
    assert resp["statusCode"] == 200
    assert len(body["jobs"]) == 4

    # Other user should see none
    resp = jobs_handler.api_handler(
        _event("GET", "/jobs", user=OTHER_USER, query={"resultId": RESULT_ID}), None,
    )
    assert len(json.loads(resp["body"])["jobs"]) == 0


def test_get_job_forbids_cross_user(jobs_handler, jobs_tables):
    _seed_result(jobs_tables["results"])
    with patch.object(jobs_handler, "adzuna_search", side_effect=_fake_adzuna):
        jobs_handler.api_handler(
            _event("POST", "/jobs/search", body={"resultId": RESULT_ID}), None,
        )
    job = next(iter(jobs_tables["jobs"].scan()["Items"]))
    resp = jobs_handler.api_handler(
        _event("GET", "/jobs/{jobId}", user=OTHER_USER,
               path_params={"jobId": job["jobId"]}),
        None,
    )
    assert resp["statusCode"] == 403


# ── Courses ───────────────────────────────────────────────────────────────────

def test_fetch_courses_uses_tavily_and_caches(jobs_handler, jobs_tables):
    _seed_result(jobs_tables["results"])
    with patch.object(jobs_handler, "adzuna_search", side_effect=_fake_adzuna):
        jobs_handler.api_handler(
            _event("POST", "/jobs/search", body={"resultId": RESULT_ID}), None,
        )
    job = next(iter(jobs_tables["jobs"].scan()["Items"]))

    fake_results = [
        {"title": "Kubernetes for Developers", "url": "https://coursera.org/k8s", "snippet": "Learn k8s"},
    ]
    with patch.object(jobs_handler, "tavily_search", return_value=fake_results) as mock_tv:
        resp = jobs_handler.api_handler(
            _event("POST", "/jobs/{jobId}/courses",
                   path_params={"jobId": job["jobId"]}),
            None,
        )
    body = json.loads(resp["body"])
    assert resp["statusCode"] == 200
    assert body["cached"] is False
    assert len(body["courses"]) >= 1
    assert body["courses"][0]["recommendations"][0]["url"] == "https://coursera.org/k8s"

    # Second call should be cached (no Tavily hit)
    with patch.object(jobs_handler, "tavily_search") as mock_tv2:
        resp2 = jobs_handler.api_handler(
            _event("POST", "/jobs/{jobId}/courses",
                   path_params={"jobId": job["jobId"]}),
            None,
        )
        mock_tv2.assert_not_called()
    assert json.loads(resp2["body"])["cached"] is True


# ── Tailored resume create / read / update ────────────────────────────────────

def _seed_job(jobs_table, description="A JD mentioning rust and kubernetes."):
    jobs_table.put_item(Item={
        "jobId": "job-1", "userId": USER, "resultId": RESULT_ID,
        "title": "Senior Backend Engineer", "company": "Acme", "location": "Remote",
        "description": description, "roleTitle": "Senior Backend Engineer",
        "resumeGaps": ["distributed systems"],
    })


def test_create_tailored_resume_happy_path(jobs_handler, jobs_tables):
    _seed_result(jobs_tables["results"])
    _seed_job(jobs_tables["jobs"])

    with patch.object(jobs_handler, "invoke_bedrock_tailor",
                      return_value="# Jane Doe\n\nSenior engineer tailored for Acme."):
        resp = jobs_handler.api_handler(
            _event("POST", "/jobs/{jobId}/tailored-resume",
                   path_params={"jobId": "job-1"},
                   body={"resumeText": "Original resume text " * 40}),
            None,
        )
    body = json.loads(resp["body"])
    assert resp["statusCode"] == 200
    assert body["markdown"].startswith("# Jane Doe")
    assert body["userId"] == USER
    assert body["jobId"] == "job-1"
    assert body["wordCount"] > 0


def test_create_tailored_resume_reuses_existing(jobs_handler, jobs_tables):
    _seed_result(jobs_tables["results"])
    _seed_job(jobs_tables["jobs"])

    with patch.object(jobs_handler, "invoke_bedrock_tailor",
                      return_value="# Generated once") as mock_tailor:
        first = jobs_handler.api_handler(
            _event("POST", "/jobs/{jobId}/tailored-resume",
                   path_params={"jobId": "job-1"},
                   body={"resumeText": "Original"}),
            None,
        )
        second = jobs_handler.api_handler(
            _event("POST", "/jobs/{jobId}/tailored-resume",
                   path_params={"jobId": "job-1"},
                   body={"resumeText": "Original"}),
            None,
        )
        assert mock_tailor.call_count == 1

    assert json.loads(first["body"])["resumeId"] == json.loads(second["body"])["resumeId"]


def test_save_tailored_resume_updates_markdown(jobs_handler, jobs_tables):
    _seed_result(jobs_tables["results"])
    _seed_job(jobs_tables["jobs"])

    with patch.object(jobs_handler, "invoke_bedrock_tailor",
                      return_value="# Initial"):
        create = jobs_handler.api_handler(
            _event("POST", "/jobs/{jobId}/tailored-resume",
                   path_params={"jobId": "job-1"},
                   body={"resumeText": "Original"}),
            None,
        )
    resume_id = json.loads(create["body"])["resumeId"]

    updated = jobs_handler.api_handler(
        _event("PUT", "/tailored-resumes/{resumeId}",
               path_params={"resumeId": resume_id},
               body={"markdown": "# Edited by user\n\nnew content"}),
        None,
    )
    body = json.loads(updated["body"])
    assert updated["statusCode"] == 200
    assert body["markdown"].startswith("# Edited by user")
    assert body["updatedAt"] >= body["createdAt"]


def test_get_tailored_resume_forbids_other_user(jobs_handler, jobs_tables):
    _seed_result(jobs_tables["results"])
    _seed_job(jobs_tables["jobs"])

    with patch.object(jobs_handler, "invoke_bedrock_tailor", return_value="# R"):
        create = jobs_handler.api_handler(
            _event("POST", "/jobs/{jobId}/tailored-resume",
                   path_params={"jobId": "job-1"},
                   body={"resumeText": "Original"}),
            None,
        )
    resume_id = json.loads(create["body"])["resumeId"]

    resp = jobs_handler.api_handler(
        _event("GET", "/tailored-resumes/{resumeId}",
               user=OTHER_USER,
               path_params={"resumeId": resume_id}),
        None,
    )
    assert resp["statusCode"] == 403
