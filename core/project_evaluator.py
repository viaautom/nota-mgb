"""Project-level evaluation for several layers in the same QGIS project."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from .evaluation_engine import MetadataEvaluationEngine


class ProjectEvaluator:
    """Score each layer in a project and sort them from worst to best."""

    def __init__(self, engine: Optional[MetadataEvaluationEngine] = None):
        self.engine = engine or MetadataEvaluationEngine()

    def evaluate_layers(self, layers: Iterable[Dict[str, Any]], resource_type: str = "cdg") -> Dict[str, Any]:
        rows: List[Dict[str, Any]] = []
        for entry in layers:
            layer_name = entry.get("name") or entry.get("layer_name") or "Camada sem nome"
            metadata = entry.get("metadata") or {}
            resource_kind = entry.get("resource_type") or resource_type
            result = self.engine.evaluate(metadata, resource_type=resource_kind)
            rows.append({
                "layer_name": layer_name,
                "resource_type": result["resource_type"],
                "resource_label": result["resource_label"],
                "total_score": result["total_score"],
                "conformity_score": result["conformity_score"],
                "quality_score": result["quality_score"],
                "status": result["status"],
                "selo": result["selo"],
                "missing_required": result["missing_required"],
                "invalid_required_values": result["invalid_required_values"],
                "is_conforme": result["is_conforme"],
                "issues": result["issues"],
            })

        # pior primeiro: não conformes antes, depois menor nota
        rows.sort(key=lambda item: (item["is_conforme"], item["total_score"]))
        summary = {
            "total_layers": len(rows),
            "conform_layers": sum(1 for item in rows if item["is_conforme"]),
            "non_conform_layers": sum(1 for item in rows if not item["is_conforme"]),
            "worst_layer": rows[0]["layer_name"] if rows else None,
            "best_layer": rows[-1]["layer_name"] if rows else None,
        }
        return {"layers": rows, "summary": summary}


__all__ = ["ProjectEvaluator"]
