import json
import unittest
from pathlib import Path

from labspec.seed import InvalidSeed, derive_name, derive_token, format_seed, normalise_seed
from labspec.validator import SchemaError, validate

SCHEMA = json.loads((Path(__file__).resolve().parent.parent / "labspec/schema/manifest.schema.json").read_text())


class SeedTest(unittest.TestCase):
    def test_normalises_and_formats(self):
        self.assertEqual(normalise_seed(" k7q2-mx4p "), "K7Q2MX4P")
        self.assertEqual(format_seed("K7Q2MX4P"), "K7Q2-MX4P")

    def test_rejects_ambiguous_characters(self):
        for bad in ("K7Q2MX4I", "K7Q2MX4", "K7Q2-MX4P-1", "K7Q2MX4O"):
            with self.assertRaises(InvalidSeed):
                normalise_seed(bad)

    def test_derivation_is_deterministic_and_seed_specific(self):
        a = derive_name("storage-sas-leak", "K7Q2MX4P", "storageAccount", "bwsas", 10)
        self.assertEqual(a, derive_name("storage-sas-leak", "k7q2-mx4p", "storageAccount", "bwsas", 10))
        self.assertNotEqual(a, derive_name("storage-sas-leak", "K7Q2MX4Q", "storageAccount", "bwsas", 10))
        self.assertRegex(a, r"^bwsas[0-9a-z]{10}$")
        self.assertEqual(len(derive_token("storage-sas-leak", "K7Q2MX4P", "marker")), 24)


class ValidatorTest(unittest.TestCase):
    def test_schema_uses_only_supported_keywords(self):
        validate({}, SCHEMA)  # raises SchemaError if the schema uses an unsupported keyword

    def test_unknown_keyword_is_refused(self):
        with self.assertRaises(SchemaError):
            validate(1, {"type": "integer", "multipleOf": 2})

    def test_reports_missing_required_and_extra_properties(self):
        errors = validate({"bogus": 1}, SCHEMA)
        self.assertTrue(any("missing required property 'id'" in e for e in errors))
        self.assertTrue(any("unexpected property 'bogus'" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
