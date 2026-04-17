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

def _fake_adzuna(role, country, results_per_page=3, skills=None):
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


def test_search_jobs_forwards_candidate_skills_to_adzuna(jobs_handler, jobs_tables):
    """skillsToHighlight from the report are normalized and passed as the skills
    argument, so two candidates with the same role but different stacks see
    different listings."""
    _seed_result(jobs_tables["results"],
                 skills_to_develop=["K8s"],
                 top_roles=[{"title": "Backend Engineer", "match_percentage": 80,
                             "resume_gaps": []}])
    jobs_tables["results"].update_item(
        Key={"userId": USER, "resultId": RESULT_ID},
        UpdateExpression="SET skillsToHighlight = :s",
        ExpressionAttributeValues={":s": [
            "Python — core language", "AWS Lambda: serverless",
            "React", "GraphQL (schema design)",
        ]},
    )

    captured_skills = {}

    def fake(role, country, results_per_page=3, skills=None):
        captured_skills["value"] = skills
        return []

    with patch.object(jobs_handler, "adzuna_search", side_effect=fake):
        jobs_handler.api_handler(
            _event("POST", "/jobs/search", body={"resultId": RESULT_ID}), None,
        )

    # Short names only (stripped), and at most 4 of them.
    assert captured_skills["value"] == ["Python", "AWS Lambda", "React", "GraphQL"]


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


def test_create_tailored_resume_prefers_stored_resume_text(jobs_handler, jobs_tables):
    """When the result has resumeText stored, that's fed to Bedrock — not the
    reconstructed blob the frontend sends. This ensures the candidate's real
    name + contact reaches the tailored resume."""
    # Seed a result with stored parsed text
    jobs_tables["results"].put_item(Item={
        "userId": USER, "resultId": RESULT_ID, "uploadId": "up-1",
        "topRoles": [{"title": "Senior Backend Engineer", "match_percentage": 88,
                       "resume_gaps": []}],
        "skillsToDevelop": [],
        "resumeText": "Jane Doe · jane@example.com · +1-555-0100\nStaff Engineer, Acme",
    })
    _seed_job(jobs_tables["jobs"])

    captured = {}

    def fake_tailor(resume_text, job_description, target_words):
        captured["text"] = resume_text
        return "# Jane Doe\nTailored."

    with patch.object(jobs_handler, "invoke_bedrock_tailor", side_effect=fake_tailor):
        resp = jobs_handler.api_handler(
            _event("POST", "/jobs/{jobId}/tailored-resume",
                   path_params={"jobId": "job-1"},
                   body={"resumeText": "RECONSTRUCTED SHORT BLOB"}),
            None,
        )

    assert resp["statusCode"] == 200
    # Bedrock got the real parsed text — with name + email — not the fallback
    assert "Jane Doe" in captured["text"]
    assert "jane@example.com" in captured["text"]


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


def test_short_skill_name_strips_prose(jobs_handler):
    cases = [
        ("Kubernetes — To stand out for platform roles you need…", "Kubernetes"),
        ("Machine Learning: prose prose prose", "Machine Learning"),
        ("Rust. A modern systems language…", "Rust"),
        ("SQL (standard dialect)", "SQL"),
        ("   GraphQL   ", "GraphQL"),
        ("", ""),
        ("A" * 80, "A" * 40),
    ]
    for raw, expected in cases:
        assert jobs_handler._short_skill_name(raw) == expected, raw


def test_infer_missing_skills_returns_short_names(jobs_handler):
    job = {"description": "We use kubernetes and graphql daily."}
    develop = [
        "Kubernetes — you need this for platform roles",
        "Rust. A modern systems language",
        "GraphQL (schema design)",
    ]
    result = jobs_handler._infer_missing_skills(job, develop)
    # kubernetes + graphql match JD; rust does not. Short names returned.
    assert result == ["Kubernetes", "GraphQL"]


def test_infer_missing_skills_falls_back_to_first_three(jobs_handler):
    job = {"description": "Purely XYZ content here."}
    develop = ["Kubernetes — why", "Rust: why", "GraphQL. why", "Spark"]
    result = jobs_handler._infer_missing_skills(job, develop)
    assert result == ["Kubernetes", "Rust", "GraphQL"]


def test_validate_latex_accepts_well_formed(jobs_handler):
    tex = (
        r"\documentclass{article}"
        "\n" r"\begin{document}" "\nHello\n" r"\end{document}"
    )
    jobs_handler.validate_latex(tex)


def test_validate_latex_rejects_missing_documentclass(jobs_handler):
    import pytest
    with pytest.raises(ValueError):
        jobs_handler.validate_latex(r"\begin{document}Hello\end{document}")


def test_validate_latex_rejects_unbalanced_environments(jobs_handler):
    import pytest
    tex = r"\documentclass{article}" + "\n" + r"\begin{document}" + "\n" + r"\begin{itemize}" + "\n" + r"\end{document}"
    with pytest.raises(ValueError):
        jobs_handler.validate_latex(tex)


def test_create_tailored_resume_latex_default_template(jobs_handler, jobs_tables):
    _seed_result(jobs_tables["results"])
    _seed_job(jobs_tables["jobs"])

    # A minimal but valid LaTeX output that Bedrock might produce
    fake_tex = (
        r"\documentclass[letterpaper,11pt]{article}"
        "\n" r"\begin{document}"
        "\n" r"\section{Experience}" "\nTailored content" "\n"
        r"\end{document}"
    )
    with patch.object(jobs_handler, "invoke_bedrock_tailor_latex",
                      return_value=fake_tex) as mock_latex, \
         patch.object(jobs_handler, "invoke_bedrock_tailor") as mock_md:
        resp = jobs_handler.api_handler(
            _event("POST", "/jobs/{jobId}/tailored-resume",
                   path_params={"jobId": "job-1"},
                   body={"resumeText": "Original resume text", "format": "latex"}),
            None,
        )
        mock_latex.assert_called_once()
        mock_md.assert_not_called()
        # Called with the default template (non-empty 4th arg)
        assert jobs_handler.DEFAULT_LATEX_TEMPLATE in mock_latex.call_args.args \
               or len(mock_latex.call_args.args[3]) > 500

    body = json.loads(resp["body"])
    assert resp["statusCode"] == 200
    assert body["format"] == "latex"
    assert body["markdown"].startswith(r"\documentclass")


def test_create_tailored_resume_latex_user_template(jobs_handler, jobs_tables):
    _seed_result(jobs_tables["results"])
    _seed_job(jobs_tables["jobs"])

    user_template = r"\documentclass{article}" + "\n" + r"\begin{document}" + "\nUSER TEMPLATE\n" + r"\end{document}"
    fake_tex = r"\documentclass{article}" + "\n" + r"\begin{document}" + "\nTailored\n" + r"\end{document}"

    with patch.object(jobs_handler, "invoke_bedrock_tailor_latex", return_value=fake_tex) as mock_latex:
        resp = jobs_handler.api_handler(
            _event("POST", "/jobs/{jobId}/tailored-resume",
                   path_params={"jobId": "job-1"},
                   body={"resumeText": "Resume", "format": "latex", "referenceLatex": user_template}),
            None,
        )
        # User template was passed through (not the default)
        assert mock_latex.call_args.args[3] == user_template

    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["format"] == "latex"


def test_create_tailored_resume_caches_per_format(jobs_handler, jobs_tables):
    """A user can generate both a markdown and a latex version for the same job."""
    _seed_result(jobs_tables["results"])
    _seed_job(jobs_tables["jobs"])

    with patch.object(jobs_handler, "invoke_bedrock_tailor", return_value="# Markdown"), \
         patch.object(jobs_handler, "invoke_bedrock_tailor_latex",
                      return_value=r"\documentclass{article}" + "\n" + r"\begin{document}" + "\nTex\n" + r"\end{document}"):
        md_resp = jobs_handler.api_handler(
            _event("POST", "/jobs/{jobId}/tailored-resume",
                   path_params={"jobId": "job-1"},
                   body={"resumeText": "R", "format": "markdown"}),
            None,
        )
        latex_resp = jobs_handler.api_handler(
            _event("POST", "/jobs/{jobId}/tailored-resume",
                   path_params={"jobId": "job-1"},
                   body={"resumeText": "R", "format": "latex"}),
            None,
        )
    md_body = json.loads(md_resp["body"])
    latex_body = json.loads(latex_resp["body"])
    assert md_body["resumeId"] != latex_body["resumeId"]
    assert md_body["format"] == "markdown"
    assert latex_body["format"] == "latex"


def test_create_tailored_resume_rejects_invalid_format(jobs_handler, jobs_tables):
    _seed_result(jobs_tables["results"])
    _seed_job(jobs_tables["jobs"])
    resp = jobs_handler.api_handler(
        _event("POST", "/jobs/{jobId}/tailored-resume",
               path_params={"jobId": "job-1"},
               body={"resumeText": "R", "format": "pdf"}),
        None,
    )
    assert resp["statusCode"] == 400


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
