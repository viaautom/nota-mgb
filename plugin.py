"""Entry-point for the QGIS MGB metadata validator plugin."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .core.domain_catalog import DomainCatalog
from .core.evaluation_engine import MetadataEvaluationEngine
from .core.project_evaluator import ProjectEvaluator
from .core.qgis_metadata_adapter import QgisMetadataAdapter
from .core.schema_policy import SchemaPolicy


class MgbMetadataPlugin:
    """Orchestration layer for validation, project scoring and schema checks."""

    def __init__(self, iface: Any = None):
        self.iface = iface
        self.domain_catalog = DomainCatalog()
        self.schema_policy = SchemaPolicy()
        self.adapter = QgisMetadataAdapter()
        self.engine = MetadataEvaluationEngine(self.domain_catalog)
        self.project_evaluator = ProjectEvaluator(self.engine)

    def validate_layer(self, layer: Any) -> Dict[str, Any]:
        metadata = self.adapter.extract_layer_metadata(layer)
        return {
            "metadata_summary": metadata,
            "profile": "Perfil MGB 2.0",
            "export_schema": self.schema_policy.default_export_schema(),
            "accepted_imports": self.schema_policy.import_schema_compatibility(),
        }

    def evaluate_layer(self, metadata: Dict[str, Any], resource_type: str = "cdg") -> Dict[str, Any]:
        return self.engine.evaluate(metadata, resource_type=resource_type)

    def evaluate_project(self, layers: Iterable[Dict[str, Any]], resource_type: str = "cdg") -> Dict[str, Any]:
        return self.project_evaluator.evaluate_layers(layers, resource_type=resource_type)

    def available_domains(self):
        return self.domain_catalog.available_domains()


__all__ = ["MgbMetadataPlugin"]
