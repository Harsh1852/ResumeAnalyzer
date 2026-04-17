#!/usr/bin/env python3
import aws_cdk as cdk
from stacks.auth_stack import AuthStack
from stacks.upload_stack import UploadStack
from stacks.parser_stack import ParserStack
from stacks.analyzer_stack import AnalyzerStack
from stacks.results_stack import ResultsStack
from stacks.frontend_stack import FrontendStack

app = cdk.App()
env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "us-east-1",
)

# Student 1: Auth + Upload
auth_stack = AuthStack(app, "ResumeAnalyzerAuth", env=env)
upload_stack = UploadStack(app, "ResumeAnalyzerUpload", auth_stack=auth_stack, env=env)

# Student 2: Parser + Analyzer
parser_stack = ParserStack(
    app, "ResumeAnalyzerParser",
    parse_queue=upload_stack.parse_queue,
    resume_bucket=upload_stack.resume_bucket,
    uploads_table=upload_stack.uploads_table,
    env=env,
)
analyzer_stack = AnalyzerStack(
    app, "ResumeAnalyzerAnalyzer",
    analysis_queue=parser_stack.analysis_queue,
    parsed_output_bucket=parser_stack.parsed_output_bucket,
    env=env,
)

# Student 3: Results + Frontend/Notification
results_stack = ResultsStack(
    app, "ResumeAnalyzerResults",
    results_queue=analyzer_stack.results_queue,
    uploads_table=upload_stack.uploads_table,
    user_pool=auth_stack.user_pool,
    env=env,
)
frontend_stack = FrontendStack(
    app, "ResumeAnalyzerFrontend",
    notification_queue=analyzer_stack.notification_queue,
    user_pool=auth_stack.user_pool,
    results_table=results_stack.results_table,
    env=env,
)

app.synth()
