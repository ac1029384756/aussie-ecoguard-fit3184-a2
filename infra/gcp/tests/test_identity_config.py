"""Offline deployment guards; no cloud SDK or Terraform installation required."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

GCP = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_identity_config", GCP / "check_identity_config.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class IdentityConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.values = json.loads((GCP / "ecoguard-fit3184-a2-2026.tfvars.json.example").read_text())
        self.values.update(aws_account_id="123456789012", aws_role_name="VerifiedWorkerRole")
        self.expected = dict(expected_project="ecoguard-fit3184-a2-2026",
                             expected_aws_account="123456789012", expected_aws_role="VerifiedWorkerRole")

    def test_complete_explicit_identity_configuration_passes(self):
        result = checker.validate_config(self.values, **self.expected)
        self.assertTrue(result["identity_only"])

    def test_example_cannot_trust_unconfirmed_aws_identity(self):
        example = json.loads((GCP / "ecoguard-fit3184-a2-2026.tfvars.json.example").read_text())
        with self.assertRaisesRegex(ValueError, "AWS account"):
            checker.validate_config(example, **self.expected)

    def test_historical_project_and_account_cannot_pass_for_new_target(self):
        for key, historical in (("project_id", "ecoguard-fit3184-jlii0474"),
                                ("aws_account_id", "360493183467"), ("aws_role_name", "LabRole")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                checker.validate_config({**self.values, key: historical}, **self.expected)

    def test_scope_sensitive_values_cannot_fall_through_to_auto_tfvars(self):
        for key in checker.REQUIRED_OVERRIDES:
            values = self.values.copy()
            del values[key]
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "overrides are missing"):
                checker.validate_config(values, **self.expected)

    def test_manifest_change_requires_updated_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "model.locked.json"
            manifest.write_bytes(checker.MANIFEST.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "SHA-256 differs"):
                checker.validate_config(self.values, **self.expected, manifest_path=manifest)

    def test_preflight_refuses_runtime_activation_and_historical_app_fields(self):
        for change in ({"identity_only": False}, {"image": "registry.example/image@sha256:abc"},
                       {"cognito_issuer": "https://historical.example"}, {"media_bucket": "historical-bucket"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                checker.validate_config({**self.values, **change}, **self.expected)


if __name__ == "__main__":
    unittest.main()
