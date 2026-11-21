"""Check that conflicting workbook aliases do not merge canonical names."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from scanner_v2_master import approved_aliases


class MasterAliasTests(unittest.TestCase):
    def test_reciprocal_aliases_preserve_both_canonical_names(self):
        aliases, conflicts = approved_aliases(
            [("Pear", "Gold Pear"), ("Gold Pear", "Pear"), ("Golden Pear", "Gold Pear")],
            ["Pear", "Gold Pear"],
            "variety",
        )
        self.assertEqual(aliases, {"Golden Pear": "Gold Pear"})
        self.assertEqual({entry["alias"] for entry in conflicts}, {"pear", "gold pear"})

    def test_only_canonical_targets_can_be_used(self):
        with self.assertRaisesRegex(ValueError, "no canonical target"):
            approved_aliases([("Early Pear", "Missing Name")], ["Pear"], "variety")


if __name__ == "__main__":
    unittest.main()
