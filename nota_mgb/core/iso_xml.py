"""Etapa 4: XML ISO 19115-3 (exportação) e leitura de ISO 19115-3 / ISO 19139.

A exportação segue a estrutura dos registros do schema 'iso19115-3.mgb' do
catálogo da INDE (ver tests/fixtures/inde/). A leitura aceita também o
ISO 19139 dos perfis MGB 2009 (mgbcompleto/mgbsumarizado), para migração.

Entrada e saída usam os ids de data/mgb_requirements.json (o mesmo dicionário
plano do motor de avaliação).
"""

from __future__ import annotations

import re
# Parser da biblioteca padrão: a entrada é filtrada em _parse (DTD e entidades são recusados).
import xml.etree.ElementTree as ET  # nosec B405
from typing import Any, Dict, List, Optional

from .domain_catalog import DomainCatalog
from .schema_policy import SchemaPolicy

NS = {
    "mdb": "http://standards.iso.org/iso/19115/-3/mdb/2.0",
    "cit": "http://standards.iso.org/iso/19115/-3/cit/2.0",
    "gco": "http://standards.iso.org/iso/19115/-3/gco/1.0",
    "gex": "http://standards.iso.org/iso/19115/-3/gex/1.0",
    "lan": "http://standards.iso.org/iso/19115/-3/lan/1.0",
    "mcc": "http://standards.iso.org/iso/19115/-3/mcc/1.0",
    "mco": "http://standards.iso.org/iso/19115/-3/mco/1.0",
    "mri": "http://standards.iso.org/iso/19115/-3/mri/1.0",
    "mrd": "http://standards.iso.org/iso/19115/-3/mrd/1.0",
    "mrl": "http://standards.iso.org/iso/19115/-3/mrl/2.0",
    "mrs": "http://standards.iso.org/iso/19115/-3/mrs/1.0",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}
GMD = "http://www.isotc211.org/2005/gmd"
SCHEMA_LOCATION = (
    "http://standards.iso.org/iso/19115/-3/mds/2.0 http://standards.iso.org/iso/19115/-3/mds/2.0/mds.xsd"
)
CODELISTS = "http://standards.iso.org/iso/19115/resources/Codelists/cat/codelists.xml"
LANGUAGE_CODELIST = "http://www.loc.gov/standards/iso639-2/"
DEFAULT_ROLE = "pointOfContact"

for _prefix, _uri in NS.items():
    ET.register_namespace(_prefix, _uri)


class XmlError(ValueError):
    """XML inválido ou de um schema não suportado."""


# --------------------------------------------------------------------------
# Escrita
# --------------------------------------------------------------------------


def _q(tag: str) -> str:
    prefix, local = tag.split(":")
    return f"{{{NS[prefix]}}}{local}"


def _sub(parent: ET.Element, path: str) -> ET.Element:
    """Cria a cadeia 'a:b/c:d' sob parent e devolve o último elemento."""
    node = parent
    for tag in path.split("/"):
        node = ET.SubElement(node, _q(tag))
    return node


def _text(parent: ET.Element, path: str, value: Any, gco: str = "gco:CharacterString", **attrs: str) -> None:
    node = _sub(parent, f"{path}/{gco}")
    node.text = str(value)
    for key, val in attrs.items():
        node.set(key, val)


def _code(parent: ET.Element, path: str, codelist: str, value: str) -> None:
    node = _sub(parent, path)
    node.set("codeList", f"{CODELISTS}#{codelist}")
    node.set("codeListValue", str(value))


def _as_list(value: Any) -> List[str]:
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [s.strip() for s in str(value).split(",") if s.strip()]


def _bbox(value: Any) -> Optional[Dict[str, float]]:
    if isinstance(value, dict) and all(k in value for k in ("west", "east", "south", "north")):
        return {k: float(value[k]) for k in ("west", "east", "south", "north")}
    parts = _as_list(value)
    if len(parts) == 4:
        xmin, ymin, xmax, ymax = (float(p) for p in parts)
        return {"west": xmin, "south": ymin, "east": xmax, "north": ymax}
    return None


def _date(parent: ET.Element, path: str, value: Any, date_type: Any) -> None:
    ci_date = _sub(parent, f"{path}/cit:CI_Date")
    text = str(value)
    gco = "gco:DateTime" if "T" in text else "gco:Date"
    _text(ci_date, "cit:date", text, gco)
    _code(ci_date, "cit:dateType/cit:CI_DateTypeCode", "CI_DateTypeCode", date_type or "creation")


def _locale(parent: ET.Element, path: str, language: Any, charset: Any) -> None:
    locale = _sub(parent, f"{path}/lan:PT_Locale")
    if language:
        lang = _sub(locale, "lan:language/lan:LanguageCode")
        lang.set("codeList", LANGUAGE_CODELIST)
        lang.set("codeListValue", str(language))
    if charset:
        _code(
            locale,
            "lan:characterEncoding/lan:MD_CharacterSetCode",
            "MD_CharacterSetCode",
            SchemaPolicy.xml_charset_code(str(charset)),
        )


def _responsibility(parent: ET.Element, path: str, role: Any, name: Any, email: Any = None) -> None:
    resp = _sub(parent, f"{path}/cit:CI_Responsibility")
    _code(resp, "cit:role/cit:CI_RoleCode", "CI_RoleCode", role or DEFAULT_ROLE)
    org = _sub(resp, "cit:party/cit:CI_Organisation")
    _text(org, "cit:name", name)
    if email:
        _text(
            org, "cit:contactInfo/cit:CI_Contact/cit:address/cit:CI_Address/cit:electronicMailAddress", email
        )


def to_xml(metadata: Dict[str, Any]) -> str:
    """Gera o XML ISO 19115-3 (UTF-8) a partir do dicionário plano."""
    m = {k: v for k, v in metadata.items() if v not in (None, "", [])}
    root = ET.Element(_q("mdb:MD_Metadata"))
    root.set(_q("xsi:schemaLocation"), SCHEMA_LOCATION)

    if "metadataIdentifier" in m:
        ident = _sub(root, "mdb:metadataIdentifier/mcc:MD_Identifier")
        _text(ident, "mcc:code", m["metadataIdentifier"])
        _text(ident, "mcc:codeSpace", "urn:uuid")
    _locale(root, "mdb:defaultLocale", m.get("metadataLanguage"), m.get("metadataCharacterSet"))
    if "metadataScope" in m:
        _code(
            root,
            "mdb:metadataScope/mdb:MD_MetadataScope/mdb:resourceScope/mcc:MD_ScopeCode",
            "MD_ScopeCode",
            m["metadataScope"],
        )
    if "metadataContactName" in m:
        _responsibility(
            root,
            "mdb:contact",
            m.get("metadataContactRole"),
            m["metadataContactName"],
            m.get("metadataContactEmail"),
        )
    if "metadataDate" in m:
        _date(root, "mdb:dateInfo", m["metadataDate"], m.get("metadataDateType"))
    _text(root, "mdb:metadataStandard/cit:CI_Citation/cit:title", "ISO 19115-3:2014")
    if "metadataProfile" in m:
        _text(root, "mdb:metadataProfile/cit:CI_Citation/cit:title", m["metadataProfile"])

    if "referenceSystem" in m:
        ident = _sub(
            root,
            "mdb:referenceSystemInfo/mrs:MD_ReferenceSystem/mrs:referenceSystemIdentifier/mcc:MD_Identifier",
        )
        code = str(m["referenceSystem"])
        _text(ident, "mcc:code", code)
        if ":" in code:
            _text(ident, "mcc:codeSpace", code.split(":", 1)[0])

    ident = _sub(root, "mdb:identificationInfo/mri:MD_DataIdentification")
    citation = _sub(ident, "mri:citation/cit:CI_Citation")
    _text(citation, "cit:title", m.get("resourceTitle", ""))
    if "resourceDate" in m:
        _date(citation, "cit:date", m["resourceDate"], m.get("resourceDateType"))
    _text(ident, "mri:abstract", m.get("resourceAbstract", ""))
    for status in _as_list(m.get("resourceStatus")):
        _code(ident, "mri:status/mcc:MD_ProgressCode", "MD_ProgressCode", status)
    if "resourceContactName" in m:
        _responsibility(
            ident,
            "mri:pointOfContact",
            m.get("resourceContactRole"),
            m["resourceContactName"],
            m.get("email"),
        )
    if "spatialRepresentationType" in m:
        _code(
            ident,
            "mri:spatialRepresentationType/mcc:MD_SpatialRepresentationTypeCode",
            "MD_SpatialRepresentationTypeCode",
            m["spatialRepresentationType"],
        )
    if "equivalentScale" in m:
        _text(
            ident,
            "mri:spatialResolution/mri:MD_Resolution/mri:equivalentScale/mri:MD_RepresentativeFraction/"
            "mri:denominator",
            int(float(m["equivalentScale"])),
            "gco:Integer",
        )
    elif "distance" in m:
        _text(
            ident,
            "mri:spatialResolution/mri:MD_Resolution/mri:distance",
            m["distance"],
            "gco:Distance",
            uom="m",
        )
    for topic in _as_list(m.get("topicCategory")):
        _sub(ident, "mri:topicCategory/mri:MD_TopicCategoryCode").text = topic
    bbox = _bbox(m.get("extent"))
    if bbox:
        box = _sub(ident, "mri:extent/gex:EX_Extent/gex:geographicElement/gex:EX_GeographicBoundingBox")
        for side, tag in (
            ("west", "westBoundLongitude"),
            ("east", "eastBoundLongitude"),
            ("south", "southBoundLatitude"),
            ("north", "northBoundLatitude"),
        ):
            _text(box, f"gex:{tag}", round(bbox[side], 6), "gco:Decimal")
    keywords = _as_list(m.get("keywords"))
    if keywords:
        kw = _sub(ident, "mri:descriptiveKeywords/mri:MD_Keywords")
        for word in keywords:
            _text(kw, "mri:keyword", word)
    for limitation in _as_list(m.get("license")):
        _text(ident, "mri:resourceConstraints/mco:MD_LegalConstraints/mco:useLimitation", limitation)
    if m.get("resourceLanguage") or m.get("resourceCharacterSet"):
        _locale(ident, "mri:defaultLocale", m.get("resourceLanguage"), m.get("resourceCharacterSet"))

    links = _as_list(m.get("distribution"))
    if links:
        options = _sub(
            root, "mdb:distributionInfo/mrd:MD_Distribution/mrd:transferOptions/mrd:MD_DigitalTransferOptions"
        )
        for url in links:
            online = _sub(options, "mrd:onLine/cit:CI_OnlineResource")
            _text(online, "cit:linkage", url)
    lineage = _as_list(m.get("lineage")) if isinstance(m.get("lineage"), list) else [m.get("lineage")]
    lineage = [str(item) for item in lineage if item]
    if lineage:
        _text(root, "mdb:resourceLineage/mrl:LI_Lineage/mrl:statement", "\n".join(lineage))

    _indent(root)
    body = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"


def _indent(elem: ET.Element, level: int = 0) -> None:
    """ET.indent só existe a partir do Python 3.9; QGIS 3.28 pode ter 3.9+, mas sem garantia."""
    pad = "\n" + "  " * level
    if len(elem):
        if not (elem.text or "").strip():
            elem.text = pad + "  "
        for child in elem:
            _indent(child, level + 1)
        if not (child.tail or "").strip():
            child.tail = pad
    if level and not (elem.tail or "").strip():
        elem.tail = pad


# --------------------------------------------------------------------------
# Leitura
# --------------------------------------------------------------------------

_FORBIDDEN = re.compile(r"<!(DOCTYPE|ENTITY)", re.IGNORECASE)


def _parse(text: str) -> ET.Element:
    if _FORBIDDEN.search(text):
        raise XmlError("XML com DTD/entidades não é aceito.")
    try:
        # DTD e entidades recusados acima.
        return ET.fromstring(text)  # nosec B314
    except ET.ParseError as exc:
        raise XmlError(f"XML inválido: {exc}") from exc


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _path(path: str) -> str:
    return "/".join(f"{{*}}{part}" for part in path.split("/"))


def _first(node: Optional[ET.Element], path: str) -> Optional[ET.Element]:
    return None if node is None else node.find(_path(path))


def _all(node: Optional[ET.Element], path: str) -> List[ET.Element]:
    return [] if node is None else node.findall(_path(path))


def _value(node: Optional[ET.Element]) -> Optional[str]:
    """Texto de um gco:* / gmx:Anchor filho, ou codeListValue de um código."""
    if node is None:
        return None
    if node.get("codeListValue") is not None:
        return node.get("codeListValue").strip() or None
    for child in node.iter():
        if child is node:
            continue
        if child.get("codeListValue") is not None:
            return child.get("codeListValue").strip() or None
        if child.text and child.text.strip():
            return child.text.strip()
    text = (node.text or "").strip()
    return text or None


def _get(node: Optional[ET.Element], path: str) -> Optional[str]:
    return _value(_first(node, path))


def _values(node: Optional[ET.Element], path: str) -> List[str]:
    return [v for v in (_value(n) for n in _all(node, path)) if v]


def _clean(data: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in data.items() if v not in (None, "", [])}


def _bbox_from(node: Optional[ET.Element]) -> Optional[Dict[str, float]]:
    if node is None:
        return None
    try:
        return {
            "west": float(_get(node, "westBoundLongitude")),
            "east": float(_get(node, "eastBoundLongitude")),
            "south": float(_get(node, "southBoundLatitude")),
            "north": float(_get(node, "northBoundLatitude")),
        }
    except (TypeError, ValueError):
        return None


def _constraints(ident: Optional[ET.Element]) -> List[str]:
    """Texto livre (useLimitation, otherConstraints) e códigos de restrição informativos."""
    found: List[str] = []
    for path in (
        "resourceConstraints/*/useLimitation",
        "resourceConstraints/*/otherConstraints",
        "resourceConstraints/*/useConstraints",
        "resourceConstraints/*/accessConstraints",
        "resourceConstraints/*/classification",
    ):
        for value in _values(ident, path):
            if value != "otherRestrictions" and value not in found:  # "otherRestrictions" só remete ao texto
                found.append(value)
    return found


def _charset(value: Optional[str]) -> Optional[str]:
    return DomainCatalog().normalize("MD_CharacterSetCode", value) or value


def _read_19115_3(root: ET.Element) -> Dict[str, Any]:
    contact = _first(root, "contact/CI_Responsibility")
    ident = _first(root, "identificationInfo/MD_DataIdentification")
    poc = _first(ident, "pointOfContact/CI_Responsibility")
    dates = _all(root, "dateInfo/CI_Date")
    meta_date = next(
        (d for d in dates if _get(d, "dateType") in ("creation", "revision")), dates[0] if dates else None
    )
    res_date = _first(ident, "citation/CI_Citation/date/CI_Date")
    party_name = "party/*/name"

    return _clean(
        {
            "metadataIdentifier": _get(root, "metadataIdentifier/MD_Identifier/code"),
            "metadataLanguage": _get(root, "defaultLocale/PT_Locale/language"),
            "metadataCharacterSet": _charset(_get(root, "defaultLocale/PT_Locale/characterEncoding")),
            "metadataScope": _get(root, "metadataScope/MD_MetadataScope/resourceScope"),
            "metadataContactRole": _get(contact, "role"),
            "metadataContactName": _get(contact, party_name),
            "metadataContactEmail": _get(
                contact, "party/*/contactInfo/CI_Contact/address/CI_Address/electronicMailAddress"
            ),
            "metadataDate": _get(meta_date, "date"),
            "metadataDateType": _get(meta_date, "dateType"),
            "metadataProfile": _get(root, "metadataProfile/CI_Citation/title"),
            "resourceTitle": _get(ident, "citation/CI_Citation/title"),
            "resourceDate": _get(res_date, "date"),
            "resourceDateType": _get(res_date, "dateType"),
            "resourceAbstract": _get(ident, "abstract"),
            "resourceStatus": _get(ident, "status"),
            "resourceContactRole": _get(poc, "role"),
            "resourceContactName": _get(poc, party_name),
            "email": _get(poc, "party/*/contactInfo/CI_Contact/address/CI_Address/electronicMailAddress"),
            "spatialRepresentationType": _get(ident, "spatialRepresentationType"),
            "equivalentScale": _get(
                ident, "spatialResolution/MD_Resolution/equivalentScale/MD_RepresentativeFraction/denominator"
            ),
            "distance": _get(ident, "spatialResolution/MD_Resolution/distance"),
            "topicCategory": _values(ident, "topicCategory/MD_TopicCategoryCode"),
            "extent": _bbox_from(
                _first(ident, "extent/EX_Extent/geographicElement/EX_GeographicBoundingBox")
            ),
            "keywords": _values(ident, "descriptiveKeywords/MD_Keywords/keyword"),
            "license": _constraints(ident),
            "resourceLanguage": _get(ident, "defaultLocale/PT_Locale/language"),
            "resourceCharacterSet": _charset(_get(ident, "defaultLocale/PT_Locale/characterEncoding")),
            "referenceSystem": _get(
                root, "referenceSystemInfo/MD_ReferenceSystem/referenceSystemIdentifier/MD_Identifier/code"
            ),
            "distribution": _values(
                root,
                "distributionInfo/MD_Distribution/transferOptions/MD_DigitalTransferOptions/"
                "onLine/CI_OnlineResource/linkage",
            ),
            "lineage": _get(root, "resourceLineage/LI_Lineage/statement"),
        }
    )


def _read_19139(root: ET.Element) -> Dict[str, Any]:
    contact = _first(root, "contact/CI_ResponsibleParty")
    ident = _first(root, "identificationInfo/MD_DataIdentification")
    poc = _first(ident, "pointOfContact/CI_ResponsibleParty")
    res_date = _first(ident, "citation/CI_Citation/date/CI_Date")
    email_path = "contactInfo/CI_Contact/address/CI_Address/electronicMailAddress"

    def party(node: Optional[ET.Element]) -> Optional[str]:
        return _get(node, "organisationName") or _get(node, "individualName")

    return _clean(
        {
            "metadataIdentifier": _get(root, "fileIdentifier"),
            "metadataLanguage": _get(root, "language"),
            "metadataCharacterSet": _charset(_get(root, "characterSet")),
            "metadataScope": _get(root, "hierarchyLevel"),
            "metadataContactRole": _get(contact, "role"),
            "metadataContactName": party(contact),
            "metadataContactEmail": _get(contact, email_path),
            "metadataDate": _get(root, "dateStamp"),
            "metadataDateType": "creation" if _get(root, "dateStamp") else None,
            # metadataStandardName do MGB 2009 não é "Perfil MGB 2.0": fica de fora para a migração preencher.
            "resourceTitle": _get(ident, "citation/CI_Citation/title"),
            "resourceDate": _get(res_date, "date"),
            "resourceDateType": _get(res_date, "dateType"),
            "resourceAbstract": _get(ident, "abstract"),
            "resourceStatus": _get(ident, "status"),
            "resourceContactRole": _get(poc, "role"),
            "resourceContactName": party(poc),
            "email": _get(poc, email_path),
            "spatialRepresentationType": _get(ident, "spatialRepresentationType"),
            "equivalentScale": _get(
                ident, "spatialResolution/MD_Resolution/equivalentScale/MD_RepresentativeFraction/denominator"
            ),
            "distance": _get(ident, "spatialResolution/MD_Resolution/distance"),
            "topicCategory": _values(ident, "topicCategory/MD_TopicCategoryCode"),
            "extent": _bbox_from(
                _first(ident, "extent/EX_Extent/geographicElement/EX_GeographicBoundingBox")
            ),
            "keywords": _values(ident, "descriptiveKeywords/MD_Keywords/keyword"),
            "license": _constraints(ident),
            "resourceLanguage": _get(ident, "language"),
            "resourceCharacterSet": _charset(_get(ident, "characterSet")),
            "referenceSystem": _get(
                root, "referenceSystemInfo/MD_ReferenceSystem/referenceSystemIdentifier/RS_Identifier/code"
            ),
            "distribution": _values(
                root,
                "distributionInfo/MD_Distribution/transferOptions/MD_DigitalTransferOptions/"
                "onLine/CI_OnlineResource/linkage",
            ),
            "lineage": _get(root, "dataQualityInfo/DQ_DataQuality/lineage/LI_Lineage/statement"),
        }
    )


def detect_schema(text: str) -> str:
    root = _parse(text)
    if root.tag == _q("mdb:MD_Metadata"):
        return "iso19115-3"
    if root.tag == f"{{{GMD}}}MD_Metadata":
        return "iso19139"
    raise XmlError(f"Elemento raiz não suportado: {_local(root.tag)}")


def from_xml(text: str) -> Dict[str, Any]:
    """Lê ISO 19115-3 ou ISO 19139 e devolve o dicionário plano + '_schema'."""
    root = _parse(text)
    if root.tag == _q("mdb:MD_Metadata"):
        data, schema = _read_19115_3(root), "iso19115-3"
    elif root.tag == f"{{{GMD}}}MD_Metadata":
        data, schema = _read_19139(root), "iso19139"
    else:
        raise XmlError(f"Elemento raiz não suportado: {_local(root.tag)}. Use ISO 19115-3 ou ISO 19139.")
    data["_schema"] = schema
    return data


def importable(imported: Dict[str, Any]) -> Dict[str, Any]:
    """Valores do XML que vão para a camada (sem chaves internas como '_schema')."""
    return {k: v for k, v in imported.items() if not k.startswith("_")}


__all__ = ["to_xml", "from_xml", "detect_schema", "importable", "XmlError"]
