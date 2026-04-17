"""
Jobs Service — HTTP API.

Endpoints:
  GET  /jobs?resultId=...                 list cached jobs for a report
  POST /jobs/search                       fetch live jobs via Adzuna for the top roles
  GET  /jobs/{jobId}                      single job detail
  POST /jobs/{jobId}/courses              fetch course recommendations (Tavily)
  POST /jobs/{jobId}/tailored-resume      generate a JD-tailored resume (Bedrock)
  GET  /tailored-resumes/{resumeId}       fetch saved tailored resume
  PUT  /tailored-resumes/{resumeId}       save user edits
"""
import json
import os
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Optional

import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

JOBS_TABLE = dynamodb.Table(os.environ["JOBS_TABLE_NAME"])
TAILORED_RESUMES_TABLE = dynamodb.Table(os.environ["TAILORED_RESUMES_TABLE_NAME"])
RESULTS_TABLE = dynamodb.Table(os.environ["RESULTS_TABLE_NAME"])

ADZUNA_APP_ID = os.environ.get("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY", "")
ADZUNA_COUNTRY = os.environ.get("ADZUNA_COUNTRY", "us")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
MAX_TOKENS = int(os.environ.get("BEDROCK_MAX_TOKENS", "4096"))

JOBS_PER_ROLE = 3

VALID_FORMATS = {"markdown", "latex"}

_LATEX_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "default_resume.tex")


def _load_default_latex_template() -> str:
    """Load the bundled Jake Gutierrez template. Cached after first read."""
    try:
        with open(_LATEX_TEMPLATE_PATH, "r") as fh:
            return fh.read()
    except OSError:
        return ""


DEFAULT_LATEX_TEMPLATE = _load_default_latex_template()


# ── Response helpers ──────────────────────────────────────────────────────────

def respond(status_code: int, body) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "OPTIONS,GET,POST,PUT,DELETE",
            "Content-Type": "application/json",
        },
        "body": json.dumps(body, default=str),
    }


def get_user_id(event: dict) -> str:
    return event.get("requestContext", {}).get("authorizer", {}).get("claims", {}).get("sub", "")


def parse_body(event: dict) -> dict:
    raw = event.get("body") or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


# ── External integrations ─────────────────────────────────────────────────────

def adzuna_search(role_title: str, country: str, results_per_page: int = JOBS_PER_ROLE,
                  skills: Optional[list] = None) -> list:
    """Query Adzuna for up to results_per_page listings for role_title.

    If skills are provided, they're passed as what_or to surface listings that match the
    candidate's actual expertise (not just the generic role title). This is what makes
    the job feed differ between two users targeting the same role.
    Returns [] on any failure.
    """
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        print("Adzuna credentials not configured — skipping live job fetch")
        return []
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "what": role_title,
        "results_per_page": str(results_per_page),
        "content-type": "application/json",
    }
    if skills:
        # Adzuna accepts what_or=space-separated; we keep it short to avoid overly narrow results.
        clean = [s.strip() for s in skills[:4] if s and s.strip()]
        if clean:
            params["what_or"] = " ".join(clean)
    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"Adzuna request failed for role '{role_title}': {e}")
        return []
    return data.get("results", [])


def tavily_search(query: str, max_results: int = 3) -> list:
    """Run a Tavily search and return a list of {title, url, snippet} results."""
    if not TAVILY_API_KEY:
        return []
    payload = json.dumps({
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
        "include_answer": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"Tavily request failed for query '{query}': {e}")
        return []
    out = []
    for r in data.get("results", [])[:max_results]:
        out.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": (r.get("content", "") or "")[:240],
        })
    return out


TAILOR_PROMPT = """You are a professional resume writer. Rewrite the candidate's resume below so it targets the specific job description that follows.

Guidelines — follow strictly:
- Output a single-page resume in Markdown (no code fences, no commentary).
- Aim for roughly {target_words} words total. Do not exceed {max_words}.
- Preserve the candidate's factual history (companies, titles, dates, degrees). Do not invent experience.
- Reorder, rephrase, and re-emphasize content so the strongest match to the JD is most visible.
- Mirror the vocabulary of the job description where the candidate legitimately has that experience.
- Keep the same section structure the candidate already uses (e.g. Summary, Experience, Skills, Education, Projects) unless a section adds no value for this role.
- Quantify achievements where the original suggests impact; do not fabricate numbers.

Original resume:
---
{resume_text}
---

Target job description:
---
{job_description}
---

Return only the markdown resume."""


TAILOR_PROMPT_LATEX = r"""You are editing a LaTeX resume file to target a specific job. Your goal is to produce a complete, compilable .tex document that preserves the template's EXACT layout while tailoring the content to the job description.

HARD RULES — breaking any of these invalidates the output:
1. Preserve the ENTIRE preamble (everything before \begin{{document}}) byte-for-byte. Do not change packages, margins, custom commands, \newcommand definitions, \titleformat, or any style directives.
2. Preserve every \documentclass, \usepackage, \newcommand, \begin{{...}}, \end{{...}}, \section{{...}}, \resumeSubHeadingListStart/End, \resumeItemListStart/End.
3. Only edit text that is visible content: bullet strings inside \resumeItem{{...}}, role titles inside \resumeSubheading{{}}{{}}{{}}{{}}, project names inside \resumeProjectHeading{{}}{{}}, skill lists, and the header (name, contact links).
4. Never fabricate companies, dates, or degrees. Use the candidate's real history from their resume text below. If the reference template has placeholder companies (e.g. "Company Name", "State University"), REPLACE them with the candidate's real data.
5. LaTeX escape rules inside text content: use \% for %, \& for &, \_ for _, \$ for $, \# for #, \textbackslash{{}} for literal backslash. Never escape inside commands or macros.
6. The output MUST begin with \documentclass and end with \end{{document}}.
7. Keep the resume to one page — target total body content around {target_words} words. Trim or add experience bullets as needed.
8. Tailor wording of bullets to echo the JD's language where the candidate legitimately has that experience. Do not invent skills.
9. Do NOT wrap the output in code fences. Do NOT include commentary, apology, or explanation. Output ONLY the raw .tex file content.

CANDIDATE'S EXISTING RESUME (plain text, use this for factual content):
---
{resume_text}
---

TARGET JOB DESCRIPTION:
---
{job_description}
---

REFERENCE LATEX TEMPLATE (preserve its structure exactly; fill with candidate's real content):
---
{latex_template}
---

Return the complete tailored .tex file, starting with \documentclass and ending with \end{{document}}."""


def _strip_code_fences(text: str) -> str:
    """Remove leading/trailing ```lang fences if Bedrock wrapped output in them."""
    text = text.strip()
    if not text.startswith("```"):
        return text
    parts = text.split("```")
    if len(parts) < 3:
        return text
    body = parts[1]
    for lang in ("markdown", "latex", "tex"):
        if body.startswith(lang):
            body = body[len(lang):].lstrip("\n")
            break
    return body.strip()


def validate_latex(tex: str) -> None:
    """Raise ValueError if the output is obviously not a compilable LaTeX file."""
    if not tex:
        raise ValueError("Empty LaTeX output")
    if r"\documentclass" not in tex[:200]:
        raise ValueError("LaTeX output must start with \\documentclass")
    if r"\begin{document}" not in tex:
        raise ValueError("LaTeX output missing \\begin{document}")
    if r"\end{document}" not in tex:
        raise ValueError("LaTeX output missing \\end{document}")
    # Balance \begin{...} against \end{...}
    begins = tex.count(r"\begin{")
    ends = tex.count(r"\end{")
    if begins != ends:
        raise ValueError(f"Unbalanced environments: {begins} \\begin vs {ends} \\end")


def _call_bedrock(prompt: str, temperature: float = 0.4) -> str:
    request_body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": MAX_TOKENS,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    })
    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=request_body,
    )
    response_body = json.loads(response["body"].read())
    return response_body["content"][0]["text"].strip()


def invoke_bedrock_tailor(resume_text: str, job_description: str, target_words: int) -> str:
    max_words = int(target_words * 1.15)
    prompt = TAILOR_PROMPT.format(
        resume_text=resume_text[:10000],
        job_description=job_description[:4000],
        target_words=target_words,
        max_words=max_words,
    )
    return _strip_code_fences(_call_bedrock(prompt))


def invoke_bedrock_tailor_latex(resume_text: str, job_description: str,
                                 target_words: int, latex_template: str) -> str:
    """LaTeX variant. Validates output and retries once on obvious structural errors."""
    prompt = TAILOR_PROMPT_LATEX.format(
        resume_text=resume_text[:10000],
        job_description=job_description[:4000],
        target_words=target_words,
        latex_template=latex_template[:12000],
    )
    tex = _strip_code_fences(_call_bedrock(prompt, temperature=0.3))
    try:
        validate_latex(tex)
        return tex
    except ValueError as first_err:
        # One retry with a stricter framing
        retry_prompt = prompt + (
            "\n\nIMPORTANT: Your previous attempt failed validation: "
            f"{first_err}. Output ONLY the complete .tex file starting with "
            r"\documentclass and ending with \end{document}."
        )
        tex = _strip_code_fences(_call_bedrock(retry_prompt, temperature=0.2))
        validate_latex(tex)  # will raise if still broken
        return tex


# ── Domain helpers ────────────────────────────────────────────────────────────

def _load_result(user_id: str, result_id: str) -> Optional[dict]:
    """Fetch a result record for the given user. Returns None if not found or forbidden."""
    resp = RESULTS_TABLE.query(
        IndexName="resultId-index",
        KeyConditionExpression=Key("resultId").eq(result_id),
    )
    for item in resp.get("Items", []):
        if item.get("userId") == user_id:
            return item
    return None


def _job_item_from_adzuna(raw: dict, user_id: str, result_id: str, role: dict) -> dict:
    """Normalize an Adzuna job payload into a DynamoDB row."""
    company = (raw.get("company") or {}).get("display_name", "")
    location = (raw.get("location") or {}).get("display_name", "")
    salary_min = raw.get("salary_min")
    salary_max = raw.get("salary_max")
    return {
        "jobId": str(uuid.uuid4()),
        "userId": user_id,
        "resultId": result_id,
        "roleTitle": role.get("title", ""),
        "matchPercentage": role.get("match_percentage", 0),
        "title": raw.get("title", ""),
        "company": company,
        "location": location,
        "description": raw.get("description", "") or "",
        "redirectUrl": raw.get("redirect_url", ""),
        "created": raw.get("created", ""),
        "salaryMin": int(salary_min) if isinstance(salary_min, (int, float)) else None,
        "salaryMax": int(salary_max) if isinstance(salary_max, (int, float)) else None,
        "salaryCurrency": raw.get("salary_is_predicted", ""),
        "resumeGaps": role.get("resume_gaps", []),
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }


_SKILL_SEPARATORS = (" — ", " – ", " - ", ": ", ". ", " (")


def _short_skill_name(raw: str) -> str:
    """Trim a Bedrock skill entry down to just the skill name.

    Bedrock often returns skills_to_develop as "Skill — long explanation…". We want
    "Skill" only, so Tavily queries and UI labels stay crisp. Falls back to a 40-char
    truncation if no separator is found.
    """
    if not raw:
        return ""
    text = raw.strip()
    for sep in _SKILL_SEPARATORS:
        if sep in text:
            text = text.split(sep, 1)[0]
            break
    return text.strip().rstrip(".,;:")[:40]


def _infer_missing_skills(job: dict, skills_to_develop: list) -> list:
    """Best-effort: intersect the result's skills_to_develop with terms in the JD.

    Returns short skill names (stripped of Bedrock's prose explanations) so the UI
    shows "Kubernetes" instead of the full advisory sentence.
    """
    if not skills_to_develop:
        return []
    normalized = [_short_skill_name(s) for s in skills_to_develop if s]
    normalized = [s for s in normalized if s]
    jd = (job.get("description") or "").lower()
    missing = [s for s in normalized if s.lower() in jd]
    return missing or normalized[:3]


def _word_count(text: str) -> int:
    return len([w for w in (text or "").split() if w.strip()])


# ── Route handlers ────────────────────────────────────────────────────────────

def list_jobs(event: dict) -> dict:
    user_id = get_user_id(event)
    if not user_id:
        return respond(401, {"error": "Unauthorized"})
    params = event.get("queryStringParameters") or {}
    result_id = params.get("resultId")
    if not result_id:
        return respond(400, {"error": "resultId query parameter is required"})

    resp = JOBS_TABLE.query(
        IndexName="resultId-index",
        KeyConditionExpression=Key("resultId").eq(result_id),
    )
    items = [i for i in resp.get("Items", []) if i.get("userId") == user_id]
    return respond(200, {"jobs": items})


def search_jobs(event: dict) -> dict:
    user_id = get_user_id(event)
    if not user_id:
        return respond(401, {"error": "Unauthorized"})
    body = parse_body(event)
    result_id = body.get("resultId")
    if not result_id:
        return respond(400, {"error": "resultId is required"})
    country = (body.get("country") or ADZUNA_COUNTRY).lower()

    result = _load_result(user_id, result_id)
    if not result:
        return respond(404, {"error": "Report not found"})

    # Return cached if already fetched for this result
    existing = JOBS_TABLE.query(
        IndexName="resultId-index",
        KeyConditionExpression=Key("resultId").eq(result_id),
    )
    cached = [i for i in existing.get("Items", []) if i.get("userId") == user_id]
    if cached:
        return respond(200, {"jobs": cached, "cached": True})

    top_roles = result.get("topRoles") or []
    # Pull the candidate's strongest skills so the Adzuna query reflects THIS
    # candidate, not just the role title. Two candidates with the same top role
    # but different stacks should see different listings.
    skills_to_highlight = [
        _short_skill_name(s) for s in (result.get("skillsToHighlight") or [])
    ]
    skills_to_highlight = [s for s in skills_to_highlight if s][:4]

    items_to_write = []
    for role in top_roles[:5]:
        hits = adzuna_search(
            role.get("title", ""), country,
            skills=skills_to_highlight,
        )
        for hit in hits:
            items_to_write.append(_job_item_from_adzuna(hit, user_id, result_id, role))

    if items_to_write:
        with JOBS_TABLE.batch_writer() as batch:
            for item in items_to_write:
                batch.put_item(Item=item)

    return respond(200, {"jobs": items_to_write, "cached": False})


def get_job(event: dict) -> dict:
    user_id = get_user_id(event)
    if not user_id:
        return respond(401, {"error": "Unauthorized"})
    job_id = (event.get("pathParameters") or {}).get("jobId", "")
    if not job_id:
        return respond(400, {"error": "jobId is required"})

    resp = JOBS_TABLE.get_item(Key={"jobId": job_id})
    item = resp.get("Item")
    if not item:
        return respond(404, {"error": "Job not found"})
    if item.get("userId") != user_id:
        return respond(403, {"error": "Forbidden"})
    return respond(200, item)


def fetch_courses(event: dict) -> dict:
    user_id = get_user_id(event)
    if not user_id:
        return respond(401, {"error": "Unauthorized"})
    job_id = (event.get("pathParameters") or {}).get("jobId", "")
    if not job_id:
        return respond(400, {"error": "jobId is required"})

    resp = JOBS_TABLE.get_item(Key={"jobId": job_id})
    job = resp.get("Item")
    if not job:
        return respond(404, {"error": "Job not found"})
    if job.get("userId") != user_id:
        return respond(403, {"error": "Forbidden"})

    # Cached courses on the job row
    if job.get("courses"):
        return respond(200, {"courses": job["courses"], "cached": True})

    # Determine target skills: prefer missing skills inferred from the JD, fall back to resume gaps
    result = _load_result(user_id, job.get("resultId", ""))
    skills_to_develop = (result or {}).get("skillsToDevelop", [])
    skills = _infer_missing_skills(job, skills_to_develop)
    if not skills:
        skills = job.get("resumeGaps", [])[:3]

    courses = []
    for skill in skills[:4]:
        if not skill:
            continue
        query = f"best free online course to learn {skill} for a {job.get('title', '')} role"
        hits = tavily_search(query, max_results=3)
        courses.append({"skill": skill, "recommendations": hits})

    JOBS_TABLE.update_item(
        Key={"jobId": job_id},
        UpdateExpression="SET courses = :c, coursesFetchedAt = :t",
        ExpressionAttributeValues={
            ":c": courses,
            ":t": datetime.now(timezone.utc).isoformat(),
        },
    )

    return respond(200, {"courses": courses, "cached": False})


def create_tailored_resume(event: dict) -> dict:
    user_id = get_user_id(event)
    if not user_id:
        return respond(401, {"error": "Unauthorized"})
    job_id = (event.get("pathParameters") or {}).get("jobId", "")
    if not job_id:
        return respond(400, {"error": "jobId is required"})

    body = parse_body(event)
    fallback_text = body.get("resumeText") or ""

    fmt = (body.get("format") or "markdown").lower()
    if fmt not in VALID_FORMATS:
        return respond(400, {"error": f"format must be one of {sorted(VALID_FORMATS)}"})

    reference_latex = body.get("referenceLatex") or ""
    if fmt == "latex" and not reference_latex.strip():
        reference_latex = DEFAULT_LATEX_TEMPLATE
    if fmt == "latex" and not reference_latex.strip():
        return respond(500, {"error": "Default LaTeX template unavailable"})

    resp = JOBS_TABLE.get_item(Key={"jobId": job_id})
    job = resp.get("Item")
    if not job:
        return respond(404, {"error": "Job not found"})
    if job.get("userId") != user_id:
        return respond(403, {"error": "Forbidden"})

    # Prefer the parsed resume text stored on the result (has real name, contact,
    # links, etc.). Fall back to whatever the client sent — that path covers old
    # reports that were generated before resumeText was stored.
    stored_result = _load_result(user_id, job.get("resultId", ""))
    stored_resume = (stored_result or {}).get("resumeText", "") or ""
    resume_text = stored_resume.strip() or fallback_text.strip()
    if not resume_text:
        return respond(400, {"error": "No resume text available — upload a new resume."})

    # Cache: one tailored resume per (user, job, format). Different format = new row.
    existing = TAILORED_RESUMES_TABLE.query(
        IndexName="jobId-index",
        KeyConditionExpression=Key("jobId").eq(job_id),
    )
    for item in existing.get("Items", []):
        if item.get("userId") == user_id and (item.get("format") or "markdown") == fmt:
            return respond(200, item)

    target_words = max(280, min(600, _word_count(resume_text)))
    try:
        if fmt == "latex":
            content = invoke_bedrock_tailor_latex(
                resume_text, job.get("description", ""), target_words, reference_latex,
            )
        else:
            content = invoke_bedrock_tailor(resume_text, job.get("description", ""), target_words)
    except ValueError as e:
        # LaTeX validation failed even after retry
        print(f"Tailor validation failed: {e}")
        return respond(502, {"error": f"Generated content failed validation: {e}"})
    except Exception as e:
        print(f"Bedrock tailor failed: {e}")
        return respond(502, {"error": "Failed to generate tailored resume"})

    now = datetime.now(timezone.utc).isoformat()
    resume_id = str(uuid.uuid4())
    item = {
        "resumeId": resume_id,
        "userId": user_id,
        "jobId": job_id,
        "resultId": job.get("resultId", ""),
        "format": fmt,
        "markdown": content,  # field name retained for schema compatibility; holds .tex when format=latex
        "targetWords": target_words,
        "wordCount": _word_count(content),
        "createdAt": now,
        "updatedAt": now,
    }
    TAILORED_RESUMES_TABLE.put_item(Item=item)
    return respond(200, item)


def get_tailored_resume(event: dict) -> dict:
    user_id = get_user_id(event)
    if not user_id:
        return respond(401, {"error": "Unauthorized"})
    resume_id = (event.get("pathParameters") or {}).get("resumeId", "")
    if not resume_id:
        return respond(400, {"error": "resumeId is required"})

    resp = TAILORED_RESUMES_TABLE.get_item(Key={"resumeId": resume_id})
    item = resp.get("Item")
    if not item:
        return respond(404, {"error": "Tailored resume not found"})
    if item.get("userId") != user_id:
        return respond(403, {"error": "Forbidden"})
    return respond(200, item)


def save_tailored_resume(event: dict) -> dict:
    user_id = get_user_id(event)
    if not user_id:
        return respond(401, {"error": "Unauthorized"})
    resume_id = (event.get("pathParameters") or {}).get("resumeId", "")
    if not resume_id:
        return respond(400, {"error": "resumeId is required"})

    body = parse_body(event)
    markdown = body.get("markdown")
    if not isinstance(markdown, str):
        return respond(400, {"error": "markdown (string) is required"})

    resp = TAILORED_RESUMES_TABLE.get_item(Key={"resumeId": resume_id})
    item = resp.get("Item")
    if not item:
        return respond(404, {"error": "Tailored resume not found"})
    if item.get("userId") != user_id:
        return respond(403, {"error": "Forbidden"})

    now = datetime.now(timezone.utc).isoformat()
    TAILORED_RESUMES_TABLE.update_item(
        Key={"resumeId": resume_id},
        UpdateExpression="SET markdown = :m, wordCount = :w, updatedAt = :t",
        ExpressionAttributeValues={
            ":m": markdown,
            ":w": _word_count(markdown),
            ":t": now,
        },
    )
    item.update({"markdown": markdown, "wordCount": _word_count(markdown), "updatedAt": now})
    return respond(200, item)


# ── Router ────────────────────────────────────────────────────────────────────

def api_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return respond(200, {})

    method = event.get("httpMethod", "")
    path = event.get("resource") or event.get("path") or ""

    if path.endswith("/jobs/search") and method == "POST":
        return search_jobs(event)
    if path.endswith("/jobs") and method == "GET":
        return list_jobs(event)
    if path.endswith("/jobs/{jobId}") and method == "GET":
        return get_job(event)
    if path.endswith("/jobs/{jobId}/courses") and method == "POST":
        return fetch_courses(event)
    if path.endswith("/jobs/{jobId}/tailored-resume") and method == "POST":
        return create_tailored_resume(event)
    if path.endswith("/tailored-resumes/{resumeId}") and method == "GET":
        return get_tailored_resume(event)
    if path.endswith("/tailored-resumes/{resumeId}") and method == "PUT":
        return save_tailored_resume(event)

    return respond(404, {"error": f"No route for {method} {path}"})
