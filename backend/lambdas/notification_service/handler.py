"""
Notification Service — SQS-triggered.
Sends an SES email to the user when their resume analysis is complete.
"""
import json
import os

import boto3

ses = boto3.client("ses")

FROM_ADDRESS = os.environ.get("SES_FROM_ADDRESS", "noreply@example.com")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://example.com")


EMAIL_TEMPLATE = """
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
  <h2 style="color: #2563eb;">Your Resume Analysis is Ready!</h2>
  <p>Hi there,</p>
  <p>Great news — we've finished analyzing your resume. Here's a quick snapshot:</p>
  <div style="background: #f0f9ff; border-left: 4px solid #2563eb; padding: 16px; margin: 20px 0;">
    <p style="margin: 0;"><strong>Resume Score:</strong> {resume_score}/100</p>
    <p style="margin: 8px 0 0;"><strong>Top Match:</strong> {top_role}</p>
  </div>
  <p>View your full report including job search strategies and target companies:</p>
  <a href="{report_url}"
     style="display: inline-block; background: #2563eb; color: white; padding: 12px 24px;
            text-decoration: none; border-radius: 6px; margin: 8px 0;">
    View Full Report
  </a>
  <hr style="margin: 30px 0; border: none; border-top: 1px solid #e5e7eb;">
  <p style="color: #6b7280; font-size: 12px;">Resume Analyzer — Cloud Computing Project</p>
</body>
</html>
"""


def send_email(to_address: str, resume_score: int, top_role: str, result_id: str):
    report_url = f"{FRONTEND_URL}/results/{result_id}"
    html_body = EMAIL_TEMPLATE.format(
        resume_score=resume_score,
        top_role=top_role,
        report_url=report_url,
    )
    ses.send_email(
        Source=FROM_ADDRESS,
        Destination={"ToAddresses": [to_address]},
        Message={
            "Subject": {"Data": "Your Resume Analysis is Ready", "Charset": "UTF-8"},
            "Body": {
                "Html": {"Data": html_body, "Charset": "UTF-8"},
                "Text": {
                    "Data": f"Your resume score: {resume_score}/100. Top role: {top_role}. View report: {report_url}",
                    "Charset": "UTF-8",
                },
            },
        },
    )


def process_record(record: dict):
    body = json.loads(record["body"])
    if "Message" in body:
        body = json.loads(body["Message"])

    user_id = body.get("userId", "")
    analysis = body.get("analysis", {})
    upload_id = body.get("uploadId", "")

    # Try to find the user's email from the analysis or a secondary lookup
    # The analysis doesn't contain email — we need it from UsersTable.
    # For simplicity, if email is not available, we skip (SES requires verified address in sandbox).
    user_email = body.get("userEmail")
    if not user_email:
        # Attempt to look up email from UsersTable
        dynamodb = boto3.resource("dynamodb")
        users_table_name = os.environ.get("USERS_TABLE_NAME")
        if users_table_name:
            table = dynamodb.Table(users_table_name)
            result = table.get_item(Key={"userId": user_id})
            user_email = result.get("Item", {}).get("email")

    if not user_email:
        print(f"No email found for userId={user_id}, skipping notification")
        return

    resume_score = analysis.get("resume_score", 0)
    top_roles = analysis.get("top_roles", [])
    top_role = top_roles[0]["title"] if top_roles else "Unknown"

    # resultId is set by the results worker after it processes this same SNS message
    # Since both workers consume from the same SNS topic, ordering isn't guaranteed.
    # We store uploadId and let the frontend resolve resultId via polling.
    result_id = body.get("resultId", upload_id)

    try:
        send_email(user_email, resume_score, top_role, result_id)
        print(f"Email sent to {user_email} for uploadId={upload_id}")
    except ses.exceptions.MessageRejected as e:
        print(f"SES rejected email: {e}")
    except Exception as e:
        print(f"Failed to send email: {e}")
        raise


def handler(event, context):
    for record in event.get("Records", []):
        try:
            process_record(record)
        except Exception as e:
            print(f"Notification failed: {e}")
            # Don't re-raise for notification failures — we don't want to block the pipeline
