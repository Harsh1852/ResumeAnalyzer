"""
Re-triggers any stuck/pending resumes that are not already in-flight in SQS.

Logic:
  - Scans uploads table for anything not COMPLETE or FAILED
  - If a COMPLETE parse job exists for that upload -> sends to AnalysisQueue
  - If no parse job (or parse job failed) -> sends to ParseQueue to restart from scratch
  - Prints queue depths before sending so you can see if messages are already in-flight
"""
import boto3
import json
from boto3.dynamodb.conditions import Key

REGION  = "us-east-1"
ACCOUNT = "307711586938"

dynamodb = boto3.resource("dynamodb", region_name=REGION)
sqs      = boto3.client("sqs", region_name=REGION)

uploads_table    = dynamodb.Table("resume-analyzer-uploads")
parse_jobs_table = dynamodb.Table("resume-analyzer-parse-jobs")

parse_queue_url    = f"https://sqs.{REGION}.amazonaws.com/{ACCOUNT}/resume-analyzer-parse-queue"
analysis_queue_url = f"https://sqs.{REGION}.amazonaws.com/{ACCOUNT}/resume-analyzer-analysis-queue"

TERMINAL_STATUSES = {"COMPLETE", "FAILED"}


def get_queue_depth(queue_url: str) -> int:
    attrs = sqs.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"],
    )["Attributes"]
    return int(attrs["ApproximateNumberOfMessages"]) + int(attrs["ApproximateNumberOfMessagesNotVisible"])


def scan_all(table, filter_expr, expr_names, expr_values):
    """Paginate through all DynamoDB scan results."""
    items, kwargs = [], {
        "FilterExpression": filter_expr,
        "ExpressionAttributeNames": expr_names,
        "ExpressionAttributeValues": expr_values,
    }
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return items


def get_parse_job(upload_id: str):
    """Return the most recent parse job for an upload, or None."""
    result = parse_jobs_table.query(
        IndexName="uploadId-index",
        KeyConditionExpression=Key("uploadId").eq(upload_id),
    )
    items = result.get("Items", [])
    return items[0] if items else None


# ── Find all stuck uploads ────────────────────────────────────────────────────
print("Scanning uploads table for stuck/pending resumes...")
stuck = scan_all(
    uploads_table,
    "#s <> :c AND #s <> :f",
    {"#s": "status"},
    {":c": "COMPLETE", ":f": "FAILED"},
)

if not stuck:
    print("No stuck uploads found — everything looks good.")
    exit(0)

print(f"Found {len(stuck)} non-terminal upload(s): {[u['status'] for u in stuck]}")

parse_depth    = get_queue_depth(parse_queue_url)
analysis_depth = get_queue_depth(analysis_queue_url)
print(f"ParseQueue depth: {parse_depth}  |  AnalysisQueue depth: {analysis_depth}\n")

sent_analysis = sent_parse = skipped = 0

for upload in stuck:
    upload_id = upload["uploadId"]
    user_id   = upload["userId"]
    status    = upload["status"]
    s3_key    = upload.get("s3Key", "")

    parse_job = get_parse_job(upload_id)

    if parse_job and parse_job.get("status") == "COMPLETE":
        # Text already extracted — re-trigger AI analysis only
        sqs.send_message(
            QueueUrl=analysis_queue_url,
            MessageBody=json.dumps({
                "parseJobId":    parse_job["parseJobId"],
                "uploadId":      upload_id,
                "userId":        user_id,
                "parsedTextKey": parse_job["outputKey"],
            }),
        )
        print(f"  -> AnalysisQueue | uploadId={upload_id}  status={status}")
        sent_analysis += 1
    else:
        # No complete parse job — restart from parsing
        if not s3_key:
            print(f"  SKIP (no s3Key)  | uploadId={upload_id}  status={status}")
            skipped += 1
            continue
        sqs.send_message(
            QueueUrl=parse_queue_url,
            MessageBody=json.dumps({
                "uploadId": upload_id,
                "userId":   user_id,
                "s3Key":    s3_key,
                "source":   "retrigger",
            }),
        )
        print(f"  -> ParseQueue     | uploadId={upload_id}  status={status}")
        sent_parse += 1

print(f"\nDone — {sent_analysis} sent to AnalysisQueue, {sent_parse} sent to ParseQueue, {skipped} skipped.")
print("Check the dashboard in ~1-2 minutes.")
