"""
Results Service — two entry points:
  worker_handler: SQS-triggered, aggregates analysis into ResultsTable
  api_handler:    HTTP GET /results and /results/{resultId}
"""
import json
import os
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")

RESULTS_TABLE = dynamodb.Table(os.environ["RESULTS_TABLE_NAME"])
UPLOADS_TABLE = dynamodb.Table(os.environ["UPLOADS_TABLE_NAME"])


def respond(status_code: int, body) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "OPTIONS,GET,DELETE",
            "Content-Type": "application/json",
        },
        "body": json.dumps(body, default=str),
    }


# ── Worker: SQS consumer ──────────────────────────────────────────────────────

def process_result_record(record: dict):
    body = json.loads(record["body"])
    # SNS fan-out wraps the message
    if "Message" in body:
        body = json.loads(body["Message"])

    analysis_job_id = body["analysisJobId"]
    upload_id = body["uploadId"]
    user_id = body["userId"]
    analysis = body["analysis"]

    # Idempotency check
    existing = RESULTS_TABLE.query(
        IndexName="uploadId-index",
        KeyConditionExpression=Key("uploadId").eq(upload_id),
    )
    if existing["Items"]:
        print(f"Result already exists for uploadId={upload_id}, skipping")
        return

    result_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    RESULTS_TABLE.put_item(Item={
        "userId": user_id,
        "resultId": result_id,
        "uploadId": upload_id,
        "analysisJobId": analysis_job_id,
        "resumeScore": analysis.get("resume_score", 0),
        "summary": analysis.get("summary", ""),
        "resumeSectionsReview": analysis.get("resume_sections_review", {}),
        "criticalImprovements": analysis.get("critical_improvements", []),
        "topRoles": analysis.get("top_roles", []),
        "jobSearchStrategies": analysis.get("job_search_strategies", []),
        "skillsToHighlight": analysis.get("skills_to_highlight", []),
        "skillsToDevelop": analysis.get("skills_to_develop", []),
        "keyAchievements": analysis.get("key_achievements", []),
        "createdAt": now,
    })

    # Write resultId back to upload record so the frontend can find it
    UPLOADS_TABLE.update_item(
        Key={"userId": user_id, "uploadId": upload_id},
        UpdateExpression="SET #s = :s, resultId = :r, completedAt = :t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "COMPLETE",
            ":r": result_id,
            ":t": now,
        },
    )
    print(f"Result stored: resultId={result_id} uploadId={upload_id} score={analysis.get('resume_score')}")


def worker_handler(event, context):
    for record in event.get("Records", []):
        try:
            process_result_record(record)
        except Exception as e:
            print(f"Worker failed: {e}")
            raise


# ── API: HTTP handler ─────────────────────────────────────────────────────────

def get_user_id(event: dict) -> str:
    return event.get("requestContext", {}).get("authorizer", {}).get("claims", {}).get("sub", "")


def list_results(event: dict) -> dict:
    user_id = get_user_id(event)
    if not user_id:
        return respond(401, {"error": "Unauthorized"})

    params = event.get("queryStringParameters") or {}
    upload_id = params.get("uploadId")

    if upload_id:
        result = RESULTS_TABLE.query(
            IndexName="uploadId-index",
            KeyConditionExpression=Key("uploadId").eq(upload_id),
        )
        items = [i for i in result["Items"] if i["userId"] == user_id]
    else:
        result = RESULTS_TABLE.query(
            KeyConditionExpression=Key("userId").eq(user_id),
            ScanIndexForward=False,
            Limit=20,
        )
        items = result["Items"]

    return respond(200, {"results": items})


def get_result(event: dict) -> dict:
    user_id = get_user_id(event)
    if not user_id:
        return respond(401, {"error": "Unauthorized"})

    result_id = event.get("pathParameters", {}).get("resultId", "")
    if not result_id:
        return respond(400, {"error": "resultId is required"})

    result = RESULTS_TABLE.query(
        IndexName="resultId-index",
        KeyConditionExpression=Key("resultId").eq(result_id),
    )
    if not result["Items"]:
        return respond(404, {"error": "Result not found"})

    item = result["Items"][0]
    if item["userId"] != user_id:
        return respond(403, {"error": "Forbidden"})

    return respond(200, item)


def delete_result(event: dict) -> dict:
    user_id = get_user_id(event)
    if not user_id:
        return respond(401, {"error": "Unauthorized"})

    result_id = (event.get("pathParameters") or {}).get("resultId", "")
    if not result_id:
        return respond(400, {"error": "resultId is required"})

    result = RESULTS_TABLE.query(
        IndexName="resultId-index",
        KeyConditionExpression=Key("resultId").eq(result_id),
    )
    if not result["Items"]:
        return respond(404, {"error": "Result not found"})

    item = result["Items"][0]
    if item["userId"] != user_id:
        return respond(403, {"error": "Forbidden"})

    RESULTS_TABLE.delete_item(Key={"userId": user_id, "resultId": result_id})

    # Clear resultId from the upload record so the dashboard reflects the deletion
    upload_id = item.get("uploadId")
    if upload_id:
        try:
            UPLOADS_TABLE.update_item(
                Key={"userId": user_id, "uploadId": upload_id},
                UpdateExpression="REMOVE resultId SET #s = :s",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":s": "ANALYZING"},
            )
        except Exception as e:
            print(f"Upload status update warning: {e}")

    return respond(200, {"message": "Report deleted"})


def api_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return respond(200, {})

    result_id = (event.get("pathParameters") or {}).get("resultId")
    if result_id:
        if event.get("httpMethod") == "DELETE":
            return delete_result(event)
        return get_result(event)
    return list_results(event)
