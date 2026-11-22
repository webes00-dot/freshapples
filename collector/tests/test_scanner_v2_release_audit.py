"""Check audit batch assignment and coverage across partial retries."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from scanner_v2_release_audit import STORE_TIMEOUT_STATUS, audit_plan, combine_batches, write_capture_report


class ReleaseAuditTests(unittest.TestCase):
    def test_partial_artifacts_and_retries_preserve_coverage(self):
        directory = [
            {"id": f"store-{index}", "name": f"Store {index}", "menu_url": f"https://store-{index}.example/menu"}
            for index in range(25)
        ]
        directory.append({"id": "skipped", "name": "No menu"})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "directory.json"
            source.write_text(json.dumps(directory))
            _, batches, skipped = audit_plan(source)
            self.assertEqual(len(batches), 10)
            self.assertEqual(sorted(row["id"] for batch in batches for row in batch),
                             sorted(row["id"] for row in directory[:-1]))
            self.assertEqual([len(batch) for batch in batches], [3] * 5 + [2] * 5)
            first, second, third = batches[0]

            def save(attempt, row, status, cards):
                folder = root / f"v2-menu-batch-1-attempt-{attempt}"
                folder.mkdir(exist_ok=True)
                result = {"id": row["id"], "retailer": row["name"], "menu_url": row["menu_url"],
                          "products": cards, "pages": int(bool(cards)), "statuses": [status]}
                (folder / f"retailer-{row['id']}.json").write_text(json.dumps(result))

            save(1, first, "Cards captured", ["first"])
            save(1, second, STORE_TIMEOUT_STATUS, [])
            save(2, first, STORE_TIMEOUT_STATUS, [])
            save(2, second, "Cards captured", ["second"])
            save(2, third, STORE_TIMEOUT_STATUS, [])
            combined = combine_batches(directory, batches, skipped, root)
            self.assertEqual(combined["batches"][0], {"batch": 1, "targets": 3, "finished": 2})
            self.assertEqual([row["products"] for row in combined["results"]], [["first"], ["second"], []])
            self.assertEqual(len(combined["missing"]), 22)
            self.assertEqual(combined["skipped"][0][0]["id"], "skipped")
            report = root / "report"
            report.mkdir()
            write_capture_report(report, combined)
            self.assertEqual(len((report / "retailer-coverage.csv").read_text().splitlines()), len(directory) + 1)
