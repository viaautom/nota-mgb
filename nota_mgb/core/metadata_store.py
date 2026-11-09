"""Grava o metadado na camada: o que o QGIS suporta vai para o QgsLayerMetadata
nativo; o resto vai para o bloco do plugin (propriedade personalizada
'mgb/metadata', salva no projeto). Cada campo mora em um lugar só, para não
haver duas versões divergentes.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable

from .qgis_metadata_adapter import PLUGIN_PROPERTY

# CI_DateTypeCode -> nome em Qgis.MetadataDateType (QGIS 3.30+)
DATE_TYPES_QGIS = {"creation": "Created", "publication": "Published", "revision": "Revised"}

ALWAYS_NATIVE = {
    "resourceTitle",
    "resourceAbstract",
    "resourceLanguage",
    "resourceCharacterSet",
    "topicCategory",
    "referenceSystem",
    "extent",
    "resourceContactName",
}


def _as_list(value: Any) -> list:
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if str(v).strip()]
    return [s.strip() for s in str(value).split(",") if s.strip()]


def _dates_api_available(metadata: Any) -> bool:
    from qgis.core import Qgis

    return hasattr(Qgis, "MetadataDateType") and hasattr(metadata, "setDateTime")


def _set_native(metadata: Any, field: str, value: Any) -> None:
    from qgis.core import (
        QgsAbstractMetadataBase,
        QgsBox3d,
        QgsCoordinateReferenceSystem,
        QgsLayerMetadata,
    )

    if field == "resourceTitle":
        metadata.setTitle(str(value))
    elif field == "resourceAbstract":
        metadata.setAbstract(str(value))
    elif field == "resourceLanguage":
        metadata.setLanguage(str(value))
    elif field == "resourceCharacterSet":
        metadata.setEncoding(str(value))
    elif field == "topicCategory":
        metadata.setCategories(_as_list(value))
    elif field == "referenceSystem":
        code = str(value).strip()
        crs = QgsCoordinateReferenceSystem(f"EPSG:{code}" if code.isdigit() else code)
        if not crs.isValid():
            return False  # ex.: "SIRGAS2000" (MGB 2009): o texto fica no bloco do plugin
        metadata.setCrs(crs)
    elif field == "extent":
        spatial = QgsLayerMetadata.SpatialExtent()
        spatial.extentCrs = QgsCoordinateReferenceSystem("EPSG:4326")
        spatial.bounds = QgsBox3d(value["west"], value["south"], 0, value["east"], value["north"], 0)
        extent = metadata.extent()
        extent.setSpatialExtents([spatial])
        metadata.setExtent(extent)
    elif field == "resourceContactName":
        contacts = metadata.contacts()
        if contacts:
            contacts[0].name = str(value)
        else:
            contact = QgsAbstractMetadataBase.Contact(str(value))
            contact.role = "pointOfContact"
            contacts = [contact]
        metadata.setContacts(contacts)


def _set_resource_date(metadata: Any, date_value: str, date_type: str) -> bool:
    """Grava a data no nativo se a API existir e o tipo tiver equivalente."""
    from qgis.core import Qgis
    from qgis.PyQt.QtCore import QDate, QDateTime, QTime

    qgis_name = DATE_TYPES_QGIS.get(date_type)
    if not qgis_name or not _dates_api_available(metadata):
        return False
    date = QDate.fromString(str(date_value)[:10], "yyyy-MM-dd")
    if not date.isValid():
        return False
    metadata.setDateTime(getattr(Qgis.MetadataDateType, qgis_name), QDateTime(date, QTime(0, 0)))
    return True


def save_metadata(layer: Any, values: Dict[str, Any], project: Any = None) -> Dict[str, Iterable[str]]:
    """Grava `values` (ids do mgb_requirements.json) na camada. Retorna onde cada campo foi."""
    metadata = layer.metadata()
    block: Dict[str, Any] = {}
    raw = layer.customProperty(PLUGIN_PROPERTY, "")
    if raw:
        try:
            block = json.loads(raw) or {}
        except ValueError:
            block = {}

    native, plugin = [], []
    values = {k: v for k, v in values.items() if v not in (None, "", [])}

    if "resourceDate" in values or "resourceDateType" in values:
        date_value = values.get("resourceDate", block.get("resourceDate"))
        date_type = values.get("resourceDateType", block.get("resourceDateType"))
        if date_value and date_type and _set_resource_date(metadata, date_value, date_type):
            native += ["resourceDate", "resourceDateType"]
            block.pop("resourceDate", None)
            block.pop("resourceDateType", None)
            values.pop("resourceDate", None)
            values.pop("resourceDateType", None)

    for field, value in values.items():
        if field in ALWAYS_NATIVE and _set_native(metadata, field, value) is not False:
            block.pop(field, None)
            native.append(field)
        else:
            block[field] = value
            plugin.append(field)

    layer.setMetadata(metadata)
    layer.setCustomProperty(PLUGIN_PROPERTY, json.dumps(block, ensure_ascii=False))
    if project is None:
        from qgis.core import QgsProject

        project = QgsProject.instance()
    project.setDirty(True)
    return {"native": native, "plugin": plugin}


__all__ = ["save_metadata"]
