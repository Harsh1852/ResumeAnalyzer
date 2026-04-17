"""
Microservice 7: Jobs Service
Fetches live job listings via Adzuna, recommends courses via Tavily,
and generates tailored resumes via Bedrock with an editable persisted copy.
"""
import os
from aws_cdk import (
    Stack, RemovalPolicy, Duration, CfnOutput,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_apigateway as apigw,
    aws_iam as iam,
)
from constructs import Construct

LAMBDA_DIR = os.path.join(os.path.dirname(__file__), "..", "lambdas")
BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"


class JobsStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str,
        results_table: dynamodb.Table,
        user_pool,  # aws_cognito.UserPool passed from AuthStack
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Jobs Table (PK: jobId; GSI on resultId and userId) ──
        self.jobs_table = dynamodb.Table(
            self, "JobsTable",
            table_name="resume-analyzer-jobs",
            partition_key=dynamodb.Attribute(name="jobId", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.jobs_table.add_global_secondary_index(
            index_name="resultId-index",
            partition_key=dynamodb.Attribute(name="resultId", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )
        self.jobs_table.add_global_secondary_index(
            index_name="userId-index",
            partition_key=dynamodb.Attribute(name="userId", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # ── Tailored Resumes Table (PK: resumeId; GSI on userId and jobId) ──
        self.tailored_resumes_table = dynamodb.Table(
            self, "TailoredResumesTable",
            table_name="resume-analyzer-tailored-resumes",
            partition_key=dynamodb.Attribute(name="resumeId", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.tailored_resumes_table.add_global_secondary_index(
            index_name="userId-index",
            partition_key=dynamodb.Attribute(name="userId", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )
        self.tailored_resumes_table.add_global_secondary_index(
            index_name="jobId-index",
            partition_key=dynamodb.Attribute(name="jobId", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # ── Jobs API Lambda ──
        self.jobs_api_lambda = lambda_.Function(
            self, "JobsAPILambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.api_handler",
            code=lambda_.Code.from_asset(os.path.join(LAMBDA_DIR, "jobs_service")),
            timeout=Duration.seconds(60),
            memory_size=512,
            environment={
                "JOBS_TABLE_NAME": self.jobs_table.table_name,
                "TAILORED_RESUMES_TABLE_NAME": self.tailored_resumes_table.table_name,
                "RESULTS_TABLE_NAME": results_table.table_name,
                "ADZUNA_APP_ID": os.environ.get("ADZUNA_APP_ID", "a9822df2"),
                "ADZUNA_APP_KEY": os.environ.get("ADZUNA_APP_KEY", "4803ef8a0d3f3ef210ed045c47d31c81"),
                "ADZUNA_COUNTRY": os.environ.get("ADZUNA_COUNTRY", "us"),
                "TAVILY_API_KEY": os.environ.get("TAVILY_API_KEY", "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"),
                "BEDROCK_MODEL_ID": BEDROCK_MODEL_ID,
                "BEDROCK_MAX_TOKENS": "4096",
            },
        )

        self.jobs_table.grant_read_write_data(self.jobs_api_lambda)
        self.tailored_resumes_table.grant_read_write_data(self.jobs_api_lambda)
        results_table.grant_read_data(self.jobs_api_lambda)

        self.jobs_api_lambda.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["bedrock:InvokeModel"],
            resources=[
                f"arn:aws:bedrock:{self.region}::foundation-model/{BEDROCK_MODEL_ID}",
            ],
        ))

        # ── API Gateway ──
        self.jobs_api = apigw.RestApi(
            self, "JobsAPI",
            rest_api_name="resume-analyzer-jobs-api",
            deploy_options=apigw.StageOptions(stage_name="prod"),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"],
            ),
        )
        authorizer = apigw.CognitoUserPoolsAuthorizer(
            self, "JobsCognitoAuthorizer",
            cognito_user_pools=[user_pool],
        )
        integration = apigw.LambdaIntegration(self.jobs_api_lambda)

        def protect(resource, *methods):
            for m in methods:
                resource.add_method(
                    m, integration,
                    authorizer=authorizer,
                    authorization_type=apigw.AuthorizationType.COGNITO,
                )

        jobs_root = self.jobs_api.root.add_resource("jobs")
        protect(jobs_root, "GET")  # ?resultId=

        jobs_search = jobs_root.add_resource("search")
        protect(jobs_search, "POST")

        job_by_id = jobs_root.add_resource("{jobId}")
        protect(job_by_id, "GET")

        job_courses = job_by_id.add_resource("courses")
        protect(job_courses, "POST")

        job_tailored_resume = job_by_id.add_resource("tailored-resume")
        protect(job_tailored_resume, "POST")

        tailored_root = self.jobs_api.root.add_resource("tailored-resumes")
        tailored_by_id = tailored_root.add_resource("{resumeId}")
        protect(tailored_by_id, "GET", "PUT")

        CfnOutput(self, "JobsTableName", value=self.jobs_table.table_name)
        CfnOutput(self, "TailoredResumesTableName", value=self.tailored_resumes_table.table_name)
        CfnOutput(self, "JobsApiUrl", value=self.jobs_api.url, export_name="JobsApiUrl")
