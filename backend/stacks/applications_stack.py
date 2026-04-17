"""
Microservice 8: Applications Service
Tracks the user's job applications: statuses, status history, interview rounds,
notes, and aggregate stats. Pure CRUD — no Bedrock, no external APIs.
"""
import os
from aws_cdk import (
    Stack, RemovalPolicy, Duration, CfnOutput,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_apigateway as apigw,
)
from constructs import Construct

LAMBDA_DIR = os.path.join(os.path.dirname(__file__), "..", "lambdas")


class ApplicationsStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str,
        user_pool,  # aws_cognito.UserPool from AuthStack
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Applications Table ──
        # PK: applicationId. GSIs let us list-by-user and filter-by-status efficiently.
        self.applications_table = dynamodb.Table(
            self, "ApplicationsTable",
            table_name="resume-analyzer-applications",
            partition_key=dynamodb.Attribute(name="applicationId", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.applications_table.add_global_secondary_index(
            index_name="userId-index",
            partition_key=dynamodb.Attribute(name="userId", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="createdAt", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )
        self.applications_table.add_global_secondary_index(
            index_name="userId-status-index",
            partition_key=dynamodb.Attribute(name="userId", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="status", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # ── Applications API Lambda ──
        self.applications_api_lambda = lambda_.Function(
            self, "ApplicationsAPILambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.api_handler",
            code=lambda_.Code.from_asset(os.path.join(LAMBDA_DIR, "applications_service")),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "APPLICATIONS_TABLE_NAME": self.applications_table.table_name,
            },
        )
        self.applications_table.grant_read_write_data(self.applications_api_lambda)

        # ── API Gateway ──
        self.applications_api = apigw.RestApi(
            self, "ApplicationsAPI",
            rest_api_name="resume-analyzer-applications-api",
            deploy_options=apigw.StageOptions(stage_name="prod"),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"],
            ),
        )
        authorizer = apigw.CognitoUserPoolsAuthorizer(
            self, "ApplicationsCognitoAuthorizer",
            cognito_user_pools=[user_pool],
        )
        integration = apigw.LambdaIntegration(self.applications_api_lambda)

        def protect(resource, *methods):
            for m in methods:
                resource.add_method(
                    m, integration,
                    authorizer=authorizer,
                    authorization_type=apigw.AuthorizationType.COGNITO,
                )

        # /applications
        apps_root = self.applications_api.root.add_resource("applications")
        protect(apps_root, "GET", "POST")

        # /applications/stats
        apps_stats = apps_root.add_resource("stats")
        protect(apps_stats, "GET")

        # /applications/{applicationId}
        app_by_id = apps_root.add_resource("{applicationId}")
        protect(app_by_id, "GET", "PATCH", "DELETE")

        # /applications/{applicationId}/rounds
        rounds_root = app_by_id.add_resource("rounds")
        protect(rounds_root, "POST")

        # /applications/{applicationId}/rounds/{roundId}
        round_by_id = rounds_root.add_resource("{roundId}")
        protect(round_by_id, "PATCH", "DELETE")

        CfnOutput(self, "ApplicationsTableName", value=self.applications_table.table_name)
        CfnOutput(self, "ApplicationsApiUrl", value=self.applications_api.url, export_name="ApplicationsApiUrl")
