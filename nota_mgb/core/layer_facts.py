"""Fatos calculáveis de uma camada do QGIS (extensão, SRC, tipo, encoding, pixel)."""

from __future__ import annotations

from typing import Any, Dict, Optional


def _extent_wgs84(layer: Any) -> Optional[Dict[str, float]]:
    from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject

    rect = layer.extent()
    if rect is None or rect.isEmpty() or not layer.crs().isValid():
        return None
    wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
    if layer.crs() != wgs84:
        try:
            rect = QgsCoordinateTransform(layer.crs(), wgs84, QgsProject.instance()).transformBoundingBox(
                rect
            )
        except Exception:  # noqa: BLE001 - QgsCsException: extensão não convertível
            return None
    return {
        "west": round(rect.xMinimum(), 6),
        "south": round(rect.yMinimum(), 6),
        "east": round(rect.xMaximum(), 6),
        "north": round(rect.yMaximum(), 6),
    }


def _pixel_size_meters(layer: Any) -> Optional[float]:
    from qgis.core import Qgis, QgsUnitTypes

    crs = layer.crs()
    if not crs.isValid():
        return None
    size = abs(layer.rasterUnitsPerPixelX())
    if size <= 0:
        return None
    if crs.isGeographic():
        return None  # pixel em graus: tamanho em metros varia com a latitude; usuário informa
    meters = getattr(getattr(Qgis, "DistanceUnit", None), "Meters", None)  # 3.30+
    if meters is None:
        meters = QgsUnitTypes.DistanceMeters  # 3.28
    factor = QgsUnitTypes.fromUnitToUnitFactor(crs.mapUnits(), meters)
    return size * factor


def layer_facts(layer: Any) -> Dict[str, Any]:
    from qgis.core import QgsRasterLayer, QgsVectorLayer

    facts: Dict[str, Any] = {}
    if isinstance(layer, QgsVectorLayer):
        facts["kind"] = "vector"
        provider = layer.dataProvider()
        facts["encoding"] = provider.encoding() if provider is not None else None
    elif isinstance(layer, QgsRasterLayer):
        facts["kind"] = "raster"
        facts["pixelSizeMeters"] = _pixel_size_meters(layer)
    else:
        facts["kind"] = None
    if layer.crs().isValid():
        facts["crs"] = layer.crs().authid()
    facts["extent"] = _extent_wgs84(layer)
    return {k: v for k, v in facts.items() if v is not None}


__all__ = ["layer_facts"]
