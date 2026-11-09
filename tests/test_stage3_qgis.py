"""Integração com o QGIS real. Pulado quando o módulo qgis não está disponível.

Rodar com o Python do QGIS (ver CLAUDE.md), ex.:
  QT_QPA_PLATFORM=offscreen <python do QGIS> -m unittest discover -s tests
"""

from __future__ import annotations

import unittest

import helpers  # noqa: F401

try:
    from qgis.core import QgsApplication, QgsProject, QgsVectorLayer
    from qgis.PyQt.QtWidgets import QComboBox

    HAS_QGIS = True
except ImportError:
    HAS_QGIS = False

APP = None


def setUpModule():
    global APP
    if HAS_QGIS and QgsApplication.instance() is None:
        APP = QgsApplication([], True)
        APP.initQgis()


@unittest.skipUnless(HAS_QGIS, "QGIS não disponível")
class QgisIntegrationTests(unittest.TestCase):
    def setUp(self):
        from core.autofill import propose_fill
        from core.evaluation_engine import MetadataEvaluationEngine
        from core.layer_facts import layer_facts
        from core.metadata_store import save_metadata
        from core.qgis_metadata_adapter import QgisMetadataAdapter

        self.propose_fill = propose_fill
        self.engine = MetadataEvaluationEngine()
        self.layer_facts = layer_facts
        self.save_metadata = save_metadata
        self.read = QgisMetadataAdapter.extract_layer_metadata
        self.layer = QgsVectorLayer("Polygon?crs=EPSG:31983", "limites", "memory")
        provider = self.layer.dataProvider()
        from qgis.core import QgsFeature, QgsGeometry

        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromWkt("POLYGON((600000 7700000, 700000 7700000, 700000 7800000, 600000 7800000, 600000 7700000))"))
        provider.addFeatures([feature])
        self.layer.updateExtents()
        self.project = QgsProject()

    def test_facts_from_layer(self):
        facts = self.layer_facts(self.layer)
        self.assertEqual(facts["kind"], "vector")
        self.assertEqual(facts["crs"], "EPSG:31983")
        self.assertAlmostEqual(facts["extent"]["west"], -44.04, places=1)
        self.assertLess(facts["extent"]["south"], facts["extent"]["north"])

    def test_autofill_then_form_reaches_conforme(self):
        metadata = self.read(self.layer)
        changes = self.propose_fill(metadata, self.layer_facts(self.layer), self.engine)
        self.save_metadata(self.layer, {c["id"]: c["new"] for c in changes}, self.project)

        form = {
            "resourceTitle": "Limites",
            "resourceAbstract": "Limites municipais.",
            "resourceStatus": "completed",
            "resourceContactName": "Ibexdev",
            "resourceDate": "2026-01-15",
            "resourceDateType": "publication",
            "metadataContactName": "Ibexdev",
            "metadataContactRole": "pointOfContact",
            "topicCategory": "boundaries",
            "resourceLanguage": "por",
            "resourceCharacterSet": "UTF-8",  # camada em memória informa "System": não é chutado
        }
        where = self.save_metadata(self.layer, form, self.project)
        self.assertIn("resourceTitle", where["native"])
        self.assertIn("resourceStatus", where["plugin"])

        result = self.engine.evaluate(self.read(self.layer), "cdg")
        self.assertTrue(result["is_conforme"], result["issues"])
        self.assertEqual(self.layer.metadata().title(), "Limites")
        self.assertEqual(self.layer.metadata().categories(), ["boundaries"])

    def test_panel_builds_form_offscreen(self):
        from ui.panel import MgbValidationPanel

        panel = MgbValidationPanel(self.engine.resource_types())
        result = self.engine.evaluate({}, "cdg")
        domains = {n: self.engine.catalog.allowed_values(n) for n in self.engine.catalog.available_domains()}
        panel.show_result(result, self.engine.weights)
        panel.build_form(result["issues"], self.engine.elements, domains, {})
        combo = panel._form_widgets["resourceStatus"]
        self.assertIsInstance(combo, QComboBox)
        combo.setCurrentIndex(combo.findData("completed"))
        self.assertEqual(panel.form_values()["resourceStatus"], "completed")


if __name__ == "__main__":
    unittest.main()
