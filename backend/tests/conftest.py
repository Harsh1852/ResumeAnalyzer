"""
Shared fixtures for the jobs_service tests.
Uses moto to mock DynamoDB so the real AWS account is never touched.
"""
import importlib
import os
import sys

import boto3
import pytest
from moto import mock_aws


LAMBDAS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "lambdas"))


@pytest.fixture
def aws_creds(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture
def mocked_aws(aws_creds):
    with mock_aws():
        yield


def _create_table(name, pk, gsis=None):
    client = boto3.client("dynamodb", region_name="us-east-1")
    gsis = gsis or []
    attrs = [{"AttributeName": pk, "AttributeType": "S"}]
    seen = {pk}
    for idx in gsis:
        if idx["hash"] not in seen:
            attrs.append({"AttributeName": idx["hash"], "AttributeType": "S"})
            seen.add(idx["hash"])
    client.create_table(
        TableName=name,
        KeySchema=[{"AttributeName": pk, "KeyType": "HASH"}],
        AttributeDefinitions=attrs,
        BillingMode="PAY_PER_REQUEST",
        GlobalSecondaryIndexes=[
            {
                "IndexName": idx["name"],
                "KeySchema": [{"AttributeName": idx["hash"], "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            } for idx in gsis
        ] or None,
    )
    return boto3.resource("dynamodb", region_name="us-east-1").Table(name)


@pytest.fixture
def jobs_tables(mocked_aws):
    jobs = _create_table(
        "resume-analyzer-jobs", "jobId",
        gsis=[{"name": "resultId-index", "hash": "resultId"},
              {"name": "userId-index", "hash": "userId"}],
    )
    tailored = _create_table(
        "resume-analyzer-tailored-resumes", "resumeId",
        gsis=[{"name": "userId-index", "hash": "userId"},
              {"name": "jobId-index", "hash": "jobId"}],
    )
    # Results table mimics the one created by ResultsStack — PK userId/SK resultId
    client = boto3.client("dynamodb", region_name="us-east-1")
    client.create_table(
        TableName="resume-analyzer-results",
        KeySchema=[
            {"AttributeName": "userId", "KeyType": "HASH"},
            {"AttributeName": "resultId", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "userId", "AttributeType": "S"},
            {"AttributeName": "resultId", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[{
            "IndexName": "resultId-index",
            "KeySchema": [{"AttributeName": "resultId", "KeyType": "HASH"}],
            "Projection": {"ProjectionType": "ALL"},
        }],
        BillingMode="PAY_PER_REQUEST",
    )
    results = boto3.resource("dynamodb", region_name="us-east-1").Table("resume-analyzer-results")
    return {"jobs": jobs, "tailored": tailored, "results": results}


@pytest.fixture
def jobs_handler(jobs_tables, monkeypatch):
    """Import the jobs_service handler fresh so it picks up mocked env + tables."""
    monkeypatch.setenv("JOBS_TABLE_NAME", "resume-analyzer-jobs")
    monkeypatch.setenv("TAILORED_RESUMES_TABLE_NAME", "resume-analyzer-tailored-resumes")
    monkeypatch.setenv("RESULTS_TABLE_NAME", "resume-analyzer-results")
    monkeypatch.setenv("ADZUNA_APP_ID", "test_id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "test_key")
    monkeypatch.setenv("ADZUNA_COUNTRY", "us")
    monkeypatch.setenv("TAVILY_API_KEY", "test_tavily")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")

    sys.modules.pop("handler", None)
    path = os.path.join(LAMBDAS_DIR, "jobs_service")
    if path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)
    return importlib.import_module("handler")
