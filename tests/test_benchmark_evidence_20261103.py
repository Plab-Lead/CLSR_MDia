"""Check the numerical release and the pairing used by the deployment comparison."""

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/reproduce_mdia_evidence_20261103.py"


def test_published_outputs_reproduce_offline():
    subprocess.run([sys.executable, "-B", str(SCRIPT), "--check"], cwd=ROOT, check=True)


def test_joint_outcomes_matter_even_when_deployment_margins_match():
    spec = importlib.util.spec_from_file_location("mdia_evidence_nov03", SCRIPT)
    analysis = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analysis)
    labels = ("loss", "tie", "win")
    aligned = {i: dict.fromkeys(labels, 0) for i in labels}
    crossed = {i: dict.fromkeys(labels, 0) for i in labels}
    aligned["loss"]["loss"] = aligned["win"]["win"] = 1
    crossed["loss"]["win"] = crossed["win"]["loss"] = 1
    assert analysis.deployment_contrast(aligned, 2) == (0, [0, 0])
    assert analysis.deployment_contrast(crossed, 2) == (0, [-200, 200])
