#!/usr/bin/env python3
# ruff: noqa: B905
"""Verify portable MDia evidence hashes, scalar schemas, provenance and links."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
ART = Path("artifacts/research/20261005")

FIELDS = {
    "data/core/paired_case_data.jsonl": set(
        "call_keys case_key correct cost_unknown_attempts finish_reason group_key input_tokens original_grader_digest output_tokens pair_id parse_ok query_hash record_id side source_review_sha256 trial".split()
    ),
    "data/bfcl192/scalar_rows.jsonl": set(
        "arm correct cost_unknown_attempts derived_frozen_grader_fingerprint exact_alias_of_record_id finish_reason finish_reason_source generated grade_certificate_record_id group_order group_sha256 imported input original_api_ok_absent original_diagnosis_sha256 original_finish_reason_absent original_grader_digest_absent original_grader_digest_sha256 parse_ok record_id source_task_sha256".split()
    ),
    "data/crux192/SAFE_SCALAR_ROWS.jsonl": set(
        "arm backbone correct finish_reason generated_completed_response_tokens imported input_completed_response_tokens missing_usage_count passed_review_sha256 raw_row_sha256 record_digest registered_parse_ok source_task_digest whole_attempt_cost_available whole_group_digest".split()
    ),
}
EXPECTED_ROWS = dict(zip(FIELDS, [2752, 6912, 6912]))
DIGEST_FIELDS = {
    "case_key",
    "group_key",
    "original_grader_digest",
    "query_hash",
    "record_id",
    "source_review_sha256",
    "derived_frozen_grader_fingerprint",
    "exact_alias_of_record_id",
    "grade_certificate_record_id",
    "group_sha256",
    "original_diagnosis_sha256",
    "original_grader_digest_sha256",
    "source_task_sha256",
    "passed_review_sha256",
    "raw_row_sha256",
    "record_digest",
    "source_task_digest",
    "whole_group_digest",
}
BOOL_FIELDS = {
    "correct",
    "parse_ok",
    "imported",
    "original_api_ok_absent",
    "original_finish_reason_absent",
    "original_grader_digest_absent",
    "registered_parse_ok",
    "whole_attempt_cost_available",
}
INTEGER_FIELDS = {
    "cost_unknown_attempts",
    "input_tokens",
    "output_tokens",
    "trial",
    "generated",
    "group_order",
    "input",
    "generated_completed_response_tokens",
    "input_completed_response_tokens",
    "missing_usage_count",
}


def digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def resolve_member(root, name):
    p = Path(name)
    if p.is_absolute() or not p.parts or ".." in p.parts or "\\" in name:
        raise ValueError("Invalid release member: " + name)
    target = root / p
    if any((root / Path(*p.parts[:i])).is_symlink() for i in range(1, len(p.parts) + 1)):
        raise ValueError("Symlink in release member: " + name)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("Release member escapes root: " + name)
    return target


def verify_manifest(root=ROOT):
    root = Path(root)
    manifest = json.loads((root / "MDIA_RESEARCH_RELEASE_MANIFEST.json").read_text())
    if manifest["schema"] != "mdia-research-release-v1":
        raise ValueError("Unsupported manifest schema")
    for name, item in manifest["files"].items():
        actual = resolve_member(root, name)
        payload = actual.read_bytes()
        if len(payload) != item["bytes"] or hashlib.sha256(payload).hexdigest() != item["sha256"]:
            raise ValueError("Checksum mismatch: " + name)
    return len(manifest["files"])


def validate_scalar_row(name, row):
    if set(row) != FIELDS[name]:
        raise ValueError("Unexpected scalar fields: " + name)
    for key, value in row.items():
        if key in DIGEST_FIELDS and value is not None and not digest(value):
            raise ValueError("Invalid opaque identifier: " + key)
        if key in BOOL_FIELDS and type(value) is not bool:
            raise ValueError("Invalid boolean: " + key)
        if key in INTEGER_FIELDS and value is not None and (type(value) is not int or value < 0):
            raise ValueError("Invalid scalar: " + key)
    if "call_keys" in row and not (
        isinstance(row["call_keys"], list) and all(digest(x) for x in row["call_keys"])
    ):
        raise ValueError("Invalid call-key digests")
    if row.get("finish_reason") not in ["stop", "length", None]:
        raise ValueError("Unexpected finish-reason value")


def check_publication_inputs(root=ROOT):
    root = Path(root)
    count = 0
    for name, _fields in FIELDS.items():
        rows = [json.loads(x) for x in (root / ART / name).read_text().splitlines() if x]
        if len(rows) != EXPECTED_ROWS[name]:
            raise ValueError("Unexpected observation count: " + name)
        for row in rows:
            validate_scalar_row(name, row)
        count += len(rows)
    specs = json.loads((root / ART / "protocols/serving_spec_examples.json").read_text())
    allowed = set(
        "registry_card_id served_spec_sha256 source_artifact_sha256 benchmark style generation parent_ids serving_spec".split()
    )
    for spec in specs:
        if set(spec) != allowed or not isinstance(spec["serving_spec"], str):
            raise ValueError("Unexpected serving-spec fields")
        if hashlib.sha256(spec["serving_spec"].encode()).hexdigest() != spec["served_spec_sha256"]:
            raise ValueError("Serving-spec content hash mismatch")
    manifest = json.loads((root / "MDIA_RESEARCH_RELEASE_MANIFEST.json").read_text())
    private_path = re.compile(r"/(?:Users|home|data)/[A-Za-z0-9_.-]+")
    credential = re.compile(r"(?:sk-[A-Za-z0-9]{24,}|AKIA[A-Z0-9]{16}|BEGIN [A-Z ]*PRIVATE KEY)")
    for name in manifest["files"]:
        if Path(name).suffix.lower() not in {".py", ".json", ".jsonl", ".md", ".txt", ".csv", ".svg"}:
            continue
        content = (root / name).read_text()
        if private_path.search(content) or credential.search(content):
            raise ValueError("Private-content pattern in publication member: " + name)
    return count


def verify_links(root=ROOT):
    root = Path(root)
    manifest = json.loads((root / "MDIA_RESEARCH_RELEASE_MANIFEST.json").read_text())
    total = 0
    for name in manifest["files"]:
        if not name.endswith(".md"):
            continue
        source = root / name
        for raw in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", source.read_text()):
            ref = raw.split()[0].strip("<>")
            if ref.startswith(("https://", "http://", "mailto:", "#")):
                continue
            dest = (source.parent / unquote(ref.split("#")[0])).resolve()
            if not dest.is_relative_to(root.resolve()) or not dest.exists():
                raise ValueError("Unresolved local link in " + name + ": " + ref)
            total += 1
    return total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    files = verify_manifest(args.root)
    rows = check_publication_inputs(args.root)
    links = verify_links(args.root)
    print(
        json.dumps(
            {
                "passed": True,
                "checksummed_files": files,
                "scalar_rows": rows,
                "local_links": links,
                "publication_schema_and_provenance": "passed",
            }
        )
    )


if __name__ == "__main__":
    main()
