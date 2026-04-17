"""
Student 3 — Microservice 5: Results Service
Aggregates AI analysis into structured report records, exposes read API,
and updates upload status to COMPLETE.
"""
import os
from aws_cdk import (
    Stack, RemovalPolicy, Duration, CfnOutput,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_lambda_event_sources as lambda_events,
    aws_apigateway as apigw,
    aws_sqs as sqs,
)
from constructs import Construct

LAMBDA_DIR = os.path.join(os.path.dirname(__file__), "..", "lambdas")


class ResultsStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str,
        results_queue: sqs.Queue,
        uploads_table: dynamodb.Table,
        user_pool,  # aws_cognito.UserPool passed from AuthStack
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Results Table (PK: userId, SK: resultId) ──
        self.results_table = dynamodb.Table(
            self, "ResultsTable",
            table_name="resume-analyzer-results",
            partition_key=dynamodb.Attribute(name="userId", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="resultId", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.results_table.add_global_secondary_index(
            index_name="uploadId-index",
            partition_key=dynamodb.Attribute(name="uploadId", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )
        self.results_table.add_global_secondary_index(
            index_name="resultId-index",
            partition_key=dynamodb.Attribute(name="resultId", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # ── Results Worker Lambda (SQS-triggered) ──
        self.results_worker_lambda = lambda_.Function(
            self, "ResultsWorkerLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.worker_handler",
            code=lambda_.Code.from_asset(os.path.join(LAMBDA_DIR, "results_service")),
            timeout=Duration.seconds(60),
            environment={
                "RESULTS_TABLE_NAME": self.results_table.table_name,
                "UPLOADS_TABLE_NAME": uploads_table.table_name,
            },
        )
        self.results_worker_lambda.add_event_source(
            lambda_events.SqsEventSource(results_queue, batch_size=1)
        )
        self.results_table.grant_read_write_data(self.results_worker_lambda)
        uploads_table.grant_read_write_data(self.results_worker_lambda)

        # ── Results API Lambda (HTTP) ──
        self.results_api_lambda = lambda_.Function(
            self, "ResultsAPILambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.api_handler",
            code=lambda_.Code.from_asset(os.path.join(LAMBDA_DIR, "results_service")),
            timeout=Duration.seconds(30),
            environment={
                "RESULTS_TABLE_NAME": self.results_table.table_name,
                "UPLOADS_TABLE_NAME": uploads_table.table_name,
            },
        )
        self.results_table.grant_read_write_data(self.results_api_lambda)
        uploads_table.grant_read_write_data(self.results_api_lambda)

        # ── Own API Gateway (avoids cross-stack cycle with UploadStack) ──
        self.results_api = apigw.RestApi(
            self, "ResultsAPI",
            rest_api_name="resume-analyzer-results-api",
            deploy_options=apigw.StageOptions(stage_name="prod"),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"],
            ),
        )
        authorizer = apigw.CognitoUserPoolsAuthorizer(
            self, "ResultsCognitoAuthorizer",
            cognito_user_pools=[user_pool],
        )
        results_integration = apigw.LambdaIntegration(self.results_api_lambda)
        results_resource = self.results_api.root.add_resource("results")
        results_resource.add_method("GET", results_integration,
                                    authorizer=authorizer,
                                    authorization_type=apigw.AuthorizationType.COGNITO)
        result_id_resource = results_resource.add_resource("{resultId}")
        result_id_resource.add_method(
            "GET", results_integration,
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO)
        result_id_resource.add_method(
            "DELETE", results_integration,
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO)

        CfnOutput(self, "ResultsTableName", value=self.results_table.table_name)
        CfnOutput(self, "ResultsApiUrl", value=self.results_api.url, export_name="ResultsApiUrl")
