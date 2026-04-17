"""
Analyzer Service — SQS-triggered.
Reads parsed resume text from S3, invokes Amazon Bedrock (Claude 3 Haiku),
stores JSON result in S3, publishes to ResultsSNS topic for fan-out.
Idempotent: skips if analysisJobId already processed.
"""
import json
import os
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
MAX_TOKENS = int(os.environ.get("BEDROCK_MAX_TOKENS", "4096"))

ANALYSIS_PROMPT = """You are an expert career counselor and resume analyst with 20 years of experience.
Analyze the resume below and return a career analysis in valid JSON — no markdown, no extra text.

Resume:
---
{resume_text}
---

Return exactly this JSON structure:
{{
  "resume_score": <integer 0-100 rating overall resume quality>,
  "summary": "<2-3 sentence professional profile summary>",
  "top_roles": [
    {{
      "title": "<job title>",
      "match_percentage": <integer 0-100>,
      "reason": "<1-2 sentences explaining fit>",
      "target_companies": ["<company1>", "<company2>", "<company3>", "<company4>", "<company5>"]
    }}
  ],
  "job_search_strategies": [
    "<actionable strategy 1>",
    "<actionable strategy 2>",
    "<actionable strategy 3>",
    "<actionable strategy 4>",
    "<actionable strategy 5>"
  ],
  "skills_to_highlight": ["<skill1>", "<skill2>", "<skill3>"],
  "skills_to_develop": ["<skill1>", "<skill2>", "<skill3>"],
  "key_achievements": ["<achievement1>", "<achievement2>", "<achievement3>"]
}}

Include exactly 5 top_roles, 5 job_search_strategies, 3 skills_to_highlight, 3 skills_to_develop, and 3 key_achievements."""


def invoke_bedrock(resume_text: str) -> dict:
    prompt = ANALYSIS_PROMPT.format(resume_text=resume_text[:8000])  # cap to avoid token limit
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

    # Strip markdown code fences if Claude wrapped the JSON
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
    return json.loads(raw_text)


def process_record(record: dict):
    # SNS wraps SQS in a nested body when using fan-out
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
        status = existing["Items"][0].get("status")
        if status in ("COMPLETE", "PROCESSING"):
            print(f"Skipping duplicate: uploadId={upload_id} status={status}")
            return

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

    # Fetch parsed text
    obj = s3.get_object(Bucket=os.environ.get("PARSED_OUTPUT_BUCKET", ""), Key=parsed_text_key)
    parsed_data = json.loads(obj["Body"].read())
    resume_text = parsed_data.get("text", "")

    if not resume_text.strip():
        raise ValueError("Empty resume text — cannot analyze")

    # Invoke Bedrock
    try:
        analysis = invoke_bedrock(resume_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Bedrock returned non-JSON response: {e}")

    # Store result in S3
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

    # Fan-out via SNS → Results queue + Notification queue
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
