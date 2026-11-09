"""Shared fixtures for the unit tests (no QGIS needed)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LONG_ABSTRACT = (
    "Limites municipais do estado para apoio ao planejamento territorial e à análise espacial. "
    "A camada cobre todos os municípios, com dados atualizados em 2026, vetorizados a partir das "
    "leis de criação e revisados com a base contínua 1:250.000 do IBGE em SIRGAS 2000."
)


def general_metadata(**overrides):
    data = {
        "metadataIdentifier": "9d4f3a85-1f10-4d62-a313-5f44da7056a0",
        "metadataLanguage": "por",
        "metadataCharacterSet": "UTF-8",
        "metadataScope": "dataset",
        "metadataContactRole": "pointOfContact",
        "metadataContactName": "Ibexdev",
        "metadataDate": "2026-11-08",
        "metadataDateType": "creation",
        "metadataProfile": "Perfil MGB 2.0",
        "resourceTitle": "Limites municipais",
        "resourceDate": "2026-11-08",
        "resourceDateType": "publication",
        "resourceAbstract": LONG_ABSTRACT,
        "resourceStatus": "completed",
        "resourceContactName": "Diretoria de Geociências",
    }
    data.update(overrides)
    return data


def cdg_metadata(**overrides):
    data = general_metadata(
        spatialRepresentationType="vector",
        topicCategory=["boundaries"],
        extent={"west": -44.0, "south": -20.0, "east": -41.0, "north": -18.0},
        resourceLanguage="por",
        resourceCharacterSet="utf8",
    )
    data.update(overrides)
    return data


def quality_fields():
    return {
        "keywords": ["limites", "município", "território"],
        "lineage": "Vetorização das leis de criação e revisão topológica.",
        "license": "CC-BY 4.0",
        "referenceSystem": "EPSG:4674",
        "email": "contato@exemplo.gov.br",
        "distribution": "https://exemplo.gov.br/limites.zip",
    }
