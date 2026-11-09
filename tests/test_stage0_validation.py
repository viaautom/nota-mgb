from __future__ import annotations

import unittest

import helpers  # noqa: F401  (ajusta sys.path)

from core.domain_catalog import DomainCatalog
from core.qgis_metadata_adapter import QgisMetadataAdapter
from core.schema_policy import SchemaPolicy


class DomainCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = DomainCatalog()

    def test_official_quadros_present_with_full_lists(self):
        expected = {
            "MD_TopicCategoryCode": (58, 21),
            "CI_DateTypeCode": (71, 8),
            "CI_RoleCode": (73, 16),
            "MD_ProgressCode": (75, 8),
            "MD_ScopeCode": (76, 21),
            "MD_SpatialRepresentationTypeCode": (77, 6),
            "LanguageCode": (78, 7),
        }
        for domain, (quadro, size) in expected.items():
            self.assertEqual(self.catalog.quadro(domain), quadro, domain)
            self.assertEqual(len(self.catalog.domains[domain]["values"]), size, domain)

    def test_mgb_specific_values(self):
        self.assertTrue(self.catalog.validate("MD_TopicCategoryCode", "disaster"))
        self.assertTrue(self.catalog.validate("MD_ProgressCode", "superseded"))
        self.assertTrue(self.catalog.validate("MD_ProgressCode", "COMPLETED"))
        self.assertFalse(self.catalog.validate("CI_RoleCode", "user"))  # não existe no MGB 2.0
        self.assertEqual(self.catalog.label("MD_TopicCategoryCode", "structure"), "Edificação")

    def test_language_is_iso_639_2(self):
        self.assertTrue(self.catalog.validate("LanguageCode", "por"))
        self.assertTrue(self.catalog.validate("LanguageCode", "tup"))  # qualquer ISO 639-2
        self.assertFalse(self.catalog.validate("LanguageCode", "pt-BR"))
        self.assertEqual(self.catalog.suggest("LanguageCode", "pt-BR"), "por")

    def test_charset_accepts_iana_and_iso_codelist(self):
        self.assertEqual(self.catalog.normalize("MD_CharacterSetCode", "utf8"), "UTF-8")
        self.assertEqual(self.catalog.normalize("MD_CharacterSetCode", "utf-8"), "UTF-8")
        self.assertFalse(self.catalog.validate("MD_CharacterSetCode", "System"))


class SchemaAndApiTests(unittest.TestCase):
    def test_schema_policy_targets_inde_19115_3(self):
        policy = SchemaPolicy()
        self.assertEqual(policy.default_export_schema(), "ISO 19115-3:2016")
        self.assertEqual(policy.INDE_SCHEMA_ID, "iso19115-3.mgb")
        self.assertIn("ISO 19139", policy.import_schema_compatibility())
        self.assertEqual(policy.xml_charset_code("UTF-8"), "utf8")

    def test_qgis_api_summary(self):
        summary = QgisMetadataAdapter.get_supported_api_summary()
        self.assertEqual(summary["min_version"], "3.28")
        self.assertEqual(summary["dates_api_version"], "3.30")

    def test_adapter_reads_plugin_block_without_qgis(self):
        class FakeLayer:
            def customProperty(self, key, default=""):
                return '{"resourceStatus": "completed", "metadataProfile": "Perfil MGB 2.0"}'

        data = QgisMetadataAdapter.extract_layer_metadata(FakeLayer())
        self.assertEqual(data["resourceStatus"], "completed")


if __name__ == "__main__":
    unittest.main()
