"""Static safety assertions for the Vialo-only SAM stack."""

from pathlib import Path

TEMPLATE = (Path(__file__).resolve().parents[3] / "infra" / "template.yaml").read_text()


def test_resources_are_vialo_named_and_environment_tagged() -> None:
    for name in (
        "vialo-backend-dev",
        "vialo-deps-dev",
        "vialo-place-cache-dev",
        "vialo-shared-itineraries-dev",
        "vialo-request-limits-dev",
    ):
        assert name in TEMPLATE
    assert TEMPLATE.count("Project: vialo") >= 2
    assert TEMPLATE.count("Value: vialo") >= 5
    assert TEMPLATE.count("ManagedBy") >= 6
    assert TEMPLATE.count("Environment") >= 6


def test_cost_and_retention_defaults_are_bounded() -> None:
    assert TEMPLATE.count("BillingMode: PAY_PER_REQUEST") == 3
    assert TEMPLATE.count("PointInTimeRecoveryEnabled: false") == 3
    assert TEMPLATE.count("RetentionInDays: 7") == 2
    assert "ProvisionedConcurrency" not in TEMPLATE
    assert "ReservedConcurrentExecutions" not in TEMPLATE
    assert "MemorySize: 512" in TEMPLATE
    assert "Timeout: 30" in TEMPLATE


def test_permissions_cover_only_required_logs_and_dynamodb_operations() -> None:
    assert "AWSLambdaBasicExecutionRole" not in TEMPLATE
    assert "dynamodb:TransactWriteItems" in TEMPLATE
    assert "logs:CreateLogStream" in TEMPLATE
    assert "logs:PutLogEvents" in TEMPLATE
    assert 'Resource: "*"' not in TEMPLATE


def test_layer_and_function_source_remain_separate_arm64_artifacts() -> None:
    assert "CodeUri: ../backend/src" in TEMPLATE
    assert "ContentUri: ../backend/layer/" in TEMPLATE
    assert "CompatibleArchitectures:\n        - arm64" in TEMPLATE
    assert "BuildArchitecture: arm64" in TEMPLATE
    assert "BuildMethod: makefile" in TEMPLATE


def test_access_logs_and_runtime_configuration_do_not_expose_private_inputs() -> None:
    assert "AccessLogSettings:" in TEMPLATE
    assert "$context.identity.sourceIp" not in TEMPLATE
    assert "$context.request.body" not in TEMPLATE
    assert "KIRO_API_KEY" not in TEMPLATE
    assert "GOOGLE_MAPS_BROWSER_KEY" not in TEMPLATE
    assert "NoEcho: true" in TEMPLATE


def test_static_function_log_group_precedes_lambda() -> None:
    assert "LogGroupName: /aws/lambda/vialo-backend-dev" in TEMPLATE
    assert "DependsOn: VialoLogGroup" in TEMPLATE


def test_bedrock_iam_uses_exact_foundation_model_arns() -> None:
    """Foundation model ARNs must be exact values returned by AWS, not wildcards."""
    # Exact inference profile ARN via Sub
    assert (
        "arn:aws:bedrock:${BedrockRegion}:${AWS::AccountId}:inference-profile/${BedrockModelId}"
        in TEMPLATE
    )
    # Exact foundation model ARNs (no version suffix, no wildcard)
    assert "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-sonnet-4-6" in TEMPLATE
    assert "arn:aws:bedrock:us-east-2::foundation-model/anthropic.claude-sonnet-4-6" in TEMPLATE
    assert "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-sonnet-4-6" in TEMPLATE
    # No wildcard resources for Bedrock
    assert "arn:aws:bedrock:*" not in TEMPLATE
    assert 'Resource: "*"' not in TEMPLATE
    # No version-suffixed ARNs
    assert "v1:0" not in TEMPLATE
