"""Endpoint-aware field presence analyzer.

Tracks which fields are present in API responses, grouped by the endpoint
that returned them. This helps distinguish between:
1. Fields that are missing because of endpoint context (list vs detail)
2. Fields that are truly optional within the same endpoint
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EndpointFieldStats:
    """Field presence statistics for a specific endpoint."""

    endpoint: str
    model_name: str
    observations: int = 0
    field_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    field_examples: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    def record_observation(self, data: dict[str, Any], field_mapping: dict[str, str]) -> None:
        """Record field presence from a single API response object.

        Args:
            data: The raw API response dict
            field_mapping: Map of python_field_name -> api_alias
        """
        self.observations += 1

        for python_name, api_alias in field_mapping.items():
            if api_alias in data:
                self.field_counts[python_name] += 1
                value = data[api_alias]
                # Store example values (up to 2)
                if len(self.field_examples[python_name]) < 2:
                    if isinstance(value, dict):
                        self.field_examples[python_name].append("<dict>")
                    elif isinstance(value, list):
                        self.field_examples[python_name].append("<list>")
                    else:
                        self.field_examples[python_name].append(str(value)[:50])

    def get_analysis(self) -> dict[str, Any]:
        """Get analysis of field presence for this endpoint."""
        if self.observations == 0:
            return {"endpoint": self.endpoint, "model": self.model_name, "error": "no observations"}

        always_present = []
        sometimes_present = []
        never_present = []

        all_fields = set(self.field_counts.keys()) | set(
            f for f in self.field_examples.keys()
        )

        for field_name in sorted(all_fields):
            count = self.field_counts.get(field_name, 0)
            pct = count / self.observations * 100

            examples = self.field_examples.get(field_name, [])
            example_str = ", ".join(examples) if examples else "N/A"

            field_info = {
                "field": field_name,
                "count": count,
                "total": self.observations,
                "pct": pct,
                "examples": example_str,
            }

            if count == self.observations:
                always_present.append(field_info)
            elif count == 0:
                never_present.append(field_info)
            else:
                sometimes_present.append(field_info)

        return {
            "endpoint": self.endpoint,
            "model": self.model_name,
            "observations": self.observations,
            "always_present": always_present,
            "sometimes_present": sometimes_present,
            "never_present": never_present,
        }


class EndpointFieldAnalyzer:
    """Analyzes field presence across different API endpoints.

    Helps identify whether a field is missing because:
    1. The endpoint doesn't return it (by design)
    2. The field is truly optional within that endpoint
    """

    def __init__(self) -> None:
        self.stats: dict[tuple[str, str], EndpointFieldStats] = {}

    def get_stats(self, endpoint: str, model_name: str) -> EndpointFieldStats:
        """Get or create stats for an endpoint/model combination."""
        key = (endpoint, model_name)
        if key not in self.stats:
            self.stats[key] = EndpointFieldStats(endpoint=endpoint, model_name=model_name)
        return self.stats[key]

    def record(
        self,
        endpoint: str,
        model_name: str,
        data: dict[str, Any],
        field_mapping: dict[str, str],
    ) -> None:
        """Record field presence from an API response.

        Args:
            endpoint: API endpoint name (e.g., "list_accounts", "get_balance")
            model_name: Pydantic model class name
            data: Raw API response dict for the model
            field_mapping: Map of python_field_name -> api_alias
        """
        stats = self.get_stats(endpoint, model_name)
        stats.record_observation(data, field_mapping)

    def get_cross_endpoint_analysis(self, model_name: str) -> dict[str, Any]:
        """Analyze a model's field presence across all endpoints that use it.

        Returns analysis showing which fields are:
        - Present in ALL endpoints (universally required)
        - Present in SOME endpoints (endpoint-specific)
        - Present sometimes within an endpoint (truly optional)
        """
        # Find all endpoints that use this model
        relevant_stats = [
            stats for (_, model), stats in self.stats.items() if model == model_name
        ]

        if not relevant_stats:
            return {"model": model_name, "error": "no data"}

        # Collect field info across endpoints
        endpoints_with_field: dict[str, set[str]] = defaultdict(set)
        field_presence_by_endpoint: dict[str, dict[str, tuple[int, int]]] = defaultdict(dict)

        for stats in relevant_stats:
            analysis = stats.get_analysis()
            endpoint = stats.endpoint

            for field_info in analysis.get("always_present", []):
                field_name = field_info["field"]
                endpoints_with_field[field_name].add(endpoint)
                field_presence_by_endpoint[field_name][endpoint] = (
                    field_info["count"],
                    field_info["total"],
                )

            for field_info in analysis.get("sometimes_present", []):
                field_name = field_info["field"]
                endpoints_with_field[field_name].add(endpoint)
                field_presence_by_endpoint[field_name][endpoint] = (
                    field_info["count"],
                    field_info["total"],
                )

        all_endpoints = {stats.endpoint for stats in relevant_stats}
        all_fields = set(endpoints_with_field.keys())

        # Categorize fields
        universal_required = []  # Present in ALL observations across ALL endpoints
        endpoint_specific = []  # Present in some endpoints but not others
        truly_optional = []  # Sometimes present within an endpoint

        for field_name in sorted(all_fields):
            endpoints_with = endpoints_with_field[field_name]
            presence_info = field_presence_by_endpoint[field_name]

            # Check if it's always present when the endpoint returns it
            always_present_in_endpoints = True
            for endpoint, (count, total) in presence_info.items():
                if count < total:
                    always_present_in_endpoints = False
                    break

            if endpoints_with == all_endpoints and always_present_in_endpoints:
                universal_required.append({
                    "field": field_name,
                    "endpoints": sorted(endpoints_with),
                })
            elif not always_present_in_endpoints:
                # Sometimes missing even within endpoints that return it
                truly_optional.append({
                    "field": field_name,
                    "endpoints": sorted(endpoints_with),
                    "presence": {
                        ep: f"{c}/{t}" for ep, (c, t) in presence_info.items()
                    },
                })
            else:
                # Only present in some endpoints
                endpoint_specific.append({
                    "field": field_name,
                    "present_in": sorted(endpoints_with),
                    "missing_from": sorted(all_endpoints - endpoints_with),
                })

        return {
            "model": model_name,
            "endpoints_analyzed": sorted(all_endpoints),
            "universal_required": universal_required,
            "endpoint_specific": endpoint_specific,
            "truly_optional": truly_optional,
        }

    def print_report(self) -> None:
        """Print a detailed report of field presence by endpoint."""
        print("\n" + "=" * 70)
        print("ENDPOINT-AWARE FIELD ANALYSIS")
        print("=" * 70)

        # Group by model
        models = sorted(set(model for _, model in self.stats.keys()))

        for model_name in models:
            print(f"\n{'=' * 70}")
            print(f"Model: {model_name}")
            print("=" * 70)

            cross_analysis = self.get_cross_endpoint_analysis(model_name)

            print(f"\nEndpoints analyzed: {', '.join(cross_analysis.get('endpoints_analyzed', []))}")

            if cross_analysis.get("universal_required"):
                print(f"\n  UNIVERSALLY REQUIRED ({len(cross_analysis['universal_required'])} fields):")
                print("  (Present in ALL observations across ALL endpoints - should be required)")
                for info in cross_analysis["universal_required"]:
                    print(f"    ✓ {info['field']}")

            if cross_analysis.get("endpoint_specific"):
                print(f"\n  ENDPOINT-SPECIFIC ({len(cross_analysis['endpoint_specific'])} fields):")
                print("  (Only returned by certain endpoints - consider separate models)")
                for info in cross_analysis["endpoint_specific"]:
                    present = ", ".join(info["present_in"])
                    missing = ", ".join(info["missing_from"])
                    print(f"    ◐ {info['field']}")
                    print(f"        Present in: {present}")
                    print(f"        Missing from: {missing}")

            if cross_analysis.get("truly_optional"):
                print(f"\n  TRULY OPTIONAL ({len(cross_analysis['truly_optional'])} fields):")
                print("  (Sometimes present, sometimes not, within the same endpoint)")
                for info in cross_analysis["truly_optional"]:
                    presence = ", ".join(f"{ep}={v}" for ep, v in info["presence"].items())
                    print(f"    ? {info['field']} ({presence})")

            # Also show per-endpoint breakdown
            print("\n  Per-endpoint breakdown:")
            relevant = [(ep, m) for (ep, m) in self.stats.keys() if m == model_name]
            for endpoint, _ in sorted(relevant):
                stats = self.stats[(endpoint, model_name)]
                print(f"\n    {endpoint} ({stats.observations} observations):")
                analysis = stats.get_analysis()

                always = [f["field"] for f in analysis.get("always_present", [])]
                sometimes = [f["field"] for f in analysis.get("sometimes_present", [])]
                never = [f["field"] for f in analysis.get("never_present", [])]

                if always:
                    print(f"      Always: {', '.join(always[:5])}{'...' if len(always) > 5 else ''}")
                if sometimes:
                    print(f"      Sometimes: {', '.join(sometimes)}")
                if never:
                    print(f"      Never: {', '.join(never[:5])}{'...' if len(never) > 5 else ''}")
