"""Core package for QGIS MGB metadata validation."""

from .domain_catalog import DomainCatalog
from .evaluation_engine import MetadataEvaluationEngine
from .schema_policy import SchemaPolicy
from .qgis_metadata_adapter import QgisMetadataAdapter

__all__ = ["DomainCatalog", "MetadataEvaluationEngine", "SchemaPolicy", "QgisMetadataAdapter"]
