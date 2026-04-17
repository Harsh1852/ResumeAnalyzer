"""
Student 3 — Microservice 6: Notification + Frontend Service
Sends email notifications via SES when analysis completes.
Hosts the React frontend on S3 + CloudFront.
"""
import os
from aws_cdk import (
    Stack, RemovalPolicy, Duration, CfnOutput,
    aws_lambda as lambda_,
    aws_lambda_event_sources as lambda_events,
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_iam as iam,
    aws_sqs as sqs,
    aws_cognito as cognito,
)
from constructs import Construct

LAMBDA_DIR = os.path.join(os.path.dirname(__file__), "..", "lambdas")

SES_FROM_ADDRESS = "cloud.neu.6620@gmail.com"


class FrontendStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str,
        notification_queue: sqs.Queue,
        user_pool: cognito.UserPool,
        results_table,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Notification Lambda (SQS-triggered → SES email) ──
        self.notification_lambda = lambda_.Function(
            self, "NotificationLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset(os.path.join(LAMBDA_DIR, "notification_service")),
            timeout=Duration.seconds(30),
            environment={
                "SES_FROM_ADDRESS": SES_FROM_ADDRESS,
                "FRONTEND_URL": "FRONTEND_URL",
                "COGNITO_USER_POOL_ID": user_pool.user_pool_id,
                "RESULTS_TABLE_NAME": results_table.table_name,
            },
        )
        self.notification_lambda.add_event_source(
            lambda_events.SqsEventSource(notification_queue, batch_size=1)
        )
        results_table.grant_read_data(self.notification_lambda)

        self.notification_lambda.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["ses:SendEmail", "ses:SendRawEmail"],
            resources=["*"],
        ))
        self.notification_lambda.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["cognito-idp:AdminGetUser"],
            resources=[user_pool.user_pool_arn],
        ))

        # ── Frontend S3 Bucket ──
        self.frontend_bucket = s3.Bucket(
            self, "FrontendBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # ── CloudFront OAC + Distribution ──
        oac = cloudfront.S3OriginAccessControl(
            self, "OAC",
            description="OAC for Resume Analyzer frontend",
        )

        self.distribution = cloudfront.Distribution(
            self, "Distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(
                    self.frontend_bucket,
                    origin_access_control=oac,
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
            ],
        )

        CfnOutput(self, "FrontendBucketName", value=self.frontend_bucket.bucket_name)
        CfnOutput(self, "CloudFrontUrl", value=f"https://{self.distribution.distribution_domain_name}", export_name="CloudFrontUrl")
        CfnOutput(self, "CloudFrontDistributionId", value=self.distribution.distribution_id)
