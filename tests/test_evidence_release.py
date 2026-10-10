# ruff: noqa: E402
"""Guard scientific identity, accounting and portable publication inputs."""

import copy
import json
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from _mdia_evidence_math import bfcl_check_alias, core_aggregate, core_paired
from verify_mdia_release import resolve_member, validate_scalar_row

ART = ROOT / "artifacts/research/20261005"


class EvidenceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (ART / "data/core/paired_case_data.jsonl").open() as handle:
            cls.core = json.loads(handle.readline())
        cls.bfcl = [json.loads(x) for x in (ART / "data/bfcl192/scalar_rows.jsonl").read_text().splitlines()]

    def test_whole_cost_availability_survives_missing_usage(self):
        row = copy.deepcopy(self.core)
        row.update(cost_unknown_attempts=1, input_tokens=None, output_tokens=None)
        result = core_aggregate([row])
        self.assertIsNone(result["generated"])
        self.assertIsNone(result["input"])
        self.assertFalse(result["cost_available"])

    def test_alias_cannot_change_cost_or_grade(self):
        alias = next(r for r in self.bfcl if r["exact_alias_of_record_id"])
        parent = next(r for r in self.bfcl if r["record_id"] == alias["exact_alias_of_record_id"])
        bfcl_check_alias(alias, parent)
        changed = copy.deepcopy(alias)
        changed["generated"] += 1
        with self.assertRaises(AssertionError):
            bfcl_check_alias(changed, parent)
        changed = copy.deepcopy(alias)
        changed["correct"] = not changed["correct"]
        with self.assertRaises(AssertionError):
            bfcl_check_alias(changed, parent)

    def test_pairing_rejects_different_whole_groups(self):
        a = dict(self.core, side="candidate")
        b = dict(self.core, side="reference", group_key="0" * 64)
        self.assertNotEqual(a["group_key"], b["group_key"])
        with self.assertRaises(AssertionError):
            core_paired([a, b], 0, B=10)

    def test_publication_schema_rejects_raw_question_fields(self):
        name = "data/core/paired_case_data.jsonl"
        validate_scalar_row(name, self.core)
        with self.assertRaises(ValueError):
            validate_scalar_row(name, dict(self.core, question="synthetic test string"))

    def test_manifest_rejects_traversal_and_absolute_paths(self):
        for path in ["../outside.json", "/tmp/outside.json", "nested/../../outside.json"]:
            with self.assertRaises(ValueError):
                resolve_member(ROOT, path)


if __name__ == "__main__":
    unittest.main()
