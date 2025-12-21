"""Field analyzer for detecting unknown API response fields.

This module provides utilities to:
1. Capture raw HTTP responses before parsing
2. Compare raw JSON against Pydantic models
3. Identify fields returned by the API that our models don't capture

This helps detect when E*Trade adds new fields to their API responses.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import httpx
from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Callable


# =============================================================================
# Response Capture
# =============================================================================


@dataclass
class CapturedResponse:
    """A captured HTTP response with raw JSON data."""

    url: str
    method: str
    status_code: int
    raw_json: dict[str, Any] | None


class ResponseCapture:
    """Captures HTTP responses for field analysis.

    Creates an httpx.AsyncClient with event hooks that record raw JSON
    responses before they're parsed by the client library.
    """

    def __init__(self) -> None:
        self.responses: list[CapturedResponse] = []

    def clear(self) -> None:
        """Clear captured responses."""
        self.responses.clear()

    def get_last_response(self) -> CapturedResponse | None:
        """Get the most recently captured response."""
        return self.responses[-1] if self.responses else None

    def create_client(self, **kwargs: Any) -> httpx.AsyncClient:
        """Create an httpx.AsyncClient that captures responses."""
        event_hooks = kwargs.pop("event_hooks", {})
        response_hooks = list(event_hooks.get("response", []))
        response_hooks.append(self._capture_response)
        event_hooks["response"] = response_hooks
        return httpx.AsyncClient(event_hooks=event_hooks, **kwargs)

    async def _capture_response(self, response: httpx.Response) -> None:
        """Event hook that captures response data."""
        await response.aread()

        raw_json = None
        try:
            raw_json = response.json()
        except (json.JSONDecodeError, ValueError):
            pass

        self.responses.append(CapturedResponse(
            url=str(response.url),
            method=response.request.method,
            status_code=response.status_code,
            raw_json=raw_json,
        ))


# =============================================================================
# Field Analysis
# =============================================================================


@dataclass
class UnknownField:
    """A field in the API response not captured by our model."""

    path: str  # e.g., "QuoteData.Product.newField"
    value_type: str  # e.g., "str", "int", "dict"
    sample_value: Any  # Truncated sample

    def __hash__(self) -> int:
        return hash((self.path, self.value_type))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, UnknownField):
            return NotImplemented
        return self.path == other.path and self.value_type == other.value_type


class FieldAnalyzer:
    """Compares raw JSON to Pydantic models to find unknown fields.

    Recursively traverses the JSON structure, checking each field against
    the model's declared fields (including aliases).
    """

    def analyze(
        self,
        raw_json: dict[str, Any],
        model_instance: BaseModel,
    ) -> set[UnknownField]:
        """Analyze raw JSON against a model instance.

        Returns:
            Set of unknown fields found
        """
        unknown: set[UnknownField] = set()
        self._compare_recursive(raw_json, model_instance, "", unknown)
        return unknown

    def _compare_recursive(
        self,
        raw_data: Any,
        model_instance: Any,
        path: str,
        unknown: set[UnknownField],
    ) -> None:
        """Recursively compare raw data to model."""
        if raw_data is None:
            return

        if isinstance(raw_data, dict):
            self._compare_dict(raw_data, model_instance, path, unknown)
        elif isinstance(raw_data, list):
            self._compare_list(raw_data, model_instance, path, unknown)

    def _compare_dict(
        self,
        raw_dict: dict[str, Any],
        model_instance: Any,
        path: str,
        unknown: set[UnknownField],
    ) -> None:
        """Compare a dict from raw JSON to a model instance."""
        if not isinstance(model_instance, BaseModel):
            return

        known_keys = self._get_model_keys(model_instance.__class__)

        for key, value in raw_dict.items():
            field_path = f"{path}.{key}" if path else key

            if key not in known_keys:
                unknown.add(UnknownField(
                    path=field_path,
                    value_type=self._get_type_name(value),
                    sample_value=self._truncate_value(value),
                ))
            else:
                # Recurse into known fields
                model_field_name = known_keys[key]
                model_value = getattr(model_instance, model_field_name, None)
                self._compare_recursive(value, model_value, field_path, unknown)

    def _compare_list(
        self,
        raw_list: list[Any],
        model_instance: Any,
        path: str,
        unknown: set[UnknownField],
    ) -> None:
        """Compare a list from raw JSON to a model list."""
        if not isinstance(model_instance, list):
            return

        for i, (raw_item, model_item) in enumerate(zip(raw_list, model_instance)):
            self._compare_recursive(raw_item, model_item, f"{path}[{i}]", unknown)

    def _get_model_keys(self, model_class: type[BaseModel]) -> dict[str, str]:
        """Get mapping of valid keys (field names + aliases) to field names."""
        keys: dict[str, str] = {}
        for field_name, field_info in model_class.model_fields.items():
            keys[field_name] = field_name
            if field_info.alias:
                keys[field_info.alias] = field_name
        return keys

    def _get_type_name(self, value: Any) -> str:
        """Get a readable type name."""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        if isinstance(value, str):
            return "str"
        if isinstance(value, list):
            return "list"
        if isinstance(value, dict):
            return "dict"
        return type(value).__name__

    def _truncate_value(self, value: Any, max_len: int = 50) -> Any:
        """Truncate a value for display."""
        if isinstance(value, str) and len(value) > max_len:
            return value[:max_len] + "..."
        if isinstance(value, (list, dict)):
            return f"<{self._get_type_name(value)}[{len(value)}]>"
        return value


# =============================================================================
# E*Trade Response Handling
# =============================================================================


class ETradeResponseNormalizer:
    """Handles E*Trade-specific response structure quirks.

    E*Trade wraps responses in keys like "QuoteResponse" and uses
    arrays for collections like "QuoteData", "Account", etc.
    """

    # Maps array container keys to the field used for matching individual items
    ARRAY_CONTAINERS: dict[str, str | None] = {
        "QuoteData": "symbol",
        "Account": "accountId",
        "Position": "positionId",
        "OptionPair": None,  # Can't match individually
        "Alert": "id",
        "Transaction": "transactionId",
        "Order": "orderId",
    }

    def unwrap_response(self, raw_json: dict[str, Any]) -> dict[str, Any]:
        """Remove the outer *Response wrapper if present."""
        for key in list(raw_json.keys()):
            if key.endswith("Response") and isinstance(raw_json[key], dict):
                return raw_json[key]
        return raw_json

    def find_matching_json(
        self,
        raw_json: dict[str, Any],
        model_instance: BaseModel,
    ) -> dict[str, Any]:
        """Find the JSON portion that corresponds to a model instance.

        When analyzing a single item from a list (e.g., one Quote from
        QuoteResponse.QuoteData[]), we need to find the matching JSON element.
        """
        # Check if raw_json already matches the model structure
        model_keys = self._get_model_keys(model_instance.__class__)
        json_keys = set(raw_json.keys())

        # If there's significant overlap, this is probably the right level
        if json_keys & model_keys:
            return raw_json

        # Look for array containers
        for container_key, match_field in self.ARRAY_CONTAINERS.items():
            if container_key not in raw_json:
                continue

            array_data = raw_json[container_key]
            if isinstance(array_data, dict):
                array_data = [array_data]

            if not isinstance(array_data, list) or not array_data:
                continue

            # Try to match by identifier field
            if match_field:
                # Convert camelCase to snake_case for model attribute
                model_attr = self._to_snake_case(match_field)
                model_value = getattr(model_instance, model_attr, None)

                if model_value is not None:
                    for item in array_data:
                        if item.get(match_field) == model_value:
                            return item

            # Fall back to first item
            return array_data[0]

        return raw_json

    def _get_model_keys(self, model_class: type[BaseModel]) -> set[str]:
        """Get all valid keys (field names + aliases) for a model."""
        keys: set[str] = set()
        for field_name, field_info in model_class.model_fields.items():
            keys.add(field_name)
            if field_info.alias:
                keys.add(field_info.alias)
        return keys

    def _to_snake_case(self, camel: str) -> str:
        """Convert camelCase to snake_case."""
        result = []
        for i, char in enumerate(camel):
            if char.isupper() and i > 0:
                result.append("_")
            result.append(char.lower())
        return "".join(result)


# =============================================================================
# Collector (aggregates results across test session)
# =============================================================================


class FieldAnalysisCollector:
    """Collects field analysis results across a test session.

    Aggregates unknown fields from all API calls and provides a
    deduplicated summary at the end.
    """

    def __init__(self) -> None:
        self._response_capture = ResponseCapture()
        self._analyzer = FieldAnalyzer()
        self._normalizer = ETradeResponseNormalizer()
        self._unknown_by_endpoint: dict[str, set[UnknownField]] = {}

    @property
    def response_capture(self) -> ResponseCapture:
        """Get the response capture instance for creating HTTP clients."""
        return self._response_capture

    def analyze(self, model_instance: BaseModel, endpoint: str) -> None:
        """Analyze a model against the last captured response.

        Args:
            model_instance: The parsed Pydantic model
            endpoint: Label for reporting (e.g., "accounts/list")
        """
        last_response = self._response_capture.get_last_response()
        if not last_response or not last_response.raw_json:
            return

        # Unwrap E*Trade response wrapper
        raw_json = self._normalizer.unwrap_response(last_response.raw_json)

        # Find the JSON portion matching this model instance
        raw_json = self._normalizer.find_matching_json(raw_json, model_instance)

        # Analyze and collect results
        unknown = self._analyzer.analyze(raw_json, model_instance)
        if unknown:
            self._unknown_by_endpoint.setdefault(endpoint, set()).update(unknown)

    @property
    def has_unknown_fields(self) -> bool:
        """Check if any unknown fields were found."""
        return bool(self._unknown_by_endpoint)

    @property
    def total_unknown_fields(self) -> int:
        """Total count of unique unknown fields."""
        return sum(len(fields) for fields in self._unknown_by_endpoint.values())

    def get_summary(self) -> str:
        """Get a deduplicated summary of all unknown fields."""
        if not self.has_unknown_fields:
            return "No unknown fields detected in API responses."

        lines = [
            f"FIELD ANALYSIS: {self.total_unknown_fields} unknown field(s) detected",
            "",
        ]

        for endpoint in sorted(self._unknown_by_endpoint.keys()):
            fields = self._unknown_by_endpoint[endpoint]
            lines.append(f"  {endpoint}:")
            for f in sorted(fields, key=lambda x: x.path):
                lines.append(f"    - {f.path} ({f.value_type})")
            lines.append("")

        lines.append("Add these fields to the corresponding models (see P5 backlog).")
        return "\n".join(lines)

    def get_fields_by_model(self) -> dict[str, list[str]]:
        """Group unknown fields by likely model name (for automated fixes)."""
        by_model: dict[str, list[str]] = {}

        for fields in self._unknown_by_endpoint.values():
            for f in fields:
                # First path component (before .) is often the model hint
                parts = f.path.split(".")
                model_hint = parts[0].split("[")[0] if parts else "Unknown"
                by_model.setdefault(model_hint, []).append(f.path)

        return {k: sorted(set(v)) for k, v in by_model.items()}
