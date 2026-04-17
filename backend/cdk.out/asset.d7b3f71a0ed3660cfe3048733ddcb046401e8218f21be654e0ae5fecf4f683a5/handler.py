"""Upload Service — presigned URL generation, upload confirmation, status polling."""
import json
import os
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

s3 = boto3.client("s3")
sqs = boto3.client("sqs")
dynamodb = boto3.resource("dynamodb")

BUCKET_NAME = os.environ["RESUMES_BUCKET_NAME"]
UPLOADS_TABLE = dynamodb.Table(os.environ["UPLOADS_TABLE_NAME"])
PARSE_QUEUE_URL = os.environ["PARSE_QUEUE_URL"]
PRESIGNED_EXPIRY = int(os.environ.get("PRESIGNED_URL_EXPIRY_SECONDS", "300"))

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def respond(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "OPTIONS,POST,GET",
            "Content-Type": "application/json",
        },
        "body": json.dumps(body),
    }


def get_user_id(event: dict) -> str:
    return event.get("requestContext", {}).get("authorizer", {}).get("claims", {}).get("sub", "")


def get_presigned_url(event: dict) -> dict:
    user_id = get_user_id(event)
    if not user_id:
        return respond(401, {"error": "Unauthorized"})

    body = json.loads(event.get("body") or "{}")
    file_name = body.get("fileName", "").strip()
    content_type = body.get("contentType", "application/octet-stream")

    if not file_name:
        return respond(400, {"error": "fileName is required"})

    ext = os.path.splitext(file_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return respond(400, {"error": f"File type not supported. Use: {', '.join(ALLOWED_EXTENSIONS)}"})

    upload_id = str(uuid.uuid4())
    s3_key = f"uploads/{user_id}/{upload_id}/{file_name}"

    presigned_url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": BUCKET_NAME, "Key": s3_key, "ContentType": content_type},
        ExpiresIn=PRESIGNED_EXPIRY,
    )

    UPLOADS_TABLE.put_item(Item={
        "userId": user_id,
        "uploadId": upload_id,
        "fileName": file_name,
        "s3Key": s3_key,
        "status": "PENDING",
        "createdAt": datetime.now(timezone.utc).isoformat(),
    })

    return respond(200, {
        "uploadId": upload_id,
        "presignedUrl": presigned_url,
        "s3Key": s3_key,
        "expiresIn": PRESIGNED_EXPIRY,
    })


def confirm_upload(event: dict) -> dict:
    user_id = get_user_id(event)
    if not user_id:
        return respond(401, {"error": "Unauthorized"})

    body = json.loads(event.get("body") or "{}")
    upload_id = body.get("uploadId", "").strip()

    if not upload_id:
        return respond(400, {"error": "uploadId is required"})

    result = UPLOADS_TABLE.query(
        IndexName="uploadId-index",
        KeyConditionExpression=Key("uploadId").eq(upload_id),
    )
    if not result["Items"]:
        return respond(404, {"error": "Upload not found"})

    item = result["Items"][0]
    if item["userId"] != user_id:
        return respond(403, {"error": "Forbidden"})

    UPLOADS_TABLE.update_item(
        Key={"userId": user_id, "uploadId": upload_id},
        UpdateExpression="SET #s = :s, confirmedAt = :t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": "UPLOADED", ":t": datetime.now(timezone.utc).isoformat()},
    )

    sqs.send_message(
        QueueUrl=PARSE_QUEUE_URL,
        MessageBody=json.dumps({
            "uploadId": upload_id,
            "userId": user_id,
            "s3Key": item["s3Key"],
            "fileName": item["fileName"],
            "source": "confirm",
        }),
    )

    return respond(200, {"message": "Upload confirmed. Processing started.", "uploadId": upload_id})


def list_uploads(event: dict) -> dict:
    user_id = get_user_id(event)
    if not user_id:
        return respond(401, {"error": "Unauthorized"})

    result = UPLOADS_TABLE.query(
        KeyConditionExpression=Key("userId").eq(user_id),
        ScanIndexForward=False,
        Limit=20,
    )
    return respond(200, {"uploads": result["Items"]})


def get_upload(event: dict) -> dict:
    user_id = get_user_id(event)
    if not user_id:
        return respond(401, {"error": "Unauthorized"})

    upload_id = (event.get("pathParameters") or {}).get("uploadId", "")
    if not upload_id:
        return respond(400, {"error": "uploadId is required"})

    result = UPLOADS_TABLE.get_item(Key={"userId": user_id, "uploadId": upload_id})
    if "Item" not in result:
        return respond(404, {"error": "Upload not found"})

    return respond(200, result["Item"])


def get_view_url(event: dict) -> dict:
    user_id = get_user_id(event)
    if not user_id:
        return respond(401, {"error": "Unauthorized"})

    upload_id = (event.get("pathParameters") or {}).get("uploadId", "")
    if not upload_id:
        return respond(400, {"error": "uploadId is required"})

    result = UPLOADS_TABLE.get_item(Key={"userId": user_id, "uploadId": upload_id})
    if "Item" not in result:
        return respond(404, {"error": "Upload not found"})

    item = result["Item"]
    s3_key = item.get("s3Key", "")
    if not s3_key:
        return respond(404, {"error": "Resume file not found"})

    view_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET_NAME, "Key": s3_key},
        ExpiresIn=3600,
    )
    return respond(200, {"viewUrl": view_url, "fileName": item.get("fileName", "resume")})


def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return respond(200, {})

    path = event.get("path", "")
    method = event.get("httpMethod", "")

    if "/presigned-url" in path and method == "POST":
        return get_presigned_url(event)
    if "/confirm" in path and method == "POST":
        return confirm_upload(event)
    if method == "GET":
        if "/view-url" in path:
            return get_view_url(event)
        if (event.get("pathParameters") or {}).get("uploadId"):
            return get_upload(event)
        return list_uploads(event)

    return respond(404, {"error": "Not found"})
