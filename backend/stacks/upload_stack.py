"""
Student 1 — Microservice 2: Resume Upload Service
Handles presigned URL generation, upload confirmation, and emits to the parsing pipeline.
"""
import os
from aws_cdk import (
    Stack, RemovalPolicy, Duration, CfnOutput,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_apigateway as apigw,
    aws_s3 as s3,
    aws_sqs as sqs,
    aws_s3_notifications as s3n,
)
from constructs import Construct

LAMBDA_DIR = os.path.join(os.path.dirname(__file__), "..", "lambdas")


class UploadStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, auth_stack, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Uploads Table (PK: userId, SK: uploadId) ──
        self.uploads_table = dynamodb.Table(
            self, "UploadsTable",
            table_name="resume-analyzer-uploads",
            partition_key=dynamodb.Attribute(name="userId", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="uploadId", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.uploads_table.add_global_secondary_index(
            index_name="uploadId-index",
            partition_key=dynamodb.Attribute(name="uploadId", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # ── S3 Resume Bucket ──
        self.resume_bucket = s3.Bucket(
            self, "ResumeBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            cors=[s3.CorsRule(
                allowed_methods=[s3.HttpMethods.PUT, s3.HttpMethods.GET, s3.HttpMethods.HEAD],
                allowed_origins=["*"],
                allowed_headers=["*"],
                max_age=3000,
            )],
        )

        # ── Parse Queue + DLQ ──
        parse_dlq = sqs.Queue(
            self, "ParseDLQ",
            queue_name="resume-analyzer-parse-dlq",
            retention_period=Duration.days(14),
        )
        self.parse_queue = sqs.Queue(
            self, "ParseQueue",
            queue_name="resume-analyzer-parse-queue",
            visibility_timeout=Duration.seconds(360),
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=3, queue=parse_dlq),
        )

        # S3 → SQS notification for every uploaded resume
        self.resume_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.SqsDestination(self.parse_queue),
            s3.NotificationKeyFilter(prefix="uploads/"),
        )

        # ── Upload Lambda ──
        self.upload_lambda = lambda_.Function(
            self, "UploadLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset(os.path.join(LAMBDA_DIR, "upload_service")),
            timeout=Duration.seconds(30),
            environment={
                "RESUMES_BUCKET_NAME": self.resume_bucket.bucket_name,
                "UPLOADS_TABLE_NAME": self.uploads_table.table_name,
                "PARSE_QUEUE_URL": self.parse_queue.queue_url,
                "PRESIGNED_URL_EXPIRY_SECONDS": "300",
            },
        )
        self.uploads_table.grant_read_write_data(self.upload_lambda)
        self.resume_bucket.grant_read_write(self.upload_lambda)
        self.parse_queue.grant_send_messages(self.upload_lambda)

        # Full pipeline cleanup on upload delete — bucket names resolved at runtime via CloudFormation
        self.upload_lambda.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["cloudformation:DescribeStacks"],
            resources=["*"],
        ))
        self.upload_lambda.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["s3:DeleteObject", "s3:ListObjectsV2", "s3:DeleteObjects"],
            resources=["*"],
        ))
        self.upload_lambda.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["dynamodb:Query", "dynamodb:DeleteItem"],
            resources=[
                self.format_arn(service="dynamodb", resource="table/resume-analyzer-parse-jobs"),
                self.format_arn(service="dynamodb", resource="table/resume-analyzer-parse-jobs/index/*"),
                self.format_arn(service="dynamodb", resource="table/resume-analyzer-analysis-jobs"),
                self.format_arn(service="dynamodb", resource="table/resume-analyzer-analysis-jobs/index/*"),
            ],
        ))

        # ── App API Gateway (shared by Results stack) ──
        self.app_api = apigw.RestApi(
            self, "AppAPI",
            rest_api_name="resume-analyzer-app-api",
            deploy_options=apigw.StageOptions(stage_name="prod"),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"],
            ),
        )

        self.cognito_authorizer = apigw.CognitoUserPoolsAuthorizer(
            self, "CognitoAuthorizer",
            cognito_user_pools=[auth_stack.user_pool],
            authorizer_name="ResumeAnalyzerAuthorizer",
            identity_source="method.request.header.Authorization",
        )

        upload_integration = apigw.LambdaIntegration(self.upload_lambda)
        uploads = self.app_api.root.add_resource("uploads")
        uploads.add_method("GET", upload_integration,
                           authorizer=self.cognito_authorizer,
                           authorization_type=apigw.AuthorizationType.COGNITO)
        uploads.add_resource("presigned-url").add_method(
            "POST", upload_integration,
            authorizer=self.cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO)
        uploads.add_resource("confirm").add_method(
            "POST", upload_integration,
            authorizer=self.cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO)
        upload_id_resource = uploads.add_resource("{uploadId}")
        upload_id_resource.add_method(
            "GET", upload_integration,
            authorizer=self.cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO)
        upload_id_resource.add_method(
            "DELETE", upload_integration,
            authorizer=self.cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO)
        upload_id_resource.add_resource("view-url").add_method(
            "GET", upload_integration,
            authorizer=self.cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO)

        CfnOutput(self, "AppApiUrl", value=self.app_api.url, export_name="AppApiUrl")
        CfnOutput(self, "ResumeBucketName", value=self.resume_bucket.bucket_name)
