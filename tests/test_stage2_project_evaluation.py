from __future__ import annotations

import unittest

from helpers import cdg_metadata, general_metadata, quality_fields

from core.project_evaluator import ProjectEvaluator


class Stage2ProjectEvaluationTests(unittest.TestCase):
    def test_worst_layer_first(self):
        layers = [
            {"name": "camada_boa", "metadata": dict(cdg_metadata(), **quality_fields())},
            {"name": "camada_media", "metadata": cdg_metadata()},
            {"name": "camada_ruim", "metadata": {"resourceTitle": "Ruim"}},
        ]
        report = ProjectEvaluator().evaluate_layers(layers, resource_type="cdg")
        names = [row["layer_name"] for row in report["layers"]]
        self.assertEqual(names, ["camada_ruim", "camada_media", "camada_boa"])
        self.assertEqual(report["summary"]["worst_layer"], "camada_ruim")
        self.assertEqual(report["summary"]["conform_layers"], 2)
        self.assertEqual(report["summary"]["non_conform_layers"], 1)
        self.assertTrue(report["layers"][0]["issues"])

    def test_per_layer_resource_type(self):
        layers = [{"name": "doc", "resource_type": "general", "metadata": general_metadata()}]
        report = ProjectEvaluator().evaluate_layers(layers, resource_type="cdg")
        self.assertTrue(report["layers"][0]["is_conforme"])


if __name__ == "__main__":
    unittest.main()
