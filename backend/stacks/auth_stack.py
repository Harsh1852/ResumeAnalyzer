"""
Student 1 — Microservice 1: Authentication Service
Handles user registration (Cognito OTP), email verification, login, and token refresh.
"""
import os
from aws_cdk import (
    Stack, RemovalPolicy, Duration, CfnOutput,
    aws_cognito as cognito,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_apigateway as apigw,
    aws_iam as iam,
)
from constructs import Construct

LAMBDA_DIR = os.path.join(os.path.dirname(__file__), "..", "lambdas")


class AuthStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Cognito User Pool (email OTP = Cognito's built-in verification code) ──
        self.user_pool = cognito.UserPool(
            self, "UserPool",
            user_pool_name="resume-analyzer-pool",
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            self_sign_up_enabled=True,
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
                fullname=cognito.StandardAttribute(required=False, mutable=True),
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.user_pool_client = self.user_pool.add_client(
            "WebClient",
            user_pool_client_name="resume-analyzer-web-client",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(user_password=True, user_srp=True),
            access_token_validity=Duration.hours(1),
            id_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(30),
        )

        # ── Users Table ──
        self.users_table = dynamodb.Table(
            self, "UsersTable",
            table_name="resume-analyzer-users",
            partition_key=dynamodb.Attribute(name="userId", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.users_table.add_global_secondary_index(
            index_name="email-index",
            partition_key=dynamodb.Attribute(name="email", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # ── Auth Lambda ──
        self.auth_lambda = lambda_.Function(
            self, "AuthLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset(os.path.join(LAMBDA_DIR, "auth_service")),
            timeout=Duration.seconds(30),
            environment={
                "USER_POOL_ID": self.user_pool.user_pool_id,
                "CLIENT_ID": self.user_pool_client.user_pool_client_id,
                "USERS_TABLE_NAME": self.users_table.table_name,
            },
        )
        self.users_table.grant_read_write_data(self.auth_lambda)

        # Account deletion — access other stacks' resources without circular CDK dependency.
        # Bucket names are resolved at Lambda runtime via CloudFormation SDK.
        self.auth_lambda.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["cloudformation:DescribeStacks"],
            resources=["*"],
        ))
        self.auth_lambda.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["s3:DeleteObject", "s3:ListBucket", "s3:ListObjectsV2"],
            resources=["*"],
        ))
        self.auth_lambda.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["dynamodb:Query", "dynamodb:DeleteItem"],
            resources=[
                self.format_arn(service="dynamodb", resource="table/resume-analyzer-uploads"),
                self.format_arn(service="dynamodb", resource="table/resume-analyzer-uploads/index/*"),
                self.format_arn(service="dynamodb", resource="table/resume-analyzer-results"),
                self.format_arn(service="dynamodb", resource="table/resume-analyzer-results/index/*"),
                self.format_arn(service="dynamodb", resource="table/resume-analyzer-parse-jobs"),
                self.format_arn(service="dynamodb", resource="table/resume-analyzer-parse-jobs/index/*"),
                self.format_arn(service="dynamodb", resource="table/resume-analyzer-analysis-jobs"),
                self.format_arn(service="dynamodb", resource="table/resume-analyzer-analysis-jobs/index/*"),
            ],
        ))

        self.auth_lambda.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "cognito-idp:SignUp",
                "cognito-idp:ConfirmSignUp",
                "cognito-idp:InitiateAuth",
                "cognito-idp:ResendConfirmationCode",
                "cognito-idp:GlobalSignOut",
                "cognito-idp:GetUser",
                "cognito-idp:ForgotPassword",
                "cognito-idp:ConfirmForgotPassword",
                "cognito-idp:ChangePassword",
                "cognito-idp:UpdateUserAttributes",
                "cognito-idp:VerifyUserAttribute",
                "cognito-idp:DeleteUser",
            ],
            resources=[self.user_pool.user_pool_arn],
        ))

        # ── Auth API Gateway (public — no authorizer) ──
        self.auth_api = apigw.RestApi(
            self, "AuthAPI",
            rest_api_name="resume-analyzer-auth-api",
            deploy_options=apigw.StageOptions(stage_name="prod"),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"],
            ),
        )
        auth_resource = self.auth_api.root.add_resource("auth")
        auth_integration = apigw.LambdaIntegration(self.auth_lambda)
        for route in [
            "register", "verify", "resend-otp", "login", "refresh", "logout",
            "forgot-password", "confirm-forgot-password",
            "change-password", "update-email", "verify-email-change", "delete-account",
        ]:
            auth_resource.add_resource(route).add_method("POST", auth_integration)

        CfnOutput(self, "AuthApiUrl", value=self.auth_api.url, export_name="AuthApiUrl")
        CfnOutput(self, "UserPoolId", value=self.user_pool.user_pool_id, export_name="UserPoolId")
        CfnOutput(self, "UserPoolClientId", value=self.user_pool_client.user_pool_client_id, export_name="UserPoolClientId")
