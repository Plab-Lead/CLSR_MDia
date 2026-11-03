"""Check that accuracy and both token metrics refer to the same pair."""

import csv
import subprocess
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/reproduce_mdia_token_efficiency.py"


def test_published_tables_match_the_paired_records(tmp_path):
    subprocess.run([sys.executable, "-B", str(SCRIPT), "--check"], check=True)
    subprocess.run([sys.executable, "-B", str(SCRIPT), "--output", str(tmp_path)], check=True)
    with (tmp_path / "audit.csv").open() as f:
        rows = {r["comparison"]: r for r in csv.DictReader(f)}
    for name in ("readme-table.md", "RESULTS.md"):
        headers = [
            line for line in (tmp_path / name).read_text().splitlines() if line.startswith("| Benchmark")
        ]
        assert headers
        for header in headers:
            assert [cell.strip() for cell in header.split("|") if "saved" in cell.lower()] == [
                "Generation saved"
            ]
    expected = set()
    for key, r in rows.items():
        n = int(r["questions"])
        for side in ("reference", "procedure"):
            pct = Decimal(100 * int(r[f"{side}_correct"])) / n
            assert r[f"{side}_accuracy_pct"] == str(pct.quantize(Decimal(".01"), rounding=ROUND_HALF_UP))
            assert int(r[f"{side}_input"]) + int(r[f"{side}_output"]) == int(r[f"{side}_total"])
        assert [field for field in r if field.endswith("_saved_pct")] == ["generation_saved_pct"]
        reference = Decimal(r["reference_output"])
        saved = 100 * (reference - Decimal(r["procedure_output"])) / reference
        assert Decimal(r["generation_saved_pct"]) == saved.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        if (
            int(r["procedure_correct"]) >= int(r["reference_correct"])
            and int(r["procedure_output"]) < int(r["reference_output"])
            and int(r["procedure_total"]) < int(r["reference_total"])
            and int(r["whole_groups"]) >= 96
            and r["reference_unknown_usage"] == r["procedure_unknown_usage"] == "0"
        ):
            expected.add(key)
    assert {key for key, r in rows.items() if r["overview"] == "True"} == expected
    # The two English comparators share a candidate, but their efficiency results differ.
    paired = rows["gpqa-pro"]
    adapted = rows["gpqa-pro/Source:obligation_english"]
    assert paired["procedure_output"] == adapted["procedure_output"]
    assert (paired["reference_accuracy_pct"], paired["generation_saved_pct"]) == ("65.63", "-0.40")
    assert (adapted["reference_accuracy_pct"], adapted["generation_saved_pct"]) == ("69.14", "+43.32")
    assert rows["C6"]["reference_accuracy_pct"] == rows["C6"]["procedure_accuracy_pct"] == "94.79"
    assert rows["crux-glm"]["also_lower_total"] == "False"
    assert rows["mmlu"]["reference_unknown_usage"] == "1"
    assert "mmlu" not in expected
    assert rows["math-flash"]["benchmark"] == "MATH (Level 5)"
