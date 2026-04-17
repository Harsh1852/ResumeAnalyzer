"""
Applications Service — HTTP API.

Tracks job applications, their statuses (with audit history), and their
interview rounds. Pure CRUD backed by DynamoDB.

Endpoints:
  GET    /applications                                 list (optional ?status=)
  POST   /applications                                 create
  GET    /applications/stats                           aggregate counts + rates
  GET    /applications/{applicationId}                 detail
  PATCH  /applications/{applicationId}                 partial update
  DELETE /applications/{applicationId}                 delete
  POST   /applications/{applicationId}/rounds          add interview round
  PATCH  /applications/{applicationId}/rounds/{id}     update round
  DELETE /applications/{applicationId}/rounds/{id}     delete round
"""
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
APPLICATIONS_TABLE = dynamodb.Table(os.environ["APPLICATIONS_TABLE_NAME"])

VALID_STATUSES = {
    "Wishlist",
    "Applied",
    "Phone Screen",
    "Technical Interview",
    "Onsite",
    "Offer",
    "Rejected",
    "Ghosted",
}
ACTIVE_STATUSES = {"Applied", "Phone Screen", "Technical Interview", "Onsite"}
RESPONSE_STATUSES = {"Phone Screen", "Technical Interview", "Onsite", "Offer"}
VALID_OUTCOMES = {"PENDING", "PASSED", "FAILED", "NO_SHOW", "RESCHEDULED"}

ALLOWED_PATCH_FIELDS = {
    "company", "jobTitle", "location", "jobUrl", "source",
    "status", "nextAction", "nextActionDate", "notes",
    "jobId", "resultId", "tailoredResumeId",
}
ALLOWED_ROUND_FIELDS = {
    "roundName", "scheduledAt", "outcome", "interviewer", "notes",
}


# ── Response helpers ──────────────────────────────────────────────────────────

def respond(status_code: int, body) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "OPTIONS,GET,POST,PATCH,DELETE",
            "Content-Type": "application/json",
        },
        "body": json.dumps(body, default=str),
    }


def get_user_id(event: dict) -> str:
    return event.get("requestContext", {}).get("authorizer", {}).get("claims", {}).get("sub", "")


def parse_body(event: dict) -> dict:
    raw = event.get("body") or "{}"
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_owned(application_id: str, user_id: str) -> Optional[dict]:
    """Fetch an application and confirm the caller owns it. None if missing or forbidden."""
    resp = APPLICATIONS_TABLE.get_item(Key={"applicationId": application_id})
    item = resp.get("Item")
    if not item:
        return None
    if item.get("userId") != user_id:
        return None
    return item


# ── CRUD: applications ────────────────────────────────────────────────────────

def create_application(event: dict) -> dict:
    user_id = get_user_id(event)
    if not user_id:
        return respond(401, {"error": "Unauthorized"})
    body = parse_body(event)

    company = (body.get("company") or "").strip()
    job_title = (body.get("jobTitle") or "").strip()
    if not company or not job_title:
        return respond(400, {"error": "company and jobTitle are required"})

    status = body.get("status") or "Wishlist"
    if status not in VALID_STATUSES:
        return respond(400, {"error": f"Invalid status. Must be one of: {sorted(VALID_STATUSES)}"})

    now = _now()
    application_id = str(uuid.uuid4())

    item = {
        "applicationId": application_id,
        "userId": user_id,
        "company": company,
        "jobTitle": job_title,
        "location": (body.get("location") or "").strip(),
        "jobUrl": (body.get("jobUrl") or "").strip(),
        "source": body.get("source") or "manual",
        "status": status,
        "nextAction": (body.get("nextAction") or "").strip(),
        "nextActionDate": body.get("nextActionDate") or "",
        "notes": body.get("notes") or "",
        "jobId": body.get("jobId") or "",
        "resultId": body.get("resultId") or "",
        "tailoredResumeId": body.get("tailoredResumeId") or "",
        "statusHistory": [{"status": status, "changedAt": now, "note": "Created"}],
        "interviewRounds": [],
        "createdAt": now,
        "updatedAt": now,
        "appliedAt": now if status == "Applied" else "",
        "offeredAt": now if status == "Offer" else "",
    }
    APPLICATIONS_TABLE.put_item(Item=item)
    return respond(201, item)


def list_applications(event: dict) -> dict:
    user_id = get_user_id(event)
    if not user_id:
        return respond(401, {"error": "Unauthorized"})
    params = event.get("queryStringParameters") or {}
    status_filter = params.get("status")

    if status_filter:
        if status_filter not in VALID_STATUSES:
            return respond(400, {"error": "Invalid status filter"})
        resp = APPLICATIONS_TABLE.query(
            IndexName="userId-status-index",
            KeyConditionExpression=Key("userId").eq(user_id) & Key("status").eq(status_filter),
        )
    else:
        resp = APPLICATIONS_TABLE.query(
            IndexName="userId-index",
            KeyConditionExpression=Key("userId").eq(user_id),
            ScanIndexForward=False,  # newest first
        )
    return respond(200, {"applications": resp.get("Items", [])})


def get_application(event: dict) -> dict:
    user_id = get_user_id(event)
    if not user_id:
        return respond(401, {"error": "Unauthorized"})
    application_id = (event.get("pathParameters") or {}).get("applicationId", "")
    if not application_id:
        return respond(400, {"error": "applicationId is required"})

    resp = APPLICATIONS_TABLE.get_item(Key={"applicationId": application_id})
    item = resp.get("Item")
    if not item:
        return respond(404, {"error": "Application not found"})
    if item.get("userId") != user_id:
        return respond(403, {"error": "Forbidden"})
    return respond(200, item)


def update_application(event: dict) -> dict:
    user_id = get_user_id(event)
    if not user_id:
        return respond(401, {"error": "Unauthorized"})
    application_id = (event.get("pathParameters") or {}).get("applicationId", "")
    if not application_id:
        return respond(400, {"error": "applicationId is required"})

    item = _load_owned(application_id, user_id)
    if item is None:
        resp = APPLICATIONS_TABLE.get_item(Key={"applicationId": application_id})
        if resp.get("Item"):
            return respond(403, {"error": "Forbidden"})
        return respond(404, {"error": "Application not found"})

    body = parse_body(event)
    updates = {k: v for k, v in body.items() if k in ALLOWED_PATCH_FIELDS}
    if not updates:
        return respond(400, {"error": "No valid fields to update"})

    if "status" in updates and updates["status"] not in VALID_STATUSES:
        return respond(400, {"error": f"Invalid status. Must be one of: {sorted(VALID_STATUSES)}"})

    now = _now()
    set_parts = ["updatedAt = :updatedAt"]
    expr_values = {":updatedAt": now}
    expr_names = {}

    for field, value in updates.items():
        # 'status' and 'notes' are DynamoDB reserved words; alias them.
        if field in ("status", "notes", "source", "location"):
            placeholder = f"#{field}"
            expr_names[placeholder] = field
            set_parts.append(f"{placeholder} = :{field}")
        else:
            set_parts.append(f"{field} = :{field}")
        expr_values[f":{field}"] = value

    new_status = updates.get("status")
    if new_status and new_status != item.get("status"):
        # Append to statusHistory
        history = list(item.get("statusHistory") or [])
        history.append({
            "status": new_status,
            "changedAt": now,
            "note": body.get("statusNote", ""),
        })
        set_parts.append("statusHistory = :statusHistory")
        expr_values[":statusHistory"] = history
        if new_status == "Applied" and not item.get("appliedAt"):
            set_parts.append("appliedAt = :appliedAt")
            expr_values[":appliedAt"] = now
        if new_status == "Offer" and not item.get("offeredAt"):
            set_parts.append("offeredAt = :offeredAt")
            expr_values[":offeredAt"] = now

    update_kwargs = {
        "Key": {"applicationId": application_id},
        "UpdateExpression": "SET " + ", ".join(set_parts),
        "ExpressionAttributeValues": expr_values,
        "ReturnValues": "ALL_NEW",
    }
    if expr_names:
        update_kwargs["ExpressionAttributeNames"] = expr_names

    resp = APPLICATIONS_TABLE.update_item(**update_kwargs)
    return respond(200, resp.get("Attributes", {}))


def delete_application(event: dict) -> dict:
    user_id = get_user_id(event)
    if not user_id:
        return respond(401, {"error": "Unauthorized"})
    application_id = (event.get("pathParameters") or {}).get("applicationId", "")
    if not application_id:
        return respond(400, {"error": "applicationId is required"})

    item = _load_owned(application_id, user_id)
    if item is None:
        resp = APPLICATIONS_TABLE.get_item(Key={"applicationId": application_id})
        if resp.get("Item"):
            return respond(403, {"error": "Forbidden"})
        return respond(404, {"error": "Application not found"})

    APPLICATIONS_TABLE.delete_item(Key={"applicationId": application_id})
    return respond(200, {"message": "Deleted"})


# ── Interview rounds ──────────────────────────────────────────────────────────

def _sanitize_round_update(body: dict) -> dict:
    updates = {}
    for k, v in body.items():
        if k in ALLOWED_ROUND_FIELDS:
            updates[k] = v
    if "outcome" in updates and updates["outcome"] not in VALID_OUTCOMES:
        raise ValueError(f"Invalid outcome. Must be one of: {sorted(VALID_OUTCOMES)}")
    return updates


def add_round(event: dict) -> dict:
    user_id = get_user_id(event)
    if not user_id:
        return respond(401, {"error": "Unauthorized"})
    application_id = (event.get("pathParameters") or {}).get("applicationId", "")
    if not application_id:
        return respond(400, {"error": "applicationId is required"})

    item = _load_owned(application_id, user_id)
    if item is None:
        return respond(404, {"error": "Application not found"})

    body = parse_body(event)
    round_name = (body.get("roundName") or "").strip()
    if not round_name:
        return respond(400, {"error": "roundName is required"})

    outcome = body.get("outcome") or "PENDING"
    if outcome not in VALID_OUTCOMES:
        return respond(400, {"error": f"Invalid outcome. Must be one of: {sorted(VALID_OUTCOMES)}"})

    now = _now()
    new_round = {
        "roundId": str(uuid.uuid4()),
        "roundName": round_name,
        "scheduledAt": body.get("scheduledAt") or "",
        "outcome": outcome,
        "interviewer": (body.get("interviewer") or "").strip(),
        "notes": body.get("notes") or "",
        "createdAt": now,
    }
    rounds = list(item.get("interviewRounds") or [])
    rounds.append(new_round)

    resp = APPLICATIONS_TABLE.update_item(
        Key={"applicationId": application_id},
        UpdateExpression="SET interviewRounds = :r, updatedAt = :t",
        ExpressionAttributeValues={":r": rounds, ":t": now},
        ReturnValues="ALL_NEW",
    )
    return respond(201, resp.get("Attributes", {}))


def update_round(event: dict) -> dict:
    user_id = get_user_id(event)
    if not user_id:
        return respond(401, {"error": "Unauthorized"})
    params = event.get("pathParameters") or {}
    application_id = params.get("applicationId", "")
    round_id = params.get("roundId", "")
    if not application_id or not round_id:
        return respond(400, {"error": "applicationId and roundId are required"})

    item = _load_owned(application_id, user_id)
    if item is None:
        return respond(404, {"error": "Application not found"})

    try:
        updates = _sanitize_round_update(parse_body(event))
    except ValueError as e:
        return respond(400, {"error": str(e)})
    if not updates:
        return respond(400, {"error": "No valid fields to update"})

    rounds = list(item.get("interviewRounds") or [])
    target_idx = next((i for i, r in enumerate(rounds) if r.get("roundId") == round_id), None)
    if target_idx is None:
        return respond(404, {"error": "Round not found"})

    merged = {**rounds[target_idx], **updates}
    rounds[target_idx] = merged

    now = _now()
    resp = APPLICATIONS_TABLE.update_item(
        Key={"applicationId": application_id},
        UpdateExpression="SET interviewRounds = :r, updatedAt = :t",
        ExpressionAttributeValues={":r": rounds, ":t": now},
        ReturnValues="ALL_NEW",
    )
    return respond(200, resp.get("Attributes", {}))


def delete_round(event: dict) -> dict:
    user_id = get_user_id(event)
    if not user_id:
        return respond(401, {"error": "Unauthorized"})
    params = event.get("pathParameters") or {}
    application_id = params.get("applicationId", "")
    round_id = params.get("roundId", "")
    if not application_id or not round_id:
        return respond(400, {"error": "applicationId and roundId are required"})

    item = _load_owned(application_id, user_id)
    if item is None:
        return respond(404, {"error": "Application not found"})

    rounds = [r for r in (item.get("interviewRounds") or []) if r.get("roundId") != round_id]
    if len(rounds) == len(item.get("interviewRounds") or []):
        return respond(404, {"error": "Round not found"})

    now = _now()
    resp = APPLICATIONS_TABLE.update_item(
        Key={"applicationId": application_id},
        UpdateExpression="SET interviewRounds = :r, updatedAt = :t",
        ExpressionAttributeValues={":r": rounds, ":t": now},
        ReturnValues="ALL_NEW",
    )
    return respond(200, resp.get("Attributes", {}))


# ── Stats ─────────────────────────────────────────────────────────────────────

def get_stats(event: dict) -> dict:
    user_id = get_user_id(event)
    if not user_id:
        return respond(401, {"error": "Unauthorized"})

    resp = APPLICATIONS_TABLE.query(
        IndexName="userId-index",
        KeyConditionExpression=Key("userId").eq(user_id),
    )
    items = resp.get("Items", [])

    by_status = {st: 0 for st in VALID_STATUSES}
    for it in items:
        st = it.get("status")
        if st in by_status:
            by_status[st] += 1

    total = len(items)
    applied_plus = sum(by_status[s] for s in ACTIVE_STATUSES | {"Offer"} | {"Rejected"})
    responded = sum(by_status[s] for s in RESPONSE_STATUSES)
    offers = by_status.get("Offer", 0)

    response_rate = (responded / applied_plus) if applied_plus else 0.0
    offer_rate = (offers / applied_plus) if applied_plus else 0.0
    active = sum(by_status[s] for s in ACTIVE_STATUSES)

    return respond(200, {
        "total": total,
        "active": active,
        "byStatus": by_status,
        "responseRate": round(response_rate, 3),
        "offerRate": round(offer_rate, 3),
    })


# ── Router ────────────────────────────────────────────────────────────────────

def api_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return respond(200, {})

    method = event.get("httpMethod", "")
    path = event.get("resource") or event.get("path") or ""

    # Order matters — stats must be matched before the generic {applicationId} route
    if path.endswith("/applications/stats") and method == "GET":
        return get_stats(event)
    if path.endswith("/applications") and method == "POST":
        return create_application(event)
    if path.endswith("/applications") and method == "GET":
        return list_applications(event)
    if path.endswith("/applications/{applicationId}") and method == "GET":
        return get_application(event)
    if path.endswith("/applications/{applicationId}") and method == "PATCH":
        return update_application(event)
    if path.endswith("/applications/{applicationId}") and method == "DELETE":
        return delete_application(event)
    if path.endswith("/applications/{applicationId}/rounds") and method == "POST":
        return add_round(event)
    if path.endswith("/applications/{applicationId}/rounds/{roundId}") and method == "PATCH":
        return update_round(event)
    if path.endswith("/applications/{applicationId}/rounds/{roundId}") and method == "DELETE":
        return delete_round(event)

    return respond(404, {"error": f"No route for {method} {path}"})
