"""Scoring engine for the MGB 2.0 profile (régua do PRD: 70 conformidade + 30 qualidade).

Which elements are required, their domains and fixed values come from
data/mgb_requirements.json; this module only knows how to check them.
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .domain_catalog import DomainCatalog

REQUIREMENTS_PATH = Path(__file__).resolve().parents[1] / "data" / "mgb_requirements.json"
CONFORMITY_POINTS = 70


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return ", ".join(_text(item) for item in value if _text(item))
    if isinstance(value, dict):
        return ", ".join(_text(item) for item in value.values() if _text(item))
    return str(value).strip()


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [item for item in value if _text(item)]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [value]


def _is_date(value: Any) -> bool:
    if isinstance(value, (_dt.date, _dt.datetime)):
        return True
    text = _text(value)
    if not text:
        return False
    if text.endswith("Z"):
        text = text[:-1]
    for parser in (_dt.datetime.fromisoformat, _dt.date.fromisoformat):
        try:
            parser(text)
            return True
        except ValueError:
            continue
    return False


def _to_float(value: Any) -> Optional[float]:
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def _bbox_from(value: Any) -> Optional[Dict[str, float]]:
    """Accept dict(west, east, south, north) or [xmin, ymin, xmax, ymax] / 'xmin,ymin,xmax,ymax'."""
    if isinstance(value, dict):
        keys = ("west", "east", "south", "north")
        if all(k in value for k in keys):
            nums = {k: _to_float(value[k]) for k in keys}
            return None if None in nums.values() else nums  # type: ignore[return-value]
        return None
    parts = _as_list(value)
    if len(parts) != 4:
        return None
    nums = [_to_float(p) for p in parts]
    if None in nums:
        return None
    xmin, ymin, xmax, ymax = nums  # type: ignore[misc]
    return {"west": xmin, "south": ymin, "east": xmax, "north": ymax}


def _is_valid_extent(value: Any) -> bool:
    """Quadro 31/32: ao menos uma extensão (retângulo, polígono, descrição, temporal ou vertical)."""
    if isinstance(value, dict):
        for key in ("geographicIdentifier", "description", "polygon", "temporal", "vertical"):
            if _text(value.get(key)):
                return True
        if "bbox" in value:
            value = value["bbox"]
    bbox = _bbox_from(value)
    if bbox is None:
        return False
    return (
        -180 <= bbox["west"] <= 180
        and -180 <= bbox["east"] <= 180
        and -90 <= bbox["south"] <= 90
        and -90 <= bbox["north"] <= 90
        and bbox["south"] <= bbox["north"]
    )


def _positive(value: Any, integer: bool) -> bool:
    number = _to_float(value)
    if number is None or number <= 0:
        return False
    return number.is_integer() if integer else True


class MetadataEvaluationEngine:
    """Evaluate a flat metadata dict (ids from mgb_requirements.json) against MGB 2.0."""

    def __init__(self, catalog: Optional[DomainCatalog] = None, requirements_path: Path = REQUIREMENTS_PATH):
        self.catalog = catalog or DomainCatalog()
        with requirements_path.open("r", encoding="utf-8") as handle:
            self.requirements: Dict[str, Any] = json.load(handle)
        self.elements: Dict[str, Dict[str, Any]] = self.requirements["elements"]
        self.weights: Dict[str, Dict[str, Any]] = self.requirements["quality_criteria"]

    # --- tipos de recurso ---------------------------------------------------

    def resource_types(self) -> Dict[str, str]:
        return {key: spec["label"] for key, spec in self.requirements["resource_types"].items()}

    def required_fields(self, resource_type: str) -> List[str]:
        types = self.requirements["resource_types"]
        spec = types[resource_type]
        inherited = self.required_fields(spec["extends"]) if spec.get("extends") else []
        return inherited + list(spec["required"])

    # --- leitura dos campos -------------------------------------------------

    @staticmethod
    def _lookup(metadata: Dict[str, Any], names: List[str]) -> Any:
        for name in names:
            if name in metadata and _text(metadata[name]):
                return metadata[name]
        return None

    def _value(self, metadata: Dict[str, Any], field: str) -> Any:
        spec = self.elements.get(field, {})
        aliases = spec.get("aliases", [])
        return self._lookup(metadata, [field] + (aliases if isinstance(aliases, list) else []))

    def _quality_value(self, metadata: Dict[str, Any], name: str) -> Any:
        aliases = self.requirements.get("quality_aliases", {}).get(name, [])
        return self._lookup(metadata, [name] + aliases)

    # --- checagem de um elemento obrigatório --------------------------------

    def _check_element(self, metadata: Dict[str, Any], field: str) -> Optional[Dict[str, Any]]:
        """Return None when the element is OK, otherwise an issue dict."""
        spec = self.elements[field]
        issue = {
            "id": field,
            "label": spec["label"],
            "quadro": spec.get("quadro"),
            "linha": spec.get("linha"),
        }

        if "any_of" in spec:
            aliases = spec.get("aliases", {})
            found_any = False
            for option, rule in spec["any_of"].items():
                value = self._lookup(metadata, [option] + aliases.get(option, []))
                if value is None:
                    continue
                found_any = True
                if _positive(value, integer=(rule == "positive_integer")):
                    return None
            if not found_any:
                return dict(issue, problem="missing", message="Elemento obrigatório ausente.")
            return dict(issue, problem="invalid", message="Informe um valor maior que zero (escala: número inteiro).")

        value = self._value(metadata, field)
        if value is None:
            return dict(issue, problem="missing", message="Elemento obrigatório ausente.")

        if "fixed" in spec:
            if _text(value) != spec["fixed"]:
                return dict(issue, problem="invalid", message=f"O valor deve ser exatamente \"{spec['fixed']}\".")
            return None

        domain = spec.get("domain")
        if domain:
            bad = [item for item in _as_list(value) if not self.catalog.validate(domain, item)]
            if bad:
                quadro = self.catalog.quadro(domain)
                message = f"Valor fora da lista {domain} (Quadro {quadro}): {', '.join(_text(b) for b in bad)}."
                suggestion = self.catalog.suggest(domain, bad[0])
                result = dict(issue, problem="invalid", message=message, domain=domain)
                if suggestion:
                    result["suggestion"] = suggestion
                    result["message"] += f" Use \"{suggestion}\"."
                return result
            return None

        validator = spec.get("validator")
        if validator == "date" and not _is_date(value):
            return dict(issue, problem="invalid", message="Data inválida; use o formato AAAA-MM-DD.")
        if validator == "extent" and not _is_valid_extent(value):
            return dict(
                issue,
                problem="invalid",
                message="Extensão inválida; informe o retângulo envolvente em graus (oeste, sul, leste, norte).",
            )
        return None

    # --- qualidade (30 pts) -------------------------------------------------

    def _evaluate_quality(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        checks: Dict[str, bool] = {}

        abstract = _text(self._value(metadata, "resourceAbstract"))
        title = _text(self._value(metadata, "resourceTitle"))
        min_length = self.weights["summary"].get("min_length", 200)
        checks["summary"] = len(abstract) >= min_length and abstract.lower() != title.lower()

        min_keywords = self.weights["keywords"].get("min_count", 3)
        checks["keywords"] = len(_as_list(self._quality_value(metadata, "keywords"))) >= min_keywords

        checks["lineage"] = bool(_text(self._quality_value(metadata, "lineage")))
        checks["restrictions"] = bool(_text(self._quality_value(metadata, "license")))
        checks["referenceSystem"] = bool(_text(self._quality_value(metadata, "referenceSystem")))

        email = _text(self._quality_value(metadata, "email"))
        has_contact = bool(_text(self._value(metadata, "resourceContactName")) or _text(self._value(metadata, "metadataContactName")))
        checks["contact"] = has_contact and "@" in email

        checks["distribution"] = bool(_text(self._quality_value(metadata, "distribution")))

        points = sum(cfg["weight"] for name, cfg in self.weights.items() if checks.get(name))
        return {"checks": checks, "points": points}

    # --- avaliação ----------------------------------------------------------

    def evaluate(self, metadata: Dict[str, Any], resource_type: str = "cdg") -> Dict[str, Any]:
        resource_type = (resource_type or "cdg").lower()
        if resource_type not in self.requirements["resource_types"]:
            resource_type = "general"

        required = self.required_fields(resource_type)
        issues = [issue for issue in (self._check_element(metadata, f) for f in required) if issue]
        missing = [i["id"] for i in issues if i["problem"] == "missing"]
        invalid = [i["id"] for i in issues if i["problem"] == "invalid"]
        satisfied = len(required) - len(issues)

        quality = self._evaluate_quality(metadata)
        conformity_score = CONFORMITY_POINTS * satisfied / len(required) if required else 0.0
        total_score = conformity_score + quality["points"]

        is_conforme = not issues
        if not is_conforme:
            status, selo = "nao_conforme", "Não conforme"
        elif total_score >= 90:
            status, selo = "conforme", "Excelente"
        else:
            status, selo = "conforme", "Conforme"

        return {
            "resource_type": resource_type,
            "resource_label": self.requirements["resource_types"][resource_type]["label"],
            "required_fields": len(required),
            "satisfied_required": satisfied,
            "missing_required": missing,
            "invalid_required_values": invalid,
            "issues": issues,
            "conformity_score": round(conformity_score, 2),
            "quality_score": quality["points"],
            "total_score": round(total_score, 2),
            "status": status,
            "selo": selo,
            "quality_checks": quality["checks"],
            "is_conforme": is_conforme,
        }


__all__ = ["MetadataEvaluationEngine", "REQUIREMENTS_PATH"]
