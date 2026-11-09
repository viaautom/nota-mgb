from __future__ import annotations

import datetime as dt
import unittest
from pathlib import Path

from helpers import cdg_metadata, quality_fields

from core.autofill import apply_changes, propose_fill
from core.domain_catalog import DomainCatalog
from core.evaluation_engine import MetadataEvaluationEngine
from core.iso_xml import XmlError, detect_schema, from_xml, importable, to_xml
from core.report import layer_report, project_report

FIXTURES = Path(__file__).resolve().parent / "fixtures"
INDE_19115_3 = sorted((FIXTURES / "inde").glob("*.xml"))
INDE_19139 = {p.name[:8]: p for p in (FIXTURES / "inde_mgb2009").glob("*.xml")}


def read(path: Path) -> dict:
    return from_xml(path.read_text(encoding="utf-8"))


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.engine = MetadataEvaluationEngine()
        self.full = dict(cdg_metadata(), **quality_fields(), equivalentScale=50000)

    def test_round_trip_keeps_every_field(self):
        back = from_xml(to_xml(self.full))
        self.assertEqual(back.pop("_schema"), "iso19115-3")
        for key, value in self.full.items():
            expected = (
                value
                if not isinstance(value, str)
                or key not in ("topicCategory", "keywords", "license", "distribution")
                else [value]
            )
            if key == "equivalentScale":
                expected = "50000"
            if key.endswith("CharacterSet"):
                expected = "UTF-8"  # 'utf8' (lista ISO) volta normalizado para o nome IANA
            self.assertEqual(back.get(key), expected, key)
        self.assertEqual(self.engine.evaluate(back, "scn")["total_score"], 100)

    def test_xml_matches_inde_conventions(self):
        xml = to_xml(self.full)
        self.assertIn('codeListValue="utf8"', xml)  # IANA UTF-8 -> código ISO, como nos registros da INDE
        self.assertIn('codeListValue="por"', xml)
        self.assertIn("<gco:CharacterString>Perfil MGB 2.0</gco:CharacterString>", xml)
        self.assertIn("mds/2.0/mds.xsd", xml)
        self.assertTrue(xml.startswith('<?xml version="1.0" encoding="UTF-8"?>'))

    def test_raster_distance(self):
        data = cdg_metadata(distance=30)
        self.assertIn('uom="m"', to_xml(data))
        self.assertEqual(from_xml(to_xml(data))["distance"], "30")


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.engine = MetadataEvaluationEngine()

    def test_real_inde_19115_3_records_are_conforme(self):
        self.assertTrue(INDE_19115_3)
        for path in INDE_19115_3:
            data = read(path)
            self.assertEqual(data["_schema"], "iso19115-3")
            result = self.engine.evaluate(data, "cdg")
            self.assertTrue(result["is_conforme"], (path.name, result["issues"]))

    def test_real_inde_round_trip(self):
        for path in INDE_19115_3:
            data = importable(read(path))
            self.assertEqual(importable(from_xml(to_xml(data))), data, path.name)

    def test_mgb2009_record_migrates_with_autofill(self):
        data = importable(read(INDE_19139["6b508c1a"]))
        self.assertEqual(detect_schema(INDE_19139["6b508c1a"].read_text(encoding="utf-8")), "iso19139")
        self.assertNotIn("metadataProfile", data)  # MGB 2009 não é "Perfil MGB 2.0"
        self.assertEqual(data["resourceDate"], "27/10/2020")
        self.assertFalse(self.engine.evaluate(data, "cdg")["is_conforme"])

        changes = {c["id"]: c["new"] for c in propose_fill(data, {}, self.engine, today=dt.date(2026, 11, 9))}
        self.assertEqual(changes["metadataProfile"], "Perfil MGB 2.0")
        self.assertEqual(changes["resourceDate"], "2020-10-27")
        migrated = apply_changes(data, list({"id": k, "new": v} for k, v in changes.items()))
        self.assertTrue(self.engine.evaluate(migrated, "cdg")["is_conforme"])

    def test_mgb2009_portuguese_status_label_is_fixed(self):
        data = importable(read(INDE_19139["45622aa1"]))
        self.assertEqual(data["resourceStatus"], "Concluído")
        changes = {c["id"]: c["new"] for c in propose_fill(data, {}, self.engine)}
        self.assertEqual(changes["resourceStatus"], "completed")

    def test_typo_without_safe_fix_stays_for_the_user(self):
        data = importable(read(INDE_19139["b43bf6dd"]))
        self.assertEqual(data["resourceDateType"], "criation")
        changes = {c["id"] for c in propose_fill(data, {}, self.engine)}
        self.assertNotIn("resourceDateType", changes)
        self.assertIn("resourceDate", changes)  # 24/10/2013 -> 2013-10-24

    def test_rejects_dtd_and_other_roots(self):
        with self.assertRaises(XmlError):
            from_xml('<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><x>&a;</x>')
        with self.assertRaises(XmlError):
            from_xml("<qgis/>")
        with self.assertRaises(XmlError):
            from_xml("<não é xml")


class SuggestionTests(unittest.TestCase):
    def test_partial_dates_are_valid(self):
        engine = MetadataEvaluationEngine()
        for value in ("1981", "1981-07", "1981-07-15", "2026-11-09T12:01:15"):
            self.assertNotIn(
                "resourceDate",
                engine.evaluate(cdg_metadata(resourceDate=value), "cdg")["invalid_required_values"],
                value,
            )

    def test_label_to_code(self):
        catalog = DomainCatalog()
        self.assertEqual(catalog.suggest("MD_ProgressCode", "concluido"), "completed")
        self.assertEqual(catalog.suggest("MD_TopicCategoryCode", "Limites territoriais"), "boundaries")
        self.assertIsNone(catalog.suggest("MD_ProgressCode", "qualquer coisa"))


class ReportTests(unittest.TestCase):
    def test_layer_report_escapes_and_shows_score(self):
        engine = MetadataEvaluationEngine()
        result = engine.evaluate({"resourceTitle": "x"}, "cdg")
        html = layer_report("<camada & cia>", result, engine.weights, now=dt.datetime(2026, 11, 9, 10, 0))
        self.assertIn("&lt;camada &amp; cia&gt;", html)
        self.assertIn("Não conforme", html)
        self.assertIn("09/11/2026 10:00", html)
        self.assertIn("Q84 l.1", html)

    def test_project_report_lists_layers(self):
        report = {
            "layers": [
                {
                    "layer_name": "a",
                    "total_score": 50.0,
                    "selo": "Não conforme",
                    "missing_required": ["x"],
                    "invalid_required_values": [],
                    "resource_label": "CDG",
                }
            ],
            "summary": {"total_layers": 1, "conform_layers": 0, "non_conform_layers": 1},
        }
        self.assertIn("<td>a</td>", project_report(report))


if __name__ == "__main__":
    unittest.main()
