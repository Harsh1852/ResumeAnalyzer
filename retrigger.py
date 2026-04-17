# save as retrigger.py and run with: python retrigger.py
import boto3
import json

dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
sqs = boto3.client("sqs", region_name="us-east-1")

parse_jobs_table = dynamodb.Table("resume-analyzer-parse-jobs")
analysis_queue_url = "https://sqs.us-east-1.amazonaws.com/307711586938/resume-analyzer-analysis-queue"

# Find all successfully parsed jobs
result = parse_jobs_table.scan(
    FilterExpression="#s = :s",
    ExpressionAttributeNames={"#s": "status"},
    ExpressionAttributeValues={":s": "COMPLETE"},
)

items = result["Items"]
print(f"Found {len(items)} parsed resumes to re-trigger")

for item in items:
    sqs.send_message(
        QueueUrl=analysis_queue_url,
        MessageBody=json.dumps({
            "parseJobId": item["parseJobId"],
            "uploadId": item["uploadId"],
            "userId": item["userId"],
            "parsedTextKey": item["outputKey"],
        }),
    )
    print(f"Re-triggered: uploadId={item['uploadId']}")

print("Done — check dashboard in ~1 minute")
