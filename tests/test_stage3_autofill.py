from __future__ import annotations

import datetime as dt
import unittest

from helpers import cdg_metadata

from core.autofill import apply_changes, propose_fill
from core.evaluation_engine import MetadataEvaluationEngine

TODAY = dt.date(2026, 11, 9)
VECTOR_FACTS = {
    "kind": "vector",
    "encoding": "UTF-8",
    "crs": "EPSG:31983",
    "extent": {"west": -44.04, "south": -20.79, "east": -43.07, "north": -19.88},
}


def fill(metadata, facts=VECTOR_FACTS):
    return propose_fill(metadata, facts, today=TODAY, new_id=lambda: "uuid-fixo")


class AutofillTests(unittest.TestCase):
    def setUp(self):
        self.engine = MetadataEvaluationEngine()

    def test_fills_calculable_fields_of_empty_layer(self):
        changes = {c["id"]: c["new"] for c in fill({"resourceTitle": "Limites"})}
        self.assertEqual(changes["metadataIdentifier"], "uuid-fixo")
        self.assertEqual(changes["metadataProfile"], "Perfil MGB 2.0")
        self.assertEqual(changes["metadataScope"], "dataset")
        self.assertEqual(changes["metadataCharacterSet"], "UTF-8")
        self.assertEqual(changes["metadataDate"], "2026-11-09")
        self.assertEqual(changes["metadataDateType"], "creation")
        self.assertEqual(changes["spatialRepresentationType"], "vector")
        self.assertEqual(changes["resourceCharacterSet"], "UTF-8")
        self.assertEqual(changes["extent"], VECTOR_FACTS["extent"])
        self.assertEqual(changes["referenceSystem"], "EPSG:31983")
        self.assertNotIn("resourceTitle", changes)
        self.assertNotIn("resourceStatus", changes)  # não é calculável

    def test_never_overwrites_valid_values(self):
        complete = cdg_metadata(referenceSystem="EPSG:4674")
        self.assertEqual(fill(complete), [])

    def test_fixes_language_with_safe_suggestion(self):
        changes = {c["id"]: c for c in fill(cdg_metadata(resourceLanguage="pt-BR"))}
        self.assertEqual(changes["resourceLanguage"]["old"], "pt-BR")
        self.assertEqual(changes["resourceLanguage"]["new"], "por")

    def test_system_encoding_is_not_guessed_for_vector(self):
        facts = dict(VECTOR_FACTS, encoding="System")
        changes = {c["id"] for c in fill({}, facts)}
        self.assertNotIn("resourceCharacterSet", changes)

    def test_raster_gets_grid_and_pixel_size(self):
        facts = {"kind": "raster", "crs": "EPSG:31983", "pixelSizeMeters": 30.0, "extent": VECTOR_FACTS["extent"]}
        changes = {c["id"]: c["new"] for c in fill({}, facts)}
        self.assertEqual(changes["spatialRepresentationType"], "grid")
        self.assertEqual(changes["distance"], 30.0)
        self.assertEqual(changes["resourceCharacterSet"], "UTF-8")

    def test_after_fill_only_human_fields_remain(self):
        start = {"resourceTitle": "Limites"}
        filled = apply_changes(start, fill(start))
        missing = set(self.engine.evaluate(filled, "cdg")["missing_required"])
        self.assertEqual(missing, {
            "metadataContactRole", "metadataContactName", "resourceDate", "resourceDateType",
            "resourceAbstract", "resourceStatus", "resourceContactName", "topicCategory",
        })


if __name__ == "__main__":
    unittest.main()
