"""
Student 2 — Microservice 3: Resume Parser Service
Consumes S3 upload events from ParseQueue, calls Amazon Textract to extract text,
stores results in S3, and forwards to the AnalysisQueue.
"""
import os
from aws_cdk import (
    Stack, RemovalPolicy, Duration, CfnOutput,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_lambda_event_sources as lambda_events,
    aws_s3 as s3,
    aws_sqs as sqs,
    aws_iam as iam,
)
from constructs import Construct

LAMBDA_DIR = os.path.join(os.path.dirname(__file__), "..", "lambdas")


class ParserStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str,
        parse_queue: sqs.Queue,
        resume_bucket: s3.Bucket,
        uploads_table: dynamodb.Table,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Parsed Output Bucket ──
        self.parsed_output_bucket = s3.Bucket(
            self, "ParsedOutputBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # ── Parse Jobs Table ──
        self.parse_jobs_table = dynamodb.Table(
            self, "ParseJobsTable",
            table_name="resume-analyzer-parse-jobs",
            partition_key=dynamodb.Attribute(name="parseJobId", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.parse_jobs_table.add_global_secondary_index(
            index_name="uploadId-index",
            partition_key=dynamodb.Attribute(name="uploadId", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # ── Analysis Queue + DLQ (output of this service) ──
        analysis_dlq = sqs.Queue(
            self, "AnalysisDLQ",
            queue_name="resume-analyzer-analysis-dlq",
            retention_period=Duration.days(14),
        )
        self.analysis_queue = sqs.Queue(
            self, "AnalysisQueue",
            queue_name="resume-analyzer-analysis-queue",
            visibility_timeout=Duration.seconds(300),
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=3, queue=analysis_dlq),
        )

        # ── Parser Lambda (SQS-triggered) ──
        self.parser_lambda = lambda_.Function(
            self, "ParserLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset(os.path.join(LAMBDA_DIR, "parser_service")),
            timeout=Duration.seconds(300),
            memory_size=512,
            environment={
                "PARSED_OUTPUT_BUCKET": self.parsed_output_bucket.bucket_name,
                "PARSE_JOBS_TABLE": self.parse_jobs_table.table_name,
                "UPLOADS_TABLE": uploads_table.table_name,
                "ANALYSIS_QUEUE_URL": self.analysis_queue.queue_url,
                "RESUMES_BUCKET": resume_bucket.bucket_name,
            },
        )

        self.parser_lambda.add_event_source(
            lambda_events.SqsEventSource(parse_queue, batch_size=1)
        )

        resume_bucket.grant_read(self.parser_lambda)
        self.parsed_output_bucket.grant_read_write(self.parser_lambda)
        self.parse_jobs_table.grant_read_write_data(self.parser_lambda)
        uploads_table.grant_read_write_data(self.parser_lambda)
        self.analysis_queue.grant_send_messages(self.parser_lambda)

        self.parser_lambda.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "textract:StartDocumentTextDetection",
                "textract:GetDocumentTextDetection",
                "textract:DetectDocumentText",
                "textract:AnalyzeDocument",
            ],
            resources=["*"],
        ))

        CfnOutput(self, "AnalysisQueueUrl", value=self.analysis_queue.queue_url)
        CfnOutput(self, "ParsedOutputBucketName", value=self.parsed_output_bucket.bucket_name)
