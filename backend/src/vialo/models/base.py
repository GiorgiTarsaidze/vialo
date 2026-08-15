"""Base Pydantic model with camelCase JSON aliases and strict validation."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    """Base model for all API request/response types.

    - JSON serialization uses camelCase aliases
    - Python code uses snake_case
    - Extra fields are forbidden
    - Strict type coercion in Python mode (no string→float, no int→str)
    - JSON parsing mode still allows standard ISO datetime strings

    The strict=True config ensures no silent type coercion in Python mode.
    When validating from JSON (via model_validate_json or from API Gateway),
    Pydantic's JSON parser handles datetime strings natively.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        strict=True,
        validate_assignment=True,
    )
