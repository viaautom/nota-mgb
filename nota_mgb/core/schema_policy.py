"""XML schema rules for export/import, based on the INDE catalog (Etapa 0).

Conferido em 09/11/2026 em https://metadados.inde.gov.br/geonetwork
(GeoNetwork 3.10.2). Schemas instalados e nº de registros:
  iso19139 ............... 47299
  iso19139.mgbsumarizado . 14910   (MGB 2009)
  iso19115-3.mgb .......... 7320   (Perfil MGB 2.0)
  iso19139.mgbcompleto .... 4543   (MGB 2009)
  iso19115-3.2018 .......... 367
Conclusão: a INDE já importa ISO 19115-3 com o perfil MGB 2.0; exportar só
19115-3. Registros reais usam LanguageCode "por" (ISO 639-2) e
MD_CharacterSetCode codeListValue "utf8" (lista ISO), com
metadataProfile/CI_Citation/title = "Perfil MGB 2.0".
"""

from __future__ import annotations

from typing import Dict, List


class SchemaPolicy:
    """Business rules around export/import compatibility for the MGB profile."""

    PROFILE = "Perfil MGB 2.0"
    EXPORT_SCHEMA = "ISO 19115-3:2016"
    INDE_SCHEMA_ID = "iso19115-3.mgb"
    MDB_NAMESPACE = "http://standards.iso.org/iso/19115/-3/mdb/2.0"
    FALLBACK_IMPORT_SCHEMA = "ISO 19139 (MGB 2009)"
    ACCEPTED_SCHEMAS = (
        ("ISO 19115-3:2016", "Perfil MGB 2.0; schema 'iso19115-3.mgb' no GeoNetwork da INDE."),
        ("ISO 19139", "Metadados MGB 2009 (mgbcompleto/mgbsumarizado); só importação para avaliar e migrar."),
    )
    # MD_CharacterSetCode: nome IANA (Quadro 80) -> codeListValue da lista ISO usado no XML
    XML_CHARSET_CODES = {
        "UTF-8": "utf8",
        "UTF-16": "utf16",
        "ISO-8859-1": "8859part1",
        "ISO-8859-14": "8859part14",
        "ISO-8859-15": "8859part15",
        "US-ASCII": "usAscii",
        "Windows-1252": "windows1252",
    }

    @classmethod
    def default_export_schema(cls) -> str:
        return cls.EXPORT_SCHEMA

    @classmethod
    def import_schema_compatibility(cls) -> List[str]:
        return [schema for schema, _ in cls.ACCEPTED_SCHEMAS]

    @classmethod
    def target_catalog_requires_19115_3(cls) -> bool:
        return True

    @classmethod
    def xml_charset_code(cls, iana_name: str) -> str:
        return cls.XML_CHARSET_CODES.get(iana_name, iana_name)

    @classmethod
    def summary(cls) -> Dict[str, object]:
        return {
            "profile": cls.PROFILE,
            "export_schema": cls.EXPORT_SCHEMA,
            "inde_schema_id": cls.INDE_SCHEMA_ID,
            "fallback_import_schema": cls.FALLBACK_IMPORT_SCHEMA,
            "accepted_imports": cls.import_schema_compatibility(),
            "requires_catalog_validation": cls.target_catalog_requires_19115_3(),
        }


__all__ = ["SchemaPolicy"]
