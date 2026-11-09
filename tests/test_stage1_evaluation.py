from __future__ import annotations

import unittest

from helpers import cdg_metadata, general_metadata, quality_fields

from core.evaluation_engine import MetadataEvaluationEngine


class Stage1EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.engine = MetadataEvaluationEngine()

    def test_required_counts_match_quadros(self):
        self.assertEqual(len(self.engine.required_fields("general")), 15)  # Q84
        self.assertEqual(len(self.engine.required_fields("cdg")), 20)  # Q85 (extensão = 1)
        self.assertEqual(len(self.engine.required_fields("scn")), 21)  # Q86

    def test_complete_cdg_is_excelente(self):
        result = self.engine.evaluate(dict(cdg_metadata(), **quality_fields()), "cdg")
        self.assertTrue(result["is_conforme"], result["issues"])
        self.assertEqual(result["total_score"], 100)
        self.assertEqual(result["selo"], "Excelente")

    def test_conforme_without_quality(self):
        result = self.engine.evaluate(cdg_metadata(resourceAbstract="Limites municipais do estado."), "cdg")
        self.assertTrue(result["is_conforme"])
        self.assertEqual(result["conformity_score"], 70)
        self.assertEqual(result["selo"], "Conforme")

    def test_missing_required_is_nao_conforme(self):
        data = general_metadata()
        del data["resourceStatus"]
        result = self.engine.evaluate(data, "general")
        self.assertFalse(result["is_conforme"])
        self.assertEqual(result["missing_required"], ["resourceStatus"])
        self.assertEqual(result["selo"], "Não conforme")
        self.assertAlmostEqual(result["conformity_score"], 70 * 14 / 15, places=2)

    def test_invalid_value_does_not_score_and_suggests_fix(self):
        result = self.engine.evaluate(general_metadata(metadataLanguage="pt-BR"), "general")
        self.assertEqual(result["invalid_required_values"], ["metadataLanguage"])
        self.assertAlmostEqual(result["conformity_score"], 70 * 14 / 15, places=2)
        self.assertEqual(result["issues"][0]["suggestion"], "por")

    def test_profile_must_be_exact(self):
        result = self.engine.evaluate(general_metadata(metadataProfile="MGB"), "general")
        self.assertIn("metadataProfile", result["invalid_required_values"])

    def test_extent_ranges(self):
        bad = cdg_metadata(extent={"west": -44, "south": -20, "east": 500000, "north": -18})
        self.assertIn("extent", self.engine.evaluate(bad, "cdg")["invalid_required_values"])
        as_text = cdg_metadata(extent="-44.0,-20.0,-41.0,-18.0")
        self.assertTrue(self.engine.evaluate(as_text, "cdg")["is_conforme"])

    def test_scn_needs_scale_or_resolution(self):
        self.assertIn("spatialResolution", self.engine.evaluate(cdg_metadata(), "scn")["missing_required"])
        self.assertTrue(self.engine.evaluate(cdg_metadata(equivalentScale=50000), "scn")["is_conforme"])
        self.assertTrue(self.engine.evaluate(cdg_metadata(distance=0.5), "scn")["is_conforme"])
        result = self.engine.evaluate(cdg_metadata(equivalentScale="1:50.000"), "scn")
        self.assertIn("spatialResolution", result["invalid_required_values"])

    def test_old_field_names_still_read(self):
        data = general_metadata()
        data["metadataContact"] = data.pop("metadataContactName")
        data["resourceScope"] = data.pop("metadataScope")
        self.assertTrue(self.engine.evaluate(data, "general")["is_conforme"])


if __name__ == "__main__":
    unittest.main()
