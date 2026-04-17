"""Auth Service — register, verify OTP, login, refresh, logout."""
import json
import os
import uuid
from datetime import datetime, timezone

import boto3

cognito = boto3.client("cognito-idp")
dynamodb = boto3.resource("dynamodb")

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
        # Mark user as verified in DynamoDB
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


def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return respond(200, {})

    path = event.get("path", "")
    body = json.loads(event.get("body") or "{}")
    auth_header = event.get("headers", {}).get("Authorization", "")
    access_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""

    if "/register" in path:
        return register(body)
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

    return respond(404, {"error": "Not found"})
