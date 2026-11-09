"""Controlled vocabularies of the Brazilian MGB 2.0 metadata profile.

All values live in data/mgb_domains.json (rules in data, not in code).
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

DOMAINS_PATH = Path(__file__).resolve().parents[1] / "data" / "mgb_domains.json"


def _load_domains(path: Path = DOMAINS_PATH) -> Dict[str, Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)["domains"]


class DomainCatalog:
    """Lookup and validation of MGB code lists (Quadros 58, 71-80)."""

    def __init__(self, extra: Optional[Mapping[str, Mapping[str, Any]]] = None):
        self.domains = _load_domains()
        if extra:
            for name, spec in extra.items():
                self.domains[name] = dict(spec)

    # --- consulta -----------------------------------------------------------

    def available_domains(self) -> List[str]:
        return sorted(self.domains)

    def _spec(self, domain_name: str) -> Dict[str, Any]:
        spec = self.domains.get(domain_name)
        if spec is None:
            raise KeyError(f"Domain '{domain_name}' not found in the MGB catalog.")
        return spec

    def quadro(self, domain_name: str) -> Optional[int]:
        return self._spec(domain_name).get("quadro")

    def get_values(self, domain_name: str) -> Dict[str, str]:
        """Official values of the quadro plus accepted extras, code -> label."""
        spec = self._spec(domain_name)
        values = dict(spec.get("values", {}))
        values.update(spec.get("extra_values", {}))
        return values

    def allowed_values(self, domain_name: str) -> List[Tuple[str, str]]:
        return list(self.get_values(domain_name).items())

    def valid_codes_for(self, domain_name: str) -> List[str]:
        return list(self.get_values(domain_name))

    def label(self, domain_name: str, code: str) -> str:
        canonical = self.normalize(domain_name, code)
        if canonical is None:
            return str(code)
        return self.get_values(domain_name).get(canonical, canonical)

    # --- validação ----------------------------------------------------------

    def normalize(self, domain_name: str, value: Any) -> Optional[str]:
        """Return the canonical code for a valid value, or None if invalid.

        Accepts, case-insensitively: official codes, extra values, equivalents
        (e.g. ISO codelist 'utf8' for IANA 'UTF-8') and, when the domain has a
        pattern (ISO 639-2), any code matching it.
        """
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        spec = self._spec(domain_name)
        lowered = text.lower()
        for code in self.get_values(domain_name):
            if code.lower() == lowered:
                return code
        equivalents = {k.lower(): v for k, v in spec.get("equivalents", {}).items()}
        if lowered in equivalents:
            return equivalents[lowered]
        pattern = spec.get("pattern")
        if pattern and lowered not in {k.lower() for k in spec.get("suggestions", {})}:
            if re.fullmatch(pattern, lowered):
                return lowered
        return None

    def validate(self, domain_name: str, value: Any) -> bool:
        return self.normalize(domain_name, value) is not None

    def suggest(self, domain_name: str, value: Any) -> Optional[str]:
        """Suggested valid code for a common invalid value.

        Ex.: 'pt-BR' -> 'por' (lista de sugestões) e 'Concluído' -> 'completed'
        (rótulo oficial em português no lugar do código).
        """
        if value is None:
            return None
        key = _fold(str(value))
        spec = self._spec(domain_name)
        suggestions = {_fold(k): v for k, v in spec.get("suggestions", {}).items()}
        if key in suggestions:
            return suggestions[key]
        labels = {_fold(label): code for code, label in self.get_values(domain_name).items()}
        return labels.get(key)


def _fold(text: str) -> str:
    """Minúsculas e sem acento, para comparar rótulos digitados à mão."""
    normalized = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


__all__ = ["DomainCatalog", "DOMAINS_PATH"]
