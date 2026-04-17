"""
Parser Service — SQS-triggered.
Extracts text from resumes using pypdf (PDFs) or Textract (images),
stores result in S3, updates DynamoDB, forwards to AnalysisQueue.
"""
import io
import json
import os
import uuid
from datetime import datetime, timezone

import boto3
import pypdf
from boto3.dynamodb.conditions import Key

s3 = boto3.client("s3")
sqs = boto3.client("sqs")
dynamodb = boto3.resource("dynamodb")

PARSED_OUTPUT_BUCKET = os.environ["PARSED_OUTPUT_BUCKET"]
PARSE_JOBS_TABLE = dynamodb.Table(os.environ["PARSE_JOBS_TABLE"])
UPLOADS_TABLE = dynamodb.Table(os.environ["UPLOADS_TABLE"])
ANALYSIS_QUEUE_URL = os.environ["ANALYSIS_QUEUE_URL"]
RESUMES_BUCKET = os.environ["RESUMES_BUCKET"]


def update_upload_status(user_id: str, upload_id: str, status: str):
    UPLOADS_TABLE.update_item(
        Key={"userId": user_id, "uploadId": upload_id},
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": status},
    )


def extract_text_from_pdf(bucket: str, key: str) -> str:
    obj = s3.get_object(Bucket=bucket, Key=key)
    pdf_bytes = obj["Body"].read()
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)
    return "\n".join(parts)


def extract_text_from_image(bucket: str, key: str) -> str:
    textract = boto3.client("textract")
    res = textract.detect_document_text(
        Document={"S3Object": {"Bucket": bucket, "Name": key}}
    )
    lines = [b["Text"] for b in res["Blocks"] if b["BlockType"] == "LINE"]
    return "\n".join(lines)


def process_record(record: dict):
    body = json.loads(record["body"])

    # S3 event notification has a different shape than our direct SQS message
    if "Records" in body:
        s3_record = body["Records"][0]["s3"]
        bucket = s3_record["bucket"]["name"]
        s3_key = s3_record["object"]["key"]
        parts = s3_key.split("/")
        user_id = parts[1] if len(parts) > 2 else "unknown"
        upload_id = parts[2] if len(parts) > 3 else "unknown"
    else:
        upload_id = body["uploadId"]
        user_id = body["userId"]
        s3_key = body["s3Key"]
        bucket = RESUMES_BUCKET

    # Idempotency check
    existing = PARSE_JOBS_TABLE.query(
        IndexName="uploadId-index",
        KeyConditionExpression=Key("uploadId").eq(upload_id),
    )
    if existing["Items"]:
        status = existing["Items"][0].get("status")
        if status in ("COMPLETE", "PROCESSING"):
            print(f"Skipping duplicate: uploadId={upload_id} status={status}")
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

    ext = os.path.splitext(s3_key)[1].lower()
    try:
        if ext == ".pdf":
            extracted_text = extract_text_from_pdf(bucket, s3_key)
        else:
            extracted_text = extract_text_from_image(bucket, s3_key)
    except Exception as e:
        print(f"Extraction error: {e}")
        PARSE_JOBS_TABLE.update_item(
            Key={"parseJobId": parse_job_id},
            UpdateExpression="SET #s = :s, errorMessage = :e",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "FAILED", ":e": str(e)},
        )
        update_upload_status(user_id, upload_id, "FAILED")
        raise

    if len(extracted_text.strip()) < 50:
        raise ValueError("Extracted text too short — file may be empty or unreadable")

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
    print(f"Parsing complete: parseJobId={parse_job_id} chars={len(extracted_text)}")


def handler(event, context):
    for record in event.get("Records", []):
        try:
            process_record(record)
        except Exception as e:
            print(f"Failed to process record: {e}")
            raise
