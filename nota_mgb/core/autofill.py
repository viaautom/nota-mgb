"""Etapa 3: propõe valores para o que dá para calcular a partir da camada.

Função pura (sem QGIS): recebe o metadado atual e os "fatos" da camada
(ver core/layer_facts.py) e devolve só as mudanças. Nunca sobrescreve um
valor válido; corrige valor inválido apenas quando há sugestão segura
(ex.: idioma "pt-BR" -> "por").
"""

from __future__ import annotations

import datetime as _dt
import uuid
from typing import Any, Callable, Dict, List, Optional

from .domain_catalog import DomainCatalog
from .evaluation_engine import MetadataEvaluationEngine

PROFILE = "Perfil MGB 2.0"
DEFAULT_LANGUAGE = "por"
XML_CHARSET = "UTF-8"


def propose_fill(
    metadata: Dict[str, Any],
    facts: Dict[str, Any],
    engine: Optional[MetadataEvaluationEngine] = None,
    today: Optional[_dt.date] = None,
    new_id: Callable[[], str] = lambda: str(uuid.uuid4()),
) -> List[Dict[str, Any]]:
    """Return a list of {id, label, old, new, reason} for missing/invalid calculable fields."""
    engine = engine or MetadataEvaluationEngine()
    catalog: DomainCatalog = engine.catalog
    today = today or _dt.date.today()
    issues = {i["id"]: i for i in engine.evaluate(metadata, "scn")["issues"]}
    changes: List[Dict[str, Any]] = []

    def propose(field: str, value: Any, reason: str) -> None:
        if value in (None, "", []) or field not in issues:
            return
        old = metadata.get(field)
        changes.append({
            "id": field,
            "label": engine.elements[field]["label"],
            "old": old,
            "new": value,
            "reason": reason,
        })

    def fixed_language(field: str) -> Optional[str]:
        suggestion = issues.get(field, {}).get("suggestion")
        return suggestion or (DEFAULT_LANGUAGE if issues.get(field, {}).get("problem") == "missing" else None)

    propose("metadataIdentifier", new_id(), "Identificador gerado (UUID).")
    propose("metadataProfile", PROFILE, "Valor fixo do perfil.")
    propose("metadataScope", "dataset", "Camada = conjunto de dados.")
    propose("metadataCharacterSet", XML_CHARSET, "O XML exportado é gravado em UTF-8.")
    propose("metadataLanguage", fixed_language("metadataLanguage"), "Idioma em ISO 639-2; confira.")
    if "metadataDate" in issues:
        propose("metadataDate", today.isoformat(), "Data de hoje.")
        if "metadataDateType" in issues or not metadata.get("metadataDateType"):
            changes.append({
                "id": "metadataDateType",
                "label": engine.elements["metadataDateType"]["label"],
                "old": metadata.get("metadataDateType"),
                "new": "creation",
                "reason": "Metadado criado hoje.",
            })
    else:
        propose("metadataDateType", "creation", "Tipo de data padrão.")

    kind = facts.get("kind")
    representation = {"vector": "vector", "raster": "grid"}.get(kind or "")
    propose("spatialRepresentationType", representation, "Tipo da camada no QGIS.")
    propose("extent", facts.get("extent"), "Calculada da camada e convertida para graus (WGS 84).")
    propose("resourceLanguage", fixed_language("resourceLanguage"), "Idioma em ISO 639-2; confira.")

    encoding = catalog.normalize("MD_CharacterSetCode", facts.get("encoding"))
    if encoding is None and kind == "raster":
        encoding = XML_CHARSET
    propose("resourceCharacterSet", encoding, "Codificação informada pelo provedor da camada.")

    if facts.get("pixelSizeMeters") and "spatialResolution" in issues:
        changes.append({
            "id": "distance",
            "label": engine.elements["spatialResolution"]["label"],
            "old": metadata.get("distance"),
            "new": round(float(facts["pixelSizeMeters"]), 6),
            "reason": "Tamanho do pixel do raster, em metros.",
        })

    if facts.get("crs") and not metadata.get("referenceSystem"):
        changes.append({
            "id": "referenceSystem",
            "label": "Sistema de referência",
            "old": None,
            "new": facts["crs"],
            "reason": "SRC da camada.",
        })
    return changes


def apply_changes(metadata: Dict[str, Any], changes: List[Dict[str, Any]]) -> Dict[str, Any]:
    result = dict(metadata)
    for change in changes:
        result[change["id"]] = change["new"]
    return result


__all__ = ["propose_fill", "apply_changes"]
