"""Offline regressions for cross-platform packaging and identity/mount boundaries."""
import argparse
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


SPEC = importlib.util.spec_from_file_location("build_lambda_zip", Path(__file__).parents[1] / "build_lambda_zip.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
IMAGE = "sha256:" + "a" * 64


def intended_wif():
    return {
        "type": "external_account", "audience": MODULE.WIF.AUDIENCE,
        "subject_token_type": "urn:ietf:params:aws:token-type:aws4_request",
        "token_url": "https://sts.googleapis.com/v1/token",
        "credential_source": copy.deepcopy(MODULE.WIF.CREDENTIAL_SOURCE),
        "universe_domain": "googleapis.com",
        "service_account_impersonation_url": (
            "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/"
            f"{MODULE.WIF.INVOKER}:generateAccessToken"),
    }


class LambdaPackageTests(unittest.TestCase):
    def arguments(self, folder, document=None):
        wif = Path(folder) / "reviewed-wif.json"
        wif.write_text(json.dumps(intended_wif() if document is None else document), encoding="utf-8")
        return ["--image-id", IMAGE, "--wif-config", str(wif), "--output", str(Path(folder) / "build/new.zip")]

    def test_review_only_validates_inputs_without_docker_or_creating_outputs(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(MODULE.subprocess, "run") as run:
            args = self.arguments(folder)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(MODULE.main(args), 0)
            self.assertFalse((Path(folder) / "build").exists())
            self.assertIn("cloud trust/connectivity are unverified", output.getvalue())
            run.assert_not_called()

    def test_historical_wif_cannot_be_silently_reused(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(MODULE.subprocess, "run") as run:
            args = ["--image-id", IMAGE, "--wif-config", str(MODULE.ROOT / "config/google-wif.json"),
                    "--output", str(Path(folder) / "new.zip"), "--build"]
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(MODULE.main(args), 1)
            self.assertFalse((Path(folder) / "new.zip").exists())
            run.assert_not_called()

    def test_wif_rejects_wrong_identity_static_credentials_and_arbitrary_sources(self):
        variants = []
        for field, value in (("audience", "//iam.googleapis.com/projects/1086936100292/locations/global/workloadIdentityPools/ecoguard-aws/providers/aws-role"),
                             ("token_url", "https://example.invalid/token"),
                             ("type", "service_account"), ("private_key", "never-copy-this-fixture"),
                             ("service_account_impersonation_url", "https://example.invalid/token")):
            document = intended_wif()
            document[field] = value
            variants.append(document)
        for source in ({"file": "/host/credentials"}, {"executable": {"command": "untrusted"}},
                       {**MODULE.WIF.CREDENTIAL_SOURCE, "url": "https://example.invalid/credentials"},
                       {**MODULE.WIF.CREDENTIAL_SOURCE, "imdsv2_session_token_url": "https://example.invalid/"}):
            document = intended_wif()
            document["credential_source"] = source
            variants.append(document)
        for document in variants:
            with self.subTest(document=document), self.assertRaises(ValueError):
                MODULE.WIF.parse_personal_wif(json.dumps(document))
        with self.assertRaises(ValueError):
            MODULE.WIF.parse_personal_wif('{"type":"external_account","type":"external_account"}')
        with self.assertRaises(ValueError):
            MODULE.WIF.parse_personal_wif(b" " * (MODULE.WIF.MAX_DOCUMENT_BYTES + 1))

    def test_tag_injection_and_missing_explicit_inputs_are_rejected(self):
        for value in ("ecoguard:test", "sha256:abc", "sha256:" + "A" * 64, IMAGE + ";id", "--privileged"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                MODULE.image_id(value)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            MODULE.parse_args(["--image-id", IMAGE, "--output", "new.zip"])

    def test_bind_path_delimiters_source_links_and_output_replacement_fail(self):
        for path in ("/tmp/a,b", "/tmp/a\nb", "/tmp/a\x00b", "/tmp/a\x7fb"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                MODULE.safe_mount_path(path)
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source"
            source.mkdir()
            (source / "link").symlink_to(Path(folder) / "outside")
            with self.assertRaises(ValueError):
                MODULE.reject_source_links(source)
            args = self.arguments(folder)
            output = Path(args[-1])
            output.parent.mkdir()
            output.write_bytes(b"keep-existing-output")
            with contextlib.redirect_stderr(io.StringIO()), mock.patch.object(MODULE.subprocess, "run") as run:
                self.assertEqual(MODULE.main(args + ["--build"]), 1)
            self.assertEqual(output.read_bytes(), b"keep-existing-output")
            run.assert_not_called()

    def test_arm_image_is_rejected_without_starting_or_pulling_containers(self):
        args = MODULE.parse_args(["--image-id", IMAGE, "--wif-config", "reviewed.json", "--output", "new.zip"])
        with mock.patch.object(MODULE.shutil, "which", return_value="docker"), \
                mock.patch.object(MODULE.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, IMAGE + " linux arm64\n", "")) as run:
            with self.assertRaises(RuntimeError):
                MODULE.check_docker(args)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][1:3], ["image", "inspect"])

    def test_locked_install_and_offline_smoke_never_mount_host_credentials_or_whole_checkout(self):
        args = MODULE.parse_args(["--image-id", IMAGE, "--wif-config", "reviewed.json", "--output", "new.zip"])
        with tempfile.TemporaryDirectory() as folder:
            install = MODULE.docker_command(args, Path(folder))
            smoke = MODULE.docker_command(args, Path(folder), smoke=True)
        for command in (install, smoke):
            self.assertEqual(command[command.index("--pull") + 1], "never")
            self.assertEqual(command[command.index("--platform") + 1], "linux/amd64")
            self.assertIn(IMAGE, command)
            self.assertNotIn("--privileged", command)
            self.assertNotIn("--env-file", command)
            self.assertNotIn("--volume", command)
        mounts = [install[index + 1] for index, value in enumerate(install) if value == "--mount"]
        self.assertEqual(len(mounts), 2)
        self.assertIn("dst=/requirements.lock.txt,readonly", mounts[1])
        self.assertNotIn(f"src={MODULE.ROOT},", " ".join(mounts))
        for flag in ("--require-hashes", "--only-binary=:all:", "--no-compile", "--isolated"):
            self.assertIn(flag, install)
        self.assertEqual(install[-2:], ["-r", "/requirements.lock.txt"])
        self.assertNotIn("requirements-ric.lock.txt", " ".join(install))
        self.assertEqual(smoke[smoke.index("--network") + 1], "none")
        self.assertIn("-S", smoke)
        self.assertIn("dst=/package,readonly", " ".join(smoke))

    def test_native_library_architecture_and_python_mismatch_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "extension.so"
            header = bytearray(20)
            header[:6] = b"\x7fELF\x02\x01"
            header[18:20] = (62).to_bytes(2, "little")
            path.write_bytes(header)
            MODULE.check_native_files(Path(folder))
            for data in (b"\xcf\xfa\xed\xfe" + b"\0" * 16, b"MZ" + b"\0" * 18,
                         bytes(header[:18]) + (183).to_bytes(2, "little")):
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    MODULE.check_native_files(Path(folder))
            path.unlink()
            (Path(folder) / "extension.cpython-314-x86_64-linux-gnu.so").write_bytes(header)
            with self.assertRaises(ValueError):
                MODULE.check_native_files(Path(folder))

    def test_failed_dependency_install_cleans_only_its_fresh_stage(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "new.zip"
            sentinel = Path(folder) / "existing-directory"
            sentinel.mkdir()
            (sentinel / "keep").write_text("keep", encoding="utf-8")
            args = MODULE.parse_args(self.arguments(folder))
            with mock.patch.object(MODULE.subprocess, "run", side_effect=subprocess.CalledProcessError(1, ["docker"])):
                with self.assertRaises(subprocess.CalledProcessError):
                    MODULE.prepare_package(args, output, intended_wif())
            self.assertFalse(output.exists())
            self.assertEqual((sentinel / "keep").read_text(encoding="utf-8"), "keep")
            self.assertEqual(list(Path(folder).glob("ecoguard-lambda-*")), [])


if __name__ == "__main__":
    unittest.main()
