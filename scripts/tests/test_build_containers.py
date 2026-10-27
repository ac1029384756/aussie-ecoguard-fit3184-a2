import contextlib
import importlib.util
import io
from pathlib import Path
import re
import shlex
import subprocess
import sys
import unittest
from unittest import mock


SPEC = importlib.util.spec_from_file_location("build_containers", Path(__file__).parents[1] / "build_containers.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ContainerBuildTests(unittest.TestCase):
    def test_both_services_pin_platform_context_and_local_output(self):
        for service, extra in (("inference", []), ("aws-ingest", ["--aws-lambda-ric-version", "4.2.2"])):
            with self.subTest(service=service):
                command = MODULE.build_command(MODULE.parse_args([service, "--image", "ecoguard:test-1", *extra]))
                self.assertEqual(command[command.index("--platform") + 1], "linux/amd64")
                self.assertEqual(command[command.index("--file") + 1], str(MODULE.DOCKERFILES[service]))
                self.assertEqual(command[-1], str(MODULE.ROOT))
                self.assertIn("--load", command)
                self.assertIn("--provenance=false", command)
                self.assertNotIn("--push", command)
                if service == "aws-ingest":
                    self.assertEqual(command[command.index("--build-arg") + 1], "AWS_LAMBDA_RIC_VERSION=4.2.2")
                else:
                    self.assertNotIn("--build-arg", command)

    def test_missing_or_floating_parameters_are_rejected(self):
        invalid = [["inference"],
                   *[["inference", "--image", image] for image in
                     ("ecoguard", "ecoguard:latest", "ecoguard:Latest", "localhost:5000/ecoguard", "ecoguard:*")],
                   ["aws-ingest", "--image", "ecoguard:test"],
                   *[["aws-ingest", "--image", "ecoguard:test", "--aws-lambda-ric-version", version]
                     for version in ("latest", "3", "3.1", "3.*", ">=3.1.1", "3.1.1 --push", "3.1.1", "4.2.3")],
                   ["inference", "--image", "ecoguard:test", "--aws-lambda-ric-version", "4.2.2"]]
        for arguments in invalid:
            with self.subTest(arguments=arguments), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    MODULE.parse_args(arguments)
                self.assertEqual(error.exception.code, 2)
        self.assertEqual(MODULE.image_tag("localhost:5000/ecoguard:v1"), "localhost:5000/ecoguard:v1")

    def test_explicit_base_image_requires_official_python_312_slim_digest(self):
        digest = "a" * 64
        self.assertEqual(MODULE.base_image("python:3.12-slim@sha256:" + "A" * 64),
                         "python:3.12-slim@sha256:" + digest)
        for service, extra in (("inference", []), ("aws-ingest", ["--aws-lambda-ric-version", "4.2.2"])):
            for tag in ("python:3.12-slim", "python:3.12-slim-bookworm"):
                with self.subTest(service=service, tag=tag):
                    image = f"{tag}@sha256:{digest}"
                    args = MODULE.parse_args([service, "--image", "ecoguard:test", "--base-image", image, *extra])
                    command = MODULE.build_command(args)
                    self.assertEqual(command[command.index(f"BASE_IMAGE={image}") - 1], "--build-arg")
        for image in ("python:3.12-slim", f"python:latest@sha256:{digest}",
                      f"other/python:3.12-slim@sha256:{digest}", f"python:3.11-slim@sha256:{digest}",
                      "python:3.12-slim@sha256:abc", "python:3.12-slim@sha256:" + "g" * 64):
            with self.subTest(image=image), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    MODULE.parse_args(["inference", "--image", "ecoguard:test", "--base-image", image])
                self.assertEqual(error.exception.code, 2)

    def test_ric_lock_and_dockerfile_keep_full_hash_checked_wheel_installation(self):
        lock = MODULE.RIC_LOCK.read_text(encoding="utf-8").replace("\\\n", " ")
        requirements = [line.strip() for line in lock.splitlines() if line.strip() and not line.lstrip().startswith("#")]
        self.assertEqual(len(requirements), 3)
        packages = {}
        for requirement in requirements:
            match = re.fullmatch(r"([a-z-]+)==([0-9]+\.[0-9]+\.[0-9]+)\s+--hash=sha256:([0-9a-f]{64})", requirement)
            self.assertIsNotNone(match, requirement)
            packages[match[1]] = match[2]
        self.assertEqual(packages, {"awslambdaric": "4.2.2", "simplejson": "3.20.2", "snapshot-restore-py": "1.0.0"})
        dockerfile = MODULE.DOCKERFILES["aws-ingest"].read_text(encoding="utf-8").replace("\\\n", " ")
        self.assertIn("COPY services/aws/requirements-ric.lock.txt ./requirements-ric.lock.txt", dockerfile)
        instruction = next(line[4:] for line in dockerfile.splitlines()
                           if line.startswith("RUN ") and "--require-hashes" in line)
        # Only run the Dockerfile's standard-library version gate, never pip or Docker.
        command = shlex.split(instruction)
        self.assertEqual(command[:2], ["python", "-c"])
        for environment in ({"AWS_LAMBDA_RIC_VERSION": "4.2.2"}, {},
                            {"AWS_LAMBDA_RIC_VERSION": "3.1.1"}, {"AWS_LAMBDA_RIC_VERSION": "4.2.2 --push"}):
            with self.subTest(environment=environment):
                # Windows needs SystemRoot to launch Python; no other host configuration is needed.
                child_environment = {"SystemRoot": MODULE.os.environ["SystemRoot"]} if MODULE.os.name == "nt" else {}
                child_environment.update(environment)
                result = subprocess.run([sys.executable, "-c", command[2]], cwd=MODULE.RIC_LOCK.parent,
                                        env=child_environment, capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0 if environment.get("AWS_LAMBDA_RIC_VERSION") == "4.2.2" else 1)
        segments = [shlex.split(segment) for segment in instruction.split(" && ")]
        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[1], ["python", "-m", "pip", "install", "--no-cache-dir", "--require-hashes",
                                     "--only-binary=awslambdaric,simplejson,snapshot-restore-py",
                                     "-r", "requirements.lock.txt", "-r", "requirements-ric.lock.txt"])
        self.assertEqual(segments[2], ["python", "-m", "pip", "check"])

    def test_default_and_explicit_dry_run_never_contact_docker(self):
        for extra in ([], ["--dry-run"]):
            with self.subTest(extra=extra), mock.patch.object(MODULE.subprocess, "run") as run, \
                    mock.patch.object(MODULE.shutil, "which", return_value=None) as which, \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(MODULE.main(["inference", "--image", "ecoguard:test", *extra]), 0)
                self.assertIn("linux/amd64", output.getvalue())
                run.assert_not_called()
                which.assert_not_called()

    def test_build_refuses_missing_cli_without_starting_any_process(self):
        with mock.patch.object(MODULE.shutil, "which", return_value=None), \
                mock.patch.object(MODULE.subprocess, "run") as run, \
                contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(MODULE.main(["inference", "--image", "ecoguard:test", "--build"]), 1)
            self.assertIn("Docker CLI is missing", output.getvalue())
            run.assert_not_called()

    def test_build_refuses_unavailable_or_non_linux_engine_or_missing_buildx(self):
        linux = subprocess.CompletedProcess([], 0, "linux\n", "")
        failed = subprocess.CompletedProcess([], 1, "", "unavailable")
        for responses in ([failed], [subprocess.CompletedProcess([], 0, "windows\n", "")],
                          [linux, failed], [subprocess.TimeoutExpired("docker", 15)]):
            with self.subTest(responses=responses), mock.patch.object(MODULE.shutil, "which", return_value="docker"), \
                    mock.patch.object(MODULE.subprocess, "run", side_effect=responses) as run, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(MODULE.main(["inference", "--image", "ecoguard:test", "--build"]), 1)
                self.assertLessEqual(run.call_count, 2)
                self.assertTrue(all("build" not in call.args[0] for call in run.call_args_list))

    def test_powershell_output_preserves_spaces_and_quotes_in_paths(self):
        with mock.patch.object(MODULE.os, "name", "nt"):
            self.assertEqual(MODULE.format_command(["docker", "a b/c'd"]), "& 'docker' 'a b/c''d'")

    def test_powershell_output_keeps_smart_quote_paths_inside_literals(self):
        paths = [
            ("C:/repo‘;Write-Output PWNED;‘/src", "'C:/repo‘‘;Write-Output PWNED;‘‘/src'"),
            ("C:/repo’;Write-Output PWNED;’/src", "'C:/repo’’;Write-Output PWNED;’’/src'"),
            ("C:/repo‚;Write-Output PWNED;‚/src", "'C:/repo‚‚;Write-Output PWNED;‚‚/src'"),
            ("C:/repo‛;Write-Output PWNED;‛/src", "'C:/repo‛‛;Write-Output PWNED;‛‛/src'"),
        ]
        with mock.patch.object(MODULE.os, "name", "nt"):
            for path, literal in paths:
                with self.subTest(path=path):
                    self.assertEqual(MODULE.format_command(["docker", path]), "& 'docker' " + literal)

    def test_build_executes_the_argument_list_without_a_shell(self):
        responses = [subprocess.CompletedProcess([], 0, "linux\n", ""),
                     subprocess.CompletedProcess([], 0, "buildx\n", ""),
                     subprocess.CompletedProcess([], 0, "", "")]
        with mock.patch.object(MODULE.shutil, "which", return_value="docker"), \
                mock.patch.object(MODULE.subprocess, "run", side_effect=responses) as run, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(MODULE.main(["inference", "--image", "ecoguard:test", "--build"]), 0)
        build = run.call_args_list[-1]
        self.assertIsInstance(build.args[0], list)
        self.assertEqual(build.args[0], MODULE.build_command(
            MODULE.parse_args(["inference", "--image", "ecoguard:test", "--build"])))
        self.assertIs(build.kwargs["shell"], False)

    def test_cli_rejects_shell_operators_and_injected_options(self):
        for image in ("--push", "ecoguard:x;Write-Output PWNED", "ecoguard:x$(id)", "ecoguard:x\n--push"):
            with self.subTest(image=image), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    MODULE.parse_args(["inference", "--image=" + image])
                self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
