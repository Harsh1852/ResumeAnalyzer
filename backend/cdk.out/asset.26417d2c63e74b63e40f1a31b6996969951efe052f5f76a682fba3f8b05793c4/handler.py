"""
Parser Service — SQS-triggered.
Downloads resume from S3, extracts text via Amazon Textract,
stores extracted JSON in S3, updates DynamoDB, forwards to AnalysisQueue.
Idempotent: skips if parseJobId already processed.
"""
import json
import os
import time
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

s3 = boto3.client("s3")
textract = boto3.client("textract")
sqs = boto3.client("sqs")
dynamodb = boto3.resource("dynamodb")

PARSED_OUTPUT_BUCKET = os.environ["PARSED_OUTPUT_BUCKET"]
PARSE_JOBS_TABLE = dynamodb.Table(os.environ["PARSE_JOBS_TABLE"])
UPLOADS_TABLE = dynamodb.Table(os.environ["UPLOADS_TABLE"])
ANALYSIS_QUEUE_URL = os.environ["ANALYSIS_QUEUE_URL"]
MAX_POLL_ATTEMPTS = int(os.environ.get("TEXTRACT_POLLING_ATTEMPTS", "20"))
POLL_DELAY = int(os.environ.get("TEXTRACT_POLLING_DELAY", "10"))


def update_upload_status(user_id: str, upload_id: str, status: str):
    UPLOADS_TABLE.update_item(
        Key={"userId": user_id, "uploadId": upload_id},
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": status},
    )


def extract_text_sync(bucket: str, key: str) -> str:
    """Synchronous Textract for single-page images (JPEG/PNG)."""
    res = textract.detect_document_text(
        Document={"S3Object": {"Bucket": bucket, "Name": key}}
    )
    lines = [b["Text"] for b in res["Blocks"] if b["BlockType"] == "LINE"]
    return "\n".join(lines)


def extract_text_async(bucket: str, key: str) -> str:
    """Async Textract for PDFs (multi-page supported)."""
    start = textract.start_document_text_detection(
        DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}}
    )
    job_id = start["JobId"]

    for _ in range(MAX_POLL_ATTEMPTS):
        time.sleep(POLL_DELAY)
        result = textract.get_document_text_detection(JobId=job_id)
        status = result["JobStatus"]
        if status == "SUCCEEDED":
            blocks = result.get("Blocks", [])
            # Handle pagination
            next_token = result.get("NextToken")
            while next_token:
                page = textract.get_document_text_detection(JobId=job_id, NextToken=next_token)
                blocks.extend(page.get("Blocks", []))
                next_token = page.get("NextToken")
            lines = [b["Text"] for b in blocks if b["BlockType"] == "LINE"]
            return "\n".join(lines)
        if status == "FAILED":
            raise RuntimeError(f"Textract job {job_id} failed")

    raise TimeoutError(f"Textract job {job_id} did not complete in time")


def process_record(record: dict):
    body = json.loads(record["body"])

    # S3 event notification has a different shape than our direct SQS message
    if "Records" in body:
        s3_record = body["Records"][0]["s3"]
        bucket = s3_record["bucket"]["name"]
        s3_key = s3_record["object"]["key"]
        # Derive upload_id from key: uploads/{userId}/{uploadId}/{fileName}
        parts = s3_key.split("/")
        user_id = parts[1] if len(parts) > 2 else "unknown"
        upload_id = parts[2] if len(parts) > 3 else "unknown"
        source = "s3_event"
    else:
        upload_id = body["uploadId"]
        user_id = body["userId"]
        s3_key = body["s3Key"]
        bucket = os.environ.get("RESUMES_BUCKET_NAME", "")
        source = body.get("source", "direct")

    # Idempotency check
    existing = PARSE_JOBS_TABLE.query(
        IndexName="uploadId-index",
        KeyConditionExpression=Key("uploadId").eq(upload_id),
    )
    if existing["Items"]:
        existing_status = existing["Items"][0].get("status")
        if existing_status in ("COMPLETE", "PROCESSING"):
            print(f"Skipping duplicate: uploadId={upload_id} status={existing_status}")
            return

    parse_job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    PARSE_JOBS_TABLE.put_item(Item={
        "parseJobId": parse_job_id,
        "uploadId": upload_id,
        "userId": user_id,
        "status": "PROCESSING",
        "createdAt": now,
    })
    update_upload_status(user_id, upload_id, "PARSING")

    # Determine file type
    ext = os.path.splitext(s3_key)[1].lower()
    try:
        if ext == ".pdf":
            # Need bucket name for async Textract — resolve from s3_key context
            if not bucket:
                # S3 event path already has bucket; for direct messages, pull from env
                from boto3.dynamodb.conditions import Attr
                upload_item_result = UPLOADS_TABLE.get_item(Key={"userId": user_id, "uploadId": upload_id})
                bucket = os.environ.get("RESUMES_BUCKET_NAME", "")
            extracted_text = extract_text_async(bucket, s3_key)
        else:
            extracted_text = extract_text_sync(bucket, s3_key)
    except Exception as e:
        print(f"Textract error: {e}")
        PARSE_JOBS_TABLE.update_item(
            Key={"parseJobId": parse_job_id},
            UpdateExpression="SET #s = :s, errorMessage = :e",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "FAILED", ":e": str(e)},
        )
        update_upload_status(user_id, upload_id, "FAILED")
        raise

    if len(extracted_text.strip()) < 50:
        raise ValueError("Extracted text is too short — file may be empty or unreadable")

    # Store extracted text in S3
    output_key = f"parsed/{user_id}/{upload_id}/text.json"
    s3.put_object(
        Bucket=PARSED_OUTPUT_BUCKET,
        Key=output_key,
        Body=json.dumps({"uploadId": upload_id, "userId": user_id, "text": extracted_text}),
        ContentType="application/json",
    )

    PARSE_JOBS_TABLE.update_item(
        Key={"parseJobId": parse_job_id},
        UpdateExpression="SET #s = :s, outputKey = :k, completedAt = :t, charCount = :c",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "COMPLETE",
            ":k": output_key,
            ":t": datetime.now(timezone.utc).isoformat(),
            ":c": len(extracted_text),
        },
    )
    update_upload_status(user_id, upload_id, "ANALYZING")

    sqs.send_message(
        QueueUrl=ANALYSIS_QUEUE_URL,
        MessageBody=json.dumps({
            "parseJobId": parse_job_id,
            "uploadId": upload_id,
            "userId": user_id,
            "parsedTextKey": output_key,
        }),
    )
    print(f"Parsing complete: parseJobId={parse_job_id} uploadId={upload_id} chars={len(extracted_text)}")


def handler(event, context):
    for record in event.get("Records", []):
        try:
            process_record(record)
        except Exception as e:
            print(f"Failed to process record: {e}")
            raise  # Re-raise to allow SQS retry / DLQ routing
