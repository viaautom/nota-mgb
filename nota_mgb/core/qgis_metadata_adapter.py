"""Read QGIS layer metadata (QgsLayerMetadata) into the engine's flat dict.

API conferida na Etapa 0 (fontes release-3_28 e release-3_30 do QGIS):
- 3.28: title, abstract, identifier, language, encoding, type, keywords,
  categories, contacts (name, organization, role, email), licenses, rights,
  constraints, links, history, crs, extent (spatial/temporal).
- Datas por tipo (dateTime/setDateTime com Qgis.MetadataDateType: Created,
  Published, Revised, Superseded) só existem a partir do QGIS 3.30. No 3.28 a
  data do recurso fica no bloco próprio do plugin.
- Não existem no QGIS: status, escopo, responsável/data/perfil do metadado,
  tipo de representação espacial, escala/resolução. Ficam no bloco do plugin
  (propriedade personalizada da camada, salva no projeto).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

PLUGIN_PROPERTY = "mgb/metadata"
MINIMUM_QGIS_VERSION = "3.28"
DATES_API_VERSION = "3.30"
CATEGORIES_VOCABULARY = "gmd:topicCategory"  # QGIS guarda categories() dentro de keywords()

# Qgis.MetadataDateType -> CI_DateTypeCode (preferência na ordem)
QGIS_DATE_TYPES = (
    ("Published", "publication"),
    ("Revised", "revision"),
    ("Created", "creation"),
)


def _call(obj: Any, name: str, *args: Any) -> Any:
    attr = getattr(obj, name, None)
    if attr is None:
        return None
    return attr(*args) if callable(attr) else attr


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, (list, tuple)):
        items = [v for v in (_clean(i) for i in value) if v]
        return items or None
    return value


class QgisMetadataAdapter:
    """Convert a QGIS layer into the field ids of data/mgb_requirements.json."""

    MINIMUM_QGIS_VERSION = MINIMUM_QGIS_VERSION
    SUPPORTED_FIELDS = [
        "title",
        "abstract",
        "identifier",
        "language",
        "encoding",
        "type",
        "keywords",
        "categories",
        "contacts",
        "licenses",
        "rights",
        "constraints",
        "links",
        "history",
        "crs",
        "extent",
    ]

    @classmethod
    def get_supported_api_summary(cls) -> Dict[str, Any]:
        return {
            "min_version": cls.MINIMUM_QGIS_VERSION,
            "dates_api_version": DATES_API_VERSION,
            "metadata_class": "QgsLayerMetadata",
            "supported_fields": list(cls.SUPPORTED_FIELDS),
            "plugin_property": PLUGIN_PROPERTY,
        }

    # --- bloco do plugin ----------------------------------------------------

    @staticmethod
    def read_plugin_block(layer: Any) -> Dict[str, Any]:
        raw = _call(layer, "customProperty", PLUGIN_PROPERTY, "")
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    # --- leitura do metadado nativo -----------------------------------------

    @staticmethod
    def _extent_wgs84(metadata: Any) -> Optional[Dict[str, float]]:
        extent = _call(metadata, "extent")
        spatial = _call(extent, "spatialExtents") if extent is not None else None
        if not spatial:
            return None
        first = spatial[0]
        bounds = first.bounds
        crs = first.extentCrs
        try:  # pragma: no cover - depende do runtime do QGIS
            from qgis.core import (  # type: ignore
                QgsCoordinateReferenceSystem,
                QgsCoordinateTransform,
                QgsProject,
                QgsRectangle,
            )

            rect = QgsRectangle(bounds.xMinimum(), bounds.yMinimum(), bounds.xMaximum(), bounds.yMaximum())
            if rect.isEmpty():
                return None
            wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
            if crs.isValid() and crs != wgs84:
                rect = QgsCoordinateTransform(crs, wgs84, QgsProject.instance()).transformBoundingBox(rect)
            return {
                "west": rect.xMinimum(),
                "south": rect.yMinimum(),
                "east": rect.xMaximum(),
                "north": rect.yMaximum(),
            }
        except Exception:  # noqa: BLE001 - extensão ilegível conta como ausente
            return None

    @staticmethod
    def _resource_date(metadata: Any) -> Dict[str, Any]:
        try:  # pragma: no cover - depende do runtime do QGIS
            from qgis.core import Qgis  # type: ignore
        except ImportError:
            return {}
        date_enum = getattr(Qgis, "MetadataDateType", None)
        if date_enum is None or not hasattr(metadata, "dateTime"):
            return {}  # QGIS 3.28: sem datas por tipo
        for qgis_name, iso_code in QGIS_DATE_TYPES:
            value = metadata.dateTime(getattr(date_enum, qgis_name))
            if value is not None and value.isValid():
                return {"resourceDate": value.date().toString("yyyy-MM-dd"), "resourceDateType": iso_code}
        return {}

    @classmethod
    def extract_layer_metadata(cls, layer: Any) -> Dict[str, Any]:
        """Native QgsLayerMetadata merged with the plugin block (plugin wins)."""
        if layer is None:
            return {}
        metadata = _call(layer, "metadata")
        result: Dict[str, Any] = {}

        if metadata is not None:
            keywords: List[str] = []
            for vocabulary, words in (_call(metadata, "keywords") or {}).items():
                if vocabulary != CATEGORIES_VOCABULARY:  # categorias não contam como palavra-chave
                    keywords.extend(words)
            contacts = _call(metadata, "contacts") or []
            first = contacts[0] if contacts else None
            crs = _call(metadata, "crs")
            history = _call(metadata, "history") or []
            constraints = [c.constraint for c in (_call(metadata, "constraints") or [])]

            result.update(
                {
                    "resourceTitle": _clean(_call(metadata, "title")),
                    "resourceAbstract": _clean(_call(metadata, "abstract")),
                    "resourceIdentifier": _clean(_call(metadata, "identifier")),
                    "resourceLanguage": _clean(_call(metadata, "language")),
                    "resourceCharacterSet": _clean(_call(metadata, "encoding")),
                    "topicCategory": _clean(_call(metadata, "categories")),
                    "keywords": _clean(keywords),
                    "resourceContactName": _clean(first.name or first.organization) if first else None,
                    "resourceContactRole": _clean(first.role) if first else None,
                    "email": _clean(first.email) if first else None,
                    "license": _clean(
                        list(_call(metadata, "licenses") or [])
                        + list(_call(metadata, "rights") or [])
                        + constraints
                    ),
                    "distribution": _clean([link.url for link in (_call(metadata, "links") or [])]),
                    "lineage": _clean(list(history)),
                    "referenceSystem": _clean(crs.authid()) if crs is not None and crs.isValid() else None,
                    "extent": cls._extent_wgs84(metadata),
                }
            )
            result.update(cls._resource_date(metadata))

        result.update({k: v for k, v in cls.read_plugin_block(layer).items() if v not in (None, "", [])})
        return {k: v for k, v in result.items() if v is not None}


__all__ = ["QgisMetadataAdapter", "PLUGIN_PROPERTY"]
