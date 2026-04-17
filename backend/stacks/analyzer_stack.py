"""
Student 2 — Microservice 4: AI Analyzer Service
Consumes parsed resume text from AnalysisQueue, invokes Amazon Bedrock (Claude 3 Haiku)
to produce job role matches + strategies, then fans out to Results and Notification queues.
"""
import os
from aws_cdk import (
    Stack, RemovalPolicy, Duration, CfnOutput,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_lambda_event_sources as lambda_events,
    aws_s3 as s3,
    aws_sqs as sqs,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subs,
    aws_iam as iam,
)
from constructs import Construct

LAMBDA_DIR = os.path.join(os.path.dirname(__file__), "..", "lambdas")
BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"


class AnalyzerStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str,
        analysis_queue: sqs.Queue,
        parsed_output_bucket: s3.Bucket,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Analysis Results Bucket ──
        self.analysis_results_bucket = s3.Bucket(
            self, "AnalysisResultsBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # ── Analysis Jobs Table ──
        self.analysis_jobs_table = dynamodb.Table(
            self, "AnalysisJobsTable",
            table_name="resume-analyzer-analysis-jobs",
            partition_key=dynamodb.Attribute(name="analysisJobId", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.analysis_jobs_table.add_global_secondary_index(
            index_name="uploadId-index",
            partition_key=dynamodb.Attribute(name="uploadId", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # ── SNS fan-out → Results queue + Notification queue ──
        self.results_topic = sns.Topic(self, "ResultsTopic", topic_name="resume-analyzer-results-topic")

        results_dlq = sqs.Queue(self, "ResultsDLQ", queue_name="resume-analyzer-results-dlq", retention_period=Duration.days(14))
        self.results_queue = sqs.Queue(
            self, "ResultsQueue",
            queue_name="resume-analyzer-results-queue",
            visibility_timeout=Duration.seconds(120),
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=3, queue=results_dlq),
        )

        notification_dlq = sqs.Queue(self, "NotificationDLQ", queue_name="resume-analyzer-notification-dlq", retention_period=Duration.days(14))
        self.notification_queue = sqs.Queue(
            self, "NotificationQueue",
            queue_name="resume-analyzer-notification-queue",
            visibility_timeout=Duration.seconds(60),
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=3, queue=notification_dlq),
        )

        self.results_topic.add_subscription(sns_subs.SqsSubscription(self.results_queue))
        self.results_topic.add_subscription(sns_subs.SqsSubscription(self.notification_queue))

        # ── Analyzer Lambda (SQS-triggered) ──
        self.analyzer_lambda = lambda_.Function(
            self, "AnalyzerLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset(os.path.join(LAMBDA_DIR, "analyzer_service")),
            timeout=Duration.seconds(120),
            memory_size=512,
            environment={
                "ANALYSIS_RESULTS_BUCKET": self.analysis_results_bucket.bucket_name,
                "ANALYSIS_JOBS_TABLE": self.analysis_jobs_table.table_name,
                "RESULTS_TOPIC_ARN": self.results_topic.topic_arn,
                "PARSED_OUTPUT_BUCKET": parsed_output_bucket.bucket_name,
                "BEDROCK_MODEL_ID": BEDROCK_MODEL_ID,
                "BEDROCK_MAX_TOKENS": "4096",
            },
        )

        self.analyzer_lambda.add_event_source(
            lambda_events.SqsEventSource(analysis_queue, batch_size=1)
        )

        parsed_output_bucket.grant_read(self.analyzer_lambda)
        self.analysis_results_bucket.grant_read_write(self.analyzer_lambda)
        self.analysis_jobs_table.grant_read_write_data(self.analyzer_lambda)
        self.results_topic.grant_publish(self.analyzer_lambda)

        self.analyzer_lambda.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["bedrock:InvokeModel"],
            resources=[f"arn:aws:bedrock:{self.region}::foundation-model/{BEDROCK_MODEL_ID}"],
        ))

        CfnOutput(self, "ResultsQueueUrl", value=self.results_queue.queue_url)
        CfnOutput(self, "NotificationQueueUrl", value=self.notification_queue.queue_url)
        CfnOutput(self, "AnalysisResultsBucketName", value=self.analysis_results_bucket.bucket_name)
