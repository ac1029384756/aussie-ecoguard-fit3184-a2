"""Offline preflight for a separate project's IAM/WIF-only setup.

No credentials, cloud clients, Terraform commands or mutations are used.
The input is an explicit JSON var-file, never the historical auto tfvars.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

MANIFEST = Path(__file__).resolve().parents[2] / "config/model.locked.json"
REQUIRED_OVERRIDES = {
    "project_id", "identity_only", "region", "aws_account_id", "aws_role_name",
    "aws_region", "cognito_issuer", "cognito_client_id", "media_bucket", "image",
    "manifest_sha256",
}


def validate_config(values, *, expected_project, expected_aws_account, expected_aws_role,
                    manifest_path=MANIFEST):
    if not isinstance(values, dict):
        raise ValueError("The var-file must be a JSON object.")
    missing = REQUIRED_OVERRIDES - values.keys()
    if missing:
        raise ValueError("Explicit overrides are missing: " + ", ".join(sorted(missing)))
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", expected_project):
        raise ValueError("The independently verified project ID is invalid.")
    if values["project_id"] != expected_project:
        raise ValueError("Project differs from the independently verified target; do not reuse the historical project.")
    if (not re.fullmatch(r"\d{12}", str(values["aws_account_id"]))
            or not isinstance(values["aws_account_id"], str)
            or values["aws_account_id"] != expected_aws_account):
        raise ValueError("AWS account must be independently verified and match the explicit var-file.")
    if (not isinstance(values["aws_role_name"], str)
            or not re.fullmatch(r"[A-Za-z0-9+=,.@_-]{1,64}", values["aws_role_name"])
            or values["aws_role_name"].startswith("REPLACE_")
            or values["aws_role_name"] != expected_aws_role):
        raise ValueError("AWS execution role must be independently verified and match the explicit var-file.")
    if values["identity_only"] is not True or values["image"] != "":
        raise ValueError("This preflight only permits identity_only=true and an empty image.")
    digest = hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest()
    if values["manifest_sha256"] != digest:
        raise ValueError("Manifest SHA-256 differs from config/model.locked.json; rebuild deployment inputs and image together.")
    # Blank application fields deliberately override the historical auto tfvars.
    if any(values[key] != "" for key in ("cognito_issuer", "cognito_client_id", "media_bucket")):
        raise ValueError("Identity setup must clear historical Cognito and media-bucket settings.")
    return {
        "project_id": values["project_id"],
        "identity_only": True,
        "manifest_sha256": digest,
        "status": "offline configuration check passed; cloud permissions, credits and Terraform state are unverified",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--var-file", type=Path, required=True, help="Explicit JSON .tfvars file")
    parser.add_argument("--expected-project", required=True, help="Project ID verified independently of this file")
    parser.add_argument("--expected-aws-account", required=True, help="AWS account ID verified independently")
    parser.add_argument("--expected-aws-role", required=True, help="AWS execution-role name verified independently")
    args = parser.parse_args(argv)
    try:
        result = validate_config(json.loads(args.var_file.read_text(encoding="utf-8")),
                                 expected_project=args.expected_project,
                                 expected_aws_account=args.expected_aws_account,
                                 expected_aws_role=args.expected_aws_role)
    except (OSError, ValueError) as error:
        print("Configuration rejected: " + str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
