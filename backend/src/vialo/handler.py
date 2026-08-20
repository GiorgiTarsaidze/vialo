"""Lambda Powertools entry point for Vialo API."""

from __future__ import annotations

from typing import Any

from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
metrics = Metrics(namespace="Vialo")
app = APIGatewayHttpResolver()

# Import route modules which register with app — imports have side effects
import vialo.api.blog  # noqa: E402, F401
import vialo.api.itineraries  # noqa: E402, F401
import vialo.api.photos  # noqa: E402, F401
import vialo.api.places  # noqa: E402, F401
import vialo.api.shares  # noqa: E402, F401


@logger.inject_lambda_context(correlation_id_path="requestContext.requestId")
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """AWS Lambda handler."""
    return app.resolve(event, context)
