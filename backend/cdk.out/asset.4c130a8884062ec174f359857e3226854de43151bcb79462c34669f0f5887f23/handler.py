"""
Analyzer Service — SQS-triggered.
Reads parsed resume text from S3, fetches real-time job market data via Tavily,
invokes Amazon Bedrock (Claude 3.5 Sonnet), stores JSON result in S3,
publishes to ResultsSNS topic for fan-out.
Idempotent: skips if analysisJobId already processed.
"""
import json
import os
import urllib.request
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
sns = boto3.client("sns")
dynamodb = boto3.resource("dynamodb")

ANALYSIS_RESULTS_BUCKET = os.environ["ANALYSIS_RESULTS_BUCKET"]
ANALYSIS_JOBS_TABLE = dynamodb.Table(os.environ["ANALYSIS_JOBS_TABLE"])
RESULTS_TOPIC_ARN = os.environ["RESULTS_TOPIC_ARN"]
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
MAX_TOKENS = int(os.environ.get("BEDROCK_MAX_TOKENS", "8192"))
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

ANALYSIS_PROMPT = """You are a seasoned career advisor and senior technical recruiter with 20 years of experience. Your role is to give candidates the honest, detailed feedback a great mentor would give — truthful and specific, but constructive. Frame problems as opportunities to improve, not failures. Every piece of feedback must explain WHY it matters and HOW to fix it.

Resume:
---
{resume_text}
---

{market_context}

Return valid JSON only — no markdown, no extra text.

SCORING GUIDE for resume_score (calibrate carefully — most resumes score 45-70):
- 85-100: Exceptional. Quantified achievements throughout, no gaps, polished presentation.
- 70-84: Strong. Minor gaps or weak phrasing in a few places. Competitive at good companies.
- 55-69: Average. Lacks specificity or quantification in key areas. Needs targeted improvements.
- 40-54: Below average. Several missing elements or vague descriptions. Significant work needed.
- Below 40: Needs a full rewrite. Fundamental structural or content issues.

GUIDE for match_percentage (be realistic):
- 85-100%: Near-perfect fit — candidate has almost every required and preferred qualification.
- 70-84%: Strong fit with a small number of addressable gaps.
- 50-69%: Moderate fit — real gaps exist but the candidate is a plausible hire with preparation.
- Below 50%: Aspirational — candidate would need 6-18 months of development to be competitive.

GUIDE for target_companies: Use real-time market data where available. Match company tier to the candidate's actual experience level and market:
- Entry/junior: startups, growth-stage companies, rotational programs at large firms.
- Mid-level: scale-ups, well-known tech firms, domain-specific industry leaders.
- Senior: top-tier only if the resume clearly demonstrates that caliber.
- Mix reach (stretch), target (realistic), and likely (high probability) companies across the 5.

Return exactly this JSON structure:
{{
  "resume_score": <integer 0-100>,
  "summary": "<3 sentences: candidate's professional level and years of experience, their 2 strongest differentiators, and the single most important thing holding them back>",
  "resume_sections_review": {{
    "professional_summary": "<specific feedback on the summary/objective: is it compelling, tailored, and concise? What should change and why?>",
    "work_experience": "<feedback on experience bullets: are achievements quantified? Do they show impact or just list duties? Give 1-2 concrete rewrite examples>",
    "skills_section": "<is the skills section well-organized and relevant? Are any critical skills missing or buried?>",
    "education": "<feedback on education presentation: relevant coursework, GPA if strong, certifications — what to add or remove?>",
    "overall_presentation": "<feedback on length, formatting, ATS compatibility, and overall visual impression>"
  }},
  "critical_improvements": [
    "<improvement 1: specific change + why it matters + how to do it — e.g. 'Rewrite 4 experience bullets to include metrics: instead of managed a team, write led a 5-person team that reduced deployment time by 40%'>",
    "<improvement 2>",
    "<improvement 3>",
    "<improvement 4>",
    "<improvement 5>"
  ],
  "top_roles": [
    {{
      "title": "<job title>",
      "match_percentage": <integer 0-100>,
      "reason": "<3 sentences: what specifically qualifies them for this role, what real gaps hiring managers will notice, and whether this is a reach/target/likely role for this candidate>",
      "resume_gaps": [
        "<gap 1: specific missing skill/experience + why it matters for this role + how to address it>",
        "<gap 2>",
        "<gap 3>"
      ],
      "application_tips": [
        "<tip 1: what to emphasize or tailor in the resume specifically for this role — be concrete>",
        "<tip 2: what to highlight in the cover letter or LinkedIn message when applying>",
        "<tip 3: how to prepare for interviews for this specific role — key topics, projects to mention>"
      ],
      "target_companies": ["<company1>", "<company2>", "<company3>", "<company4>", "<company5>"]
    }}
  ],
  "job_search_strategies": [
    "<strategy 1: specific tactic with clear steps — e.g. not just 'use LinkedIn' but 'identify 10 hiring managers at target companies on LinkedIn, follow their posts for 2 weeks, then send a personalized connection request referencing a specific post before applying'>",
    "<strategy 2: referral and networking approach specific to this candidate's field and level>",
    "<strategy 3: how to optimize their online presence — GitHub, LinkedIn, portfolio — for their target roles>",
    "<strategy 4: specific job boards, communities, or events most relevant to this candidate's field>",
    "<strategy 5: how to approach the application process — volume vs targeted, timeline, follow-up strategy>",
    "<strategy 6: how to prepare for technical screening or assessments common in their target roles>",
    "<strategy 7: a longer-term strategy to strengthen their profile over the next 3-6 months while actively applying>"
  ],
  "skills_to_highlight": [
    "<skill 1 — explain specifically why this differentiates this candidate in their target market>",
    "<skill 2>",
    "<skill 3>"
  ],
  "skills_to_develop": [
    "<skill 1 — explain exactly why this is blocking them, which roles need it, and the fastest way to learn it>",
    "<skill 2>",
    "<skill 3>"
  ],
  "key_achievements": [
    "<achievement 1 — if it lacks metrics, rewrite it with estimated impact; explain why this achievement is compelling to employers>",
    "<achievement 2>",
    "<achievement 3>"
  ]
}}

Include exactly: 5 critical_improvements, 5 top_roles each with 3 resume_gaps + 3 application_tips + 5 target_companies, 7 job_search_strategies, 3 skills_to_highlight, 3 skills_to_develop, 3 key_achievements."""


# ── Tavily helpers ─────────────────────────────────────────────────────────────

def tavily_search(query: str) -> str:
    """Call Tavily search API and return a concise summary string."""
    payload = json.dumps({
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",
        "max_results": 3,
        "include_answer": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    if data.get("answer"):
        return data["answer"]
    snippets = [r.get("content", "")[:200] for r in data.get("results", [])[:3]]
    return " | ".join(s for s in snippets if s)


def extract_field(resume_text: str) -> str:
    """Infer the candidate's primary job field from resume keywords."""
    t = resume_text.lower()
    if any(k in t for k in ["machine learning", "deep learning", "nlp", "neural network", "data science", "llm"]):
        return "data science and machine learning"
    if any(k in t for k in ["software engineer", "backend", "frontend", "full stack", "fullstack", "web developer"]):
        return "software engineering"
    if any(k in t for k in ["devops", "sre", "site reliability", "kubernetes", "terraform", "ci/cd", "platform engineer"]):
        return "devops and cloud engineering"
    if any(k in t for k in ["data analyst", "business intelligence", "tableau", "power bi", "sql analyst", "analytics engineer"]):
        return "data analytics and business intelligence"
    if any(k in t for k in ["product manager", "product management", "roadmap", "go-to-market"]):
        return "product management"
    if any(k in t for k in ["cybersecurity", "security engineer", "penetration", "soc", "infosec"]):
        return "cybersecurity"
    if any(k in t for k in ["ux", "user experience", "product design", "figma", "ui designer"]):
        return "ux and product design"
    if any(k in t for k in ["aws", "azure", "gcp", "cloud architect", "solutions architect"]):
        return "cloud architecture"
    return "technology"


def get_market_context(resume_text: str) -> str:
    """Run 2 targeted Tavily searches and return formatted context for the prompt."""
    if not TAVILY_API_KEY:
        return ""
    field = extract_field(resume_text)
    print(f"Fetching market data for field: {field}")
    try:
        hiring = tavily_search(f"top companies actively hiring {field} professionals 2025 job market")
    except Exception as e:
        print(f"Tavily hiring search failed: {e}")
        hiring = ""
    try:
        skills = tavily_search(f"most in-demand skills for {field} jobs 2025")
    except Exception as e:
        print(f"Tavily skills search failed: {e}")
        skills = ""

    if not hiring and not skills:
        return ""

    lines = ["Current Job Market Intelligence (real-time data — use this to inform company suggestions, skills, and strategies):"]
    if hiring:
        lines.append(f"- Hiring trends: {hiring}")
    if skills:
        lines.append(f"- In-demand skills: {skills}")
    return "\n".join(lines)


# ── Bedrock ────────────────────────────────────────────────────────────────────

def invoke_bedrock(resume_text: str, market_context: str) -> dict:
    prompt = ANALYSIS_PROMPT.format(
        resume_text=resume_text[:12000],
        market_context=market_context,
    )
    request_body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": MAX_TOKENS,
        "temperature": 0.3,
        "messages": [{"role": "user", "content": prompt}],
    })
    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=request_body,
    )
    response_body = json.loads(response["body"].read())
    raw_text = response_body["content"][0]["text"].strip()

    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
    return json.loads(raw_text)


# ── Main pipeline ──────────────────────────────────────────────────────────────

def process_record(record: dict):
    body = json.loads(record["body"])
    if "Message" in body:
        body = json.loads(body["Message"])

    parse_job_id = body["parseJobId"]
    upload_id = body["uploadId"]
    user_id = body["userId"]
    parsed_text_key = body["parsedTextKey"]

    # Idempotency check
    existing = ANALYSIS_JOBS_TABLE.query(
        IndexName="uploadId-index",
        KeyConditionExpression=Key("uploadId").eq(upload_id),
    )
    if existing["Items"]:
        existing_item = existing["Items"][0]
        status = existing_item.get("status")
        if status == "COMPLETE":
            print(f"Skipping duplicate: uploadId={upload_id} already COMPLETE")
            return
        if status == "PROCESSING":
            print(f"Previous attempt stuck in PROCESSING for uploadId={upload_id}, retrying")
            ANALYSIS_JOBS_TABLE.delete_item(Key={"analysisJobId": existing_item["analysisJobId"]})

    analysis_job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    ANALYSIS_JOBS_TABLE.put_item(Item={
        "analysisJobId": analysis_job_id,
        "parseJobId": parse_job_id,
        "uploadId": upload_id,
        "userId": user_id,
        "status": "PROCESSING",
        "createdAt": now,
        "modelId": MODEL_ID,
    })

    obj = s3.get_object(Bucket=os.environ.get("PARSED_OUTPUT_BUCKET", ""), Key=parsed_text_key)
    parsed_data = json.loads(obj["Body"].read())
    resume_text = parsed_data.get("text", "")

    if not resume_text.strip():
        raise ValueError("Empty resume text — cannot analyze")

    market_context = get_market_context(resume_text)
    if market_context:
        print("Market context fetched successfully")
    else:
        print("No market context (Tavily key missing or search failed) — proceeding without it")

    try:
        analysis = invoke_bedrock(resume_text, market_context)
    except json.JSONDecodeError as e:
        raise ValueError(f"Bedrock returned non-JSON response: {e}")

    result_key = f"analysis/{user_id}/{upload_id}/result.json"
    s3.put_object(
        Bucket=ANALYSIS_RESULTS_BUCKET,
        Key=result_key,
        Body=json.dumps({
            "analysisJobId": analysis_job_id,
            "uploadId": upload_id,
            "userId": user_id,
            "analysis": analysis,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }),
        ContentType="application/json",
    )

    ANALYSIS_JOBS_TABLE.update_item(
        Key={"analysisJobId": analysis_job_id},
        UpdateExpression="SET #s = :s, resultKey = :k, completedAt = :t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "COMPLETE",
            ":k": result_key,
            ":t": datetime.now(timezone.utc).isoformat(),
        },
    )

    sns.publish(
        TopicArn=RESULTS_TOPIC_ARN,
        Message=json.dumps({
            "analysisJobId": analysis_job_id,
            "uploadId": upload_id,
            "userId": user_id,
            "resultKey": result_key,
            "analysis": analysis,
        }),
    )
    print(f"Analysis complete: analysisJobId={analysis_job_id} uploadId={upload_id} score={analysis.get('resume_score')}")


def handler(event, context):
    for record in event.get("Records", []):
        try:
            process_record(record)
        except Exception as e:
            print(f"Failed to process record: {e}")
            raise
