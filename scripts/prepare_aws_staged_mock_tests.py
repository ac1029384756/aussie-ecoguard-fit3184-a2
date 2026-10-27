#!/usr/bin/env python3
"""Prepare a fresh, offline Terraform mock-test copy. Never execute Terraform.

The production legacy child provider is intentionally preserved in source. Only
the throwaway copy loses that provider block so personal tests inherit the mock.
No state, credentials, provider caches, real Lambda ZIPs or cloud tools are read.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys


PROVIDER = re.compile(r'(?ms)^provider "aws" \{\n.*?^\}\n')
REAL_PROVIDER = re.compile(r'(?m)^\s*provider\s+"')
FIXTURES = (
    "infra/aws/tests/fixtures/plan-only-package.txt",
    "infra/aws/environments/personal/tests/fixtures/hash-mismatch.zip",
)
SUITES = (
    "infra/aws/tests/runtime_controls.tftest.hcl",
    "infra/aws/tests/ecr_pull_policy.tftest.hcl",
    "infra/aws/tests/low_quota_processing.tftest.hcl",
    "infra/aws/environments/personal/tests/stages.tftest.hcl",
    "infra/aws/environments/personal/tests/processing_bounded.tftest.hcl",
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def prepare(source, output):
    source, output = source.resolve(), output.resolve()
    if output == source or source in output.parents:
        raise ValueError("Choose a fresh output directory outside the source checkout.")
    if output.exists():
        raise ValueError("Refusing to overwrite an existing output directory.")
    aws = source / "infra/aws"
    paths = set(aws.glob("*.tf")) | {
        aws / ".terraform.lock.hcl",
        aws / "deployment.auto.tfvars",
        aws / "environments/personal/main.tf",
        aws / "environments/personal/.terraform.lock.hcl",
        *(source / name for name in FIXTURES + SUITES),
    }
    contents = {}
    for path in sorted(paths):
        if not path.is_file() or any(parent.is_symlink() for parent in (path, *path.parents) if parent != source and source in parent.parents):
            raise ValueError("Required public test source is missing or symlinked: " + str(path.relative_to(source)))
        contents[path.relative_to(source).as_posix()] = path.read_bytes()
    versions = "infra/aws/versions.tf"
    provider_text = contents[versions].decode("utf-8")
    blocks = list(PROVIDER.finditer(provider_text))
    if len(blocks) != 1 or "allowed_account_ids = var.allowed_account_ids" not in blocks[0][0]:
        raise ValueError("Expected exactly the known legacy AWS provider configuration.")
    prepared = dict(contents)
    prepared[versions] = PROVIDER.sub("", provider_text).encode("utf-8")
    prepared["infra/aws/.terraform.lock.hcl"] = contents["infra/aws/environments/personal/.terraform.lock.hcl"]
    if any(REAL_PROVIDER.search(data.decode("utf-8")) for name, data in prepared.items()
           if name.endswith((".tf", ".tftest.hcl"))):
        raise ValueError("The test copy would still contain a real provider declaration.")
    for name in SUITES:
        text = prepared[name].decode("utf-8")
        runs = re.findall(r'(?m)^\s*run\s+"[^"]+"\s*\{', text)
        plans = re.findall(r'(?m)^\s*command\s*=\s*plan\s*$', text)
        if 'mock_provider "aws"' not in text or not runs or len(runs) != len(plans):
            raise ValueError("Every selected suite must remain mock-provider plan tests.")
    changes = {
        name: {"source_sha256": digest(contents[name]), "harness_sha256": digest(data)}
        for name, data in prepared.items() if contents[name] != data
    }
    if set(changes) - {versions, "infra/aws/.terraform.lock.hcl"}:
        raise ValueError("Unexpected transformation outside provider configuration/platform lock.")
    output.mkdir(parents=True, exist_ok=False)
    for name, data in sorted(prepared.items()):
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    manifest = {
        "test_only": True,
        "source_root": str(source),
        "files": {name: {"source_sha256": digest(contents[name]), "harness_sha256": digest(data)}
                  for name, data in sorted(prepared.items())},
        "only_changes": changes,
        "real_provider_declarations_remaining": [],
        "copied_state_credentials_provider_caches_or_real_lambda_zip": False,
        "resource_variable_local_and_test_code_unchanged": True,
    }
    (output / "HARNESS-MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="Source checkout; defaults to this script's repository root.")
    parser.add_argument("--output", type=Path, required=True,
                        help="Fresh test directory outside the source checkout; existing paths are refused.")
    args = parser.parse_args()
    try:
        report = prepare(args.source_root, args.output)
    except (KeyError, OSError, UnicodeError, ValueError) as error:
        print("Cannot prepare mock tests: " + str(error), file=sys.stderr)
        return 1
    print("Prepared test-only source: " + str(args.output.resolve()))
    print("Copied public files: " + str(len(report["files"])))
    print("Only transformations: legacy provider removal and optional shared platform-lock copy.")
    print("No Terraform, installation, Docker or cloud operation executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
