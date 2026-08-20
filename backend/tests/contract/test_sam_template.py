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
        "vialo-frontend-${AWS::AccountId}-${AWS::Region}-dev",
        "vialo-journal-dev",
        "vialo-journal-media-${AWS::AccountId}-${AWS::Region}-dev",
        "vialo-journal-autoconfirm-dev",
    ):
        assert name in TEMPLATE
    assert TEMPLATE.count("Project: vialo") >= 2
    assert TEMPLATE.count("Value: vialo") >= 5
    assert TEMPLATE.count("ManagedBy") >= 6
    assert TEMPLATE.count("Environment") >= 6


def test_cost_and_retention_defaults_are_bounded() -> None:
    # Four on-demand tables: place cache, shares, rate limits, and the Journal.
    assert TEMPLATE.count("BillingMode: PAY_PER_REQUEST") == 4
    assert TEMPLATE.count("PointInTimeRecoveryEnabled: false") == 4
    assert TEMPLATE.count("RetentionInDays: 7") == 2
    assert "ProvisionedConcurrency" not in TEMPLATE
    assert "ReservedConcurrentExecutions" not in TEMPLATE
    # 1769 MB is one full vCPU, selected from the deployed ARM64 solver benchmark
    # in docs/kiro-evidence/solver-benchmark/. At 512 MB the worst-case 9-stop
    # search plus progressive dropping measured 11.98 s, which does not leave
    # room for provider latency inside the 30 s API Gateway budget.
    assert "MemorySize: 1769" in TEMPLATE
    assert "Timeout: 30" in TEMPLATE
    # The Journal sign-up trigger stays tiny and short-lived.
    assert "MemorySize: 128" in TEMPLATE


def test_journal_storage_is_private_and_separately_indexed() -> None:
    """Journal media is readable only through CloudFront, and never public."""
    assert TEMPLATE.count("BlockPublicAcls: true") == 2
    assert TEMPLATE.count("RestrictPublicBuckets: true") == 2
    assert "AllowCloudFrontOACRead" in TEMPLATE
    for index in ("IndexName: gsi1", "IndexName: gsi2", "IndexName: gsi3"):
        assert index in TEMPLATE
    # Listing indexes must not project the story body or an attached itinerary.
    assert "ProjectionType: INCLUDE" in TEMPLATE
    assert "- body" not in TEMPLATE
    assert "- itinerary" not in TEMPLATE


def test_journal_writes_require_authorization_and_least_privilege() -> None:
    assert "- Authorization" in TEMPLATE
    assert "s3:PutObject" in TEMPLATE
    # The function may create cover objects only; it can never read or delete them.
    assert "s3:GetObject\n                Resource" not in TEMPLATE
    assert "covers/*" in TEMPLATE


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


# --- Frontend hosting infrastructure tests ---


def test_frontend_s3_bucket_is_private_and_encrypted() -> None:
    """S3 bucket must be private, encrypted, no website hosting, BucketOwnerEnforced."""
    assert "BucketOwnerEnforced" in TEMPLATE
    assert "SSEAlgorithm: AES256" in TEMPLATE
    assert "BlockPublicAcls: true" in TEMPLATE
    assert "BlockPublicPolicy: true" in TEMPLATE
    assert "IgnorePublicAcls: true" in TEMPLATE
    assert "RestrictPublicBuckets: true" in TEMPLATE
    # No website hosting configuration
    assert "WebsiteConfiguration" not in TEMPLATE
    assert "IndexDocument" not in TEMPLATE


def test_cloudfront_oac_configured() -> None:
    """CloudFront OAC must be used for S3 origin access."""
    assert "AWS::CloudFront::OriginAccessControl" in TEMPLATE
    assert "SigningBehavior: always" in TEMPLATE
    assert "SigningProtocol: sigv4" in TEMPLATE
    assert "OriginAccessControlId" in TEMPLATE


def test_bucket_policy_scoped_to_distribution_source_arn() -> None:
    """Bucket policy must use exact SourceArn condition for CloudFront."""
    assert "AWS:SourceArn" in TEMPLATE
    assert "cloudfront.amazonaws.com" in TEMPLATE
    assert "s3:GetObject" in TEMPLATE
    assert "FrontendDistribution" in TEMPLATE


def test_cloudfront_distribution_security_configuration() -> None:
    """Distribution must use TLSv1.2_2021, HTTP/2+3, PriceClass_100, IPv6, compression."""
    assert "TLSv1.2_2021" in TEMPLATE
    assert "http2and3" in TEMPLATE
    assert "PriceClass_100" in TEMPLATE
    assert "IPV6Enabled: true" in TEMPLATE
    assert "Compress: true" in TEMPLATE
    assert "sni-only" in TEMPLATE


def test_cloudfront_distribution_has_vialo_place_alias() -> None:
    """Distribution must alias vialo.place with FrontendCertificateArn."""
    assert "vialo.place" in TEMPLATE
    assert "FrontendCertificateArn" in TEMPLATE
    assert "AcmCertificateArn: !Ref FrontendCertificateArn" in TEMPLATE


def test_api_origin_routes_to_api_vialo_place_no_host_forward() -> None:
    """API origin must proxy to api.vialo.place with caching disabled, all methods."""
    assert "api.vialo.place" in TEMPLATE
    assert "https-only" in TEMPLATE
    assert "/api/*" in TEMPLATE
    # CachingDisabled managed policy ID
    assert "4135ea2d-6df8-44a3-9df3-4b5a84be39ad" in TEMPLATE
    # AllViewerExceptHostHeader managed policy ID — no Host forwarding
    assert "b689b0a8-53d0-40ab-baf2-68738e2966ac" in TEMPLATE
    # All HTTP methods for API
    assert "DELETE" in TEMPLATE
    assert "PATCH" in TEMPLATE


def test_spa_rewrite_cloudfront_function_exists() -> None:
    """CloudFront Function must rewrite extensionless non-API paths to /index.html."""
    assert "AWS::CloudFront::Function" in TEMPLATE
    assert "vialo-spa-rewrite" in TEMPLATE
    assert "cloudfront-js-2.0" in TEMPLATE
    assert "/index.html" in TEMPLATE
    assert "startsWith('/api/')" in TEMPLATE


def test_security_response_headers_policy_exists() -> None:
    """Response headers must include HSTS, CSP, X-Frame-Options, etc."""
    assert "AWS::CloudFront::ResponseHeadersPolicy" in TEMPLATE
    assert "StrictTransportSecurity" in TEMPLATE
    assert "ContentSecurityPolicy" in TEMPLATE
    assert "ContentTypeOptions" in TEMPLATE
    assert "FrameOptions" in TEMPLATE
    assert "DENY" in TEMPLATE
    assert "maps.googleapis.com" in TEMPLATE


def test_frontend_outputs_exist() -> None:
    """Template must export bucket name, distribution ID, and domain."""
    assert "FrontendBucketName:" in TEMPLATE
    assert "FrontendDistributionId:" in TEMPLATE
    assert "FrontendDistributionDomain:" in TEMPLATE
    assert "FrontendUrl:" in TEMPLATE


def test_no_public_acl_or_website_hosting() -> None:
    """Ensure no public ACL grants or static website hosting config."""
    assert "PublicRead" not in TEMPLATE
    assert "public-read" not in TEMPLATE
    assert "WebsiteConfiguration" not in TEMPLATE
