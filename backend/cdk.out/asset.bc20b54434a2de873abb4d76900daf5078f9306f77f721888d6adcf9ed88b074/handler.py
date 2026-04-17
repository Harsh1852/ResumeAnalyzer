"""Auth Service — register, verify OTP, login, refresh, logout, profile."""
import json
import os
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key as DynamoKey

cognito = boto3.client("cognito-idp")
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
cfn = boto3.client("cloudformation")

USER_POOL_ID = os.environ["USER_POOL_ID"]
CLIENT_ID = os.environ["CLIENT_ID"]
USERS_TABLE = dynamodb.Table(os.environ["USERS_TABLE_NAME"])


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


def register(body: dict) -> dict:
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    name = body.get("name", "").strip()

    if not email or not password:
        return respond(400, {"error": "email and password are required"})

    try:
        res = cognito.sign_up(
            ClientId=CLIENT_ID,
            Username=email,
            Password=password,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "name", "Value": name},
            ],
        )
        user_id = res["UserSub"]
        USERS_TABLE.put_item(Item={
            "userId": user_id,
            "email": email,
            "name": name,
            "status": "PENDING",
            "createdAt": datetime.now(timezone.utc).isoformat(),
        })
        return respond(201, {
            "message": "Registration successful. Check your email for the 6-digit verification code.",
            "userId": user_id,
        })
    except cognito.exceptions.UsernameExistsException:
        return respond(409, {"error": "An account with this email already exists"})
    except cognito.exceptions.InvalidPasswordException as e:
        return respond(400, {"error": str(e)})
    except Exception as e:
        print(f"register error: {e}")
        return respond(500, {"error": "Internal server error"})


def verify_otp(body: dict) -> dict:
    email = body.get("email", "").strip().lower()
    code = body.get("code", "").strip()

    if not email or not code:
        return respond(400, {"error": "email and code are required"})

    try:
        cognito.confirm_sign_up(ClientId=CLIENT_ID, Username=email, ConfirmationCode=code)
        result = USERS_TABLE.query(
            IndexName="email-index",
            KeyConditionExpression="email = :e",
            ExpressionAttributeValues={":e": email},
        )
        if result["Items"]:
            USERS_TABLE.update_item(
                Key={"userId": result["Items"][0]["userId"]},
                UpdateExpression="SET #s = :s",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":s": "VERIFIED"},
            )
        return respond(200, {"message": "Email verified successfully. You can now log in."})
    except cognito.exceptions.CodeMismatchException:
        return respond(400, {"error": "Invalid verification code"})
    except cognito.exceptions.ExpiredCodeException:
        return respond(400, {"error": "Verification code has expired. Request a new one."})
    except cognito.exceptions.NotAuthorizedException:
        return respond(400, {"error": "User is already confirmed"})
    except Exception as e:
        print(f"verify_otp error: {e}")
        return respond(500, {"error": "Internal server error"})


def resend_otp(body: dict) -> dict:
    email = body.get("email", "").strip().lower()
    if not email:
        return respond(400, {"error": "email is required"})
    try:
        cognito.resend_confirmation_code(ClientId=CLIENT_ID, Username=email)
        return respond(200, {"message": "Verification code resent to your email"})
    except cognito.exceptions.UserNotFoundException:
        return respond(404, {"error": "No account found with this email"})
    except Exception as e:
        print(f"resend_otp error: {e}")
        return respond(500, {"error": "Internal server error"})


def login(body: dict) -> dict:
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")

    if not email or not password:
        return respond(400, {"error": "email and password are required"})

    try:
        res = cognito.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            ClientId=CLIENT_ID,
            AuthParameters={"USERNAME": email, "PASSWORD": password},
        )
        auth = res["AuthenticationResult"]
        return respond(200, {
            "accessToken": auth["AccessToken"],
            "idToken": auth["IdToken"],
            "refreshToken": auth["RefreshToken"],
            "expiresIn": auth["ExpiresIn"],
        })
    except cognito.exceptions.NotAuthorizedException:
        return respond(401, {"error": "Incorrect email or password"})
    except cognito.exceptions.UserNotConfirmedException:
        return respond(403, {"error": "Please verify your email before logging in"})
    except cognito.exceptions.UserNotFoundException:
        return respond(401, {"error": "Incorrect email or password"})
    except Exception as e:
        print(f"login error: {e}")
        return respond(500, {"error": "Internal server error"})


def refresh(body: dict) -> dict:
    refresh_token = body.get("refreshToken", "")
    if not refresh_token:
        return respond(400, {"error": "refreshToken is required"})
    try:
        res = cognito.initiate_auth(
            AuthFlow="REFRESH_TOKEN_AUTH",
            ClientId=CLIENT_ID,
            AuthParameters={"REFRESH_TOKEN": refresh_token},
        )
        auth = res["AuthenticationResult"]
        return respond(200, {
            "accessToken": auth["AccessToken"],
            "idToken": auth["IdToken"],
            "expiresIn": auth["ExpiresIn"],
        })
    except Exception as e:
        print(f"refresh error: {e}")
        return respond(401, {"error": "Invalid or expired refresh token"})


def logout(body: dict, access_token: str) -> dict:
    token = access_token or body.get("accessToken", "")
    if not token:
        return respond(400, {"error": "accessToken is required"})
    try:
        cognito.global_sign_out(AccessToken=token)
        return respond(200, {"message": "Logged out successfully"})
    except Exception as e:
        print(f"logout error: {e}")
        return respond(500, {"error": "Internal server error"})


def forgot_password(body: dict) -> dict:
    email = body.get("email", "").strip().lower()
    if not email:
        return respond(400, {"error": "email is required"})
    try:
        cognito.forgot_password(ClientId=CLIENT_ID, Username=email)
        return respond(200, {"message": "Password reset code sent to your email"})
    except cognito.exceptions.UserNotFoundException:
        return respond(404, {"error": "No account found with this email"})
    except cognito.exceptions.InvalidParameterException:
        return respond(400, {"error": "Account email is not verified. Please contact support."})
    except Exception as e:
        print(f"forgot_password error: {e}")
        return respond(500, {"error": "Internal server error"})


def confirm_forgot_password(body: dict) -> dict:
    email = body.get("email", "").strip().lower()
    code = body.get("code", "").strip()
    new_password = body.get("newPassword", "")
    if not email or not code or not new_password:
        return respond(400, {"error": "email, code, and newPassword are required"})
    try:
        cognito.confirm_forgot_password(
            ClientId=CLIENT_ID,
            Username=email,
            ConfirmationCode=code,
            Password=new_password,
        )
        return respond(200, {"message": "Password reset successfully. You can now log in."})
    except cognito.exceptions.CodeMismatchException:
        return respond(400, {"error": "Invalid reset code"})
    except cognito.exceptions.ExpiredCodeException:
        return respond(400, {"error": "Reset code has expired. Request a new one."})
    except cognito.exceptions.InvalidPasswordException as e:
        return respond(400, {"error": str(e)})
    except Exception as e:
        print(f"confirm_forgot_password error: {e}")
        return respond(500, {"error": "Internal server error"})


def change_password(body: dict, access_token: str) -> dict:
    current = body.get("currentPassword", "")
    new_pwd = body.get("newPassword", "")
    if not access_token:
        return respond(401, {"error": "Authentication required"})
    if not current or not new_pwd:
        return respond(400, {"error": "currentPassword and newPassword are required"})
    try:
        cognito.change_password(
            PreviousPassword=current,
            ProposedPassword=new_pwd,
            AccessToken=access_token,
        )
        return respond(200, {"message": "Password changed successfully"})
    except cognito.exceptions.NotAuthorizedException:
        return respond(401, {"error": "Incorrect current password"})
    except cognito.exceptions.InvalidPasswordException as e:
        return respond(400, {"error": str(e)})
    except Exception as e:
        print(f"change_password error: {e}")
        return respond(500, {"error": "Internal server error"})


def update_email(body: dict, access_token: str) -> dict:
    new_email = body.get("newEmail", "").strip().lower()
    if not access_token:
        return respond(401, {"error": "Authentication required"})
    if not new_email:
        return respond(400, {"error": "newEmail is required"})
    try:
        cognito.update_user_attributes(
            AccessToken=access_token,
            UserAttributes=[{"Name": "email", "Value": new_email}],
        )
        return respond(200, {"message": "Verification code sent to your new email"})
    except cognito.exceptions.AliasExistsException:
        return respond(409, {"error": "An account with this email already exists"})
    except Exception as e:
        print(f"update_email error: {e}")
        return respond(500, {"error": "Internal server error"})


def verify_email_change(body: dict, access_token: str) -> dict:
    code = body.get("code", "").strip()
    if not access_token:
        return respond(401, {"error": "Authentication required"})
    if not code:
        return respond(400, {"error": "code is required"})
    try:
        cognito.verify_user_attribute(
            AccessToken=access_token,
            AttributeName="email",
            Code=code,
        )
        # Update DynamoDB with new email
        try:
            user_info = cognito.get_user(AccessToken=access_token)
            new_email = next((a["Value"] for a in user_info["UserAttributes"] if a["Name"] == "email"), None)
            user_id = next((a["Value"] for a in user_info["UserAttributes"] if a["Name"] == "sub"), None)
            if new_email and user_id:
                USERS_TABLE.update_item(
                    Key={"userId": user_id},
                    UpdateExpression="SET email = :e",
                    ExpressionAttributeValues={":e": new_email},
                )
        except Exception as e:
            print(f"DynamoDB email update warning: {e}")
        return respond(200, {"message": "Email updated successfully. Please log in again with your new email."})
    except cognito.exceptions.CodeMismatchException:
        return respond(400, {"error": "Invalid verification code"})
    except cognito.exceptions.ExpiredCodeException:
        return respond(400, {"error": "Verification code has expired"})
    except Exception as e:
        print(f"verify_email_change error: {e}")
        return respond(500, {"error": "Internal server error"})


def _get_bucket_names():
    """Look up bucket names from CloudFormation outputs at runtime to avoid circular CDK dependencies."""
    resume_bucket, analysis_bucket = "", ""
    try:
        outputs = {o["OutputKey"]: o["OutputValue"]
                   for o in cfn.describe_stacks(StackName="ResumeAnalyzerUpload")["Stacks"][0].get("Outputs", [])}
        resume_bucket = outputs.get("ResumeBucketName", "")
    except Exception as e:
        print(f"Could not get resume bucket: {e}")
    try:
        outputs = {o["OutputKey"]: o["OutputValue"]
                   for o in cfn.describe_stacks(StackName="ResumeAnalyzerAnalyzer")["Stacks"][0].get("Outputs", [])}
        analysis_bucket = outputs.get("AnalysisResultsBucketName", "")
    except Exception as e:
        print(f"Could not get analysis bucket: {e}")
    return resume_bucket, analysis_bucket


def _delete_s3_prefix(bucket, prefix):
    """Delete all S3 objects under a prefix."""
    if not bucket or not prefix:
        return
    try:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            objects = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
            if objects:
                s3.delete_objects(Bucket=bucket, Delete={"Objects": objects})
    except Exception as e:
        print(f"S3 prefix delete warning ({bucket}/{prefix}): {e}")


def delete_account(access_token: str) -> dict:
    if not access_token:
        return respond(401, {"error": "Authentication required"})
    try:
        user_info = cognito.get_user(AccessToken=access_token)
        user_id = next((a["Value"] for a in user_info["UserAttributes"] if a["Name"] == "sub"), None)
        if not user_id:
            return respond(500, {"error": "Could not determine user ID"})

        resume_bucket, analysis_bucket = _get_bucket_names()

        # Delete all uploads (S3 files + DynamoDB records), collect uploadIds for job cleanup
        uploads_table = dynamodb.Table("resume-analyzer-uploads")
        analysis_jobs_table = dynamodb.Table("resume-analyzer-analysis-jobs")
        response = uploads_table.query(KeyConditionExpression=DynamoKey("userId").eq(user_id))
        for item in response.get("Items", []):
            upload_id = item["uploadId"]
            s3_key = item.get("s3Key", "")
            if s3_key and resume_bucket:
                try:
                    s3.delete_object(Bucket=resume_bucket, Key=s3_key)
                except Exception as e:
                    print(f"S3 resume delete warning: {e}")
            uploads_table.delete_item(Key={"userId": user_id, "uploadId": upload_id})
            # Delete analysis job records linked to this upload via uploadId-index GSI
            try:
                jobs = analysis_jobs_table.query(
                    IndexName="uploadId-index",
                    KeyConditionExpression=DynamoKey("uploadId").eq(upload_id),
                )
                for job in jobs.get("Items", []):
                    analysis_jobs_table.delete_item(Key={"analysisJobId": job["analysisJobId"]})
            except Exception as e:
                print(f"Analysis job delete warning for uploadId={upload_id}: {e}")

        # Delete all analysis result JSON files from S3 by prefix
        _delete_s3_prefix(analysis_bucket, f"analysis/{user_id}/")

        # Delete all result records
        results_table = dynamodb.Table("resume-analyzer-results")
        response = results_table.query(KeyConditionExpression=DynamoKey("userId").eq(user_id))
        for item in response.get("Items", []):
            results_table.delete_item(Key={"userId": user_id, "resultId": item["resultId"]})

        # Delete Cognito user and users table record
        cognito.delete_user(AccessToken=access_token)
        USERS_TABLE.delete_item(Key={"userId": user_id})

        print(f"Account fully deleted: userId={user_id}")
        return respond(200, {"message": "Account deleted successfully"})
    except Exception as e:
        print(f"delete_account error: {e}")
        return respond(500, {"error": "Internal server error"})


def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return respond(200, {})

    path = event.get("path", "")
    body = json.loads(event.get("body") or "{}")
    auth_header = event.get("headers", {}).get("Authorization", "")
    access_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""

    if "/register" in path:
        return register(body)
    if "/verify-email-change" in path:
        return verify_email_change(body, access_token)
    if "/verify" in path:
        return verify_otp(body)
    if "/resend-otp" in path:
        return resend_otp(body)
    if "/login" in path:
        return login(body)
    if "/refresh" in path:
        return refresh(body)
    if "/logout" in path:
        return logout(body, access_token)
    if "/forgot-password" in path:
        return forgot_password(body)
    if "/confirm-forgot-password" in path:
        return confirm_forgot_password(body)
    if "/change-password" in path:
        return change_password(body, access_token)
    if "/update-email" in path:
        return update_email(body, access_token)
    if "/delete-account" in path:
        return delete_account(access_token)

    return respond(404, {"error": "Not found"})
