"""Export service for production plans."""

import json


def export_json(shots: list[dict], metadata: dict | None = None) -> str:
    """Export shot list as JSON."""
    output = {
        "metadata": metadata or {},
        "shots": shots,
    }
    return json.dumps(output, indent=2)
