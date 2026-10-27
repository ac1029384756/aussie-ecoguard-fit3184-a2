"""Prepare a real Linux/Python 3.12 Lambda ZIP using an existing local Docker image.

The default is a local, print-only review. --build downloads hash-locked business
wheels into a fresh temporary directory, runs an offline package smoke check and
creates a ZIP. No registry pull/push, cloud credentials or deployment is used.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("lambda_wif", ROOT / "scripts/lambda_wif.py")
WIF = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WIF)

# -S makes this smoke check depend on the staged ZIP contents, not the image's
# already-installed site-packages. No Lambda handler or runtime() is invoked.
SMOKE = r'''
import importlib, io, platform, sys
assert sys.version_info[:2] == (3, 12), "Python 3.12 is required"
assert platform.system() == "Linux" and platform.machine() == "x86_64"
sys.path.insert(0, "/package")
for name in ("boto3", "google.auth", "requests", "PIL.Image", "cryptography", "pydantic"):
    module = importlib.import_module(name)
    assert module.__file__.startswith("/package/"), "Dependency came from outside the package"
from PIL import Image
data = io.BytesIO()
Image.new("RGB", (8, 8), "green").save(data, format="JPEG")
data.seek(0)
assert Image.open(data).size == (8, 8)
from cryptography.hazmat.primitives import hashes
digest = hashes.Hash(hashes.SHA256())
digest.update(b"ecoguard-offline-package-check")
assert len(digest.finalize()) == 32
from pydantic import BaseModel
class Check(BaseModel):
    value: int
assert Check(value="12").value == 12
from ecoguard_aws.config import Config
from ecoguard_aws.pet_scoring import calibration
assert Config.from_env().mode == "aws"
assert calibration()
handlers = importlib.import_module("ecoguard_aws.handlers")
for name in ("api", "infer", "delete", "notify", "outbox", "cleanup", "lex_fulfillment"):
    assert callable(getattr(handlers, name))
assert importlib.import_module("ecoguard_aws.runtime")._runtime is None
print("Offline staged package imports/native libraries passed; no handlers or cloud calls ran.")
'''


def image_id(value):
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise argparse.ArgumentTypeError("--image-id requires the full immutable local sha256 image ID")
    return value


def safe_mount_path(path):
    path = Path(path).resolve()
    if any(character == "," or ord(character) < 32 or ord(character) == 127 for character in str(path)):
        raise ValueError("Docker bind paths cannot contain commas or control characters")
    return path


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-id", required=True, type=image_id,
                        help="full ID of the already reviewed local Linux amd64 Python 3.12 image")
    parser.add_argument("--wif-config", required=True, type=Path,
                        help="explicit caller-reviewed public WIF JSON for the intended personal project")
    parser.add_argument("--output", required=True, type=Path, help="new ZIP path; existing files are never replaced")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="review inputs/operations only; no Docker or writes (default)")
    mode.add_argument("--build", action="store_true", help="install locked wheels, smoke check offline, then create the ZIP")
    return parser.parse_args(argv)


def docker_command(args, stage, *, smoke=False):
    lock = safe_mount_path(ROOT / "services/aws/requirements.lock.txt")
    stage = safe_mount_path(stage)
    user = f"{os.getuid()}:{os.getgid()}" if hasattr(os, "getuid") else "1000:1000"
    command = ["docker", "run", "--rm", "--pull", "never", "--platform", "linux/amd64",
               "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
               "--user", user, "--tmpfs", "/tmp:rw,noexec,nosuid,size=536870912",
               "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "ECO_MODE=aws",
               "--env", "AWS_EC2_METADATA_DISABLED=true", "--workdir", "/tmp",
               "--mount", f"type=bind,src={stage},dst=/package" + (",readonly" if smoke else ""),
               "--entrypoint", "python"]
    if smoke:
        return command + ["--network", "none", args.image_id, "-S", "-B", "-c", SMOKE]
    return command + ["--mount", f"type=bind,src={lock},dst=/requirements.lock.txt,readonly", args.image_id,
                      "-B", "-m", "pip", "--isolated", "install", "--disable-pip-version-check",
                      "--no-cache-dir", "--no-compile", "--require-hashes", "--only-binary=:all:",
                      "--platform", "manylinux_2_28_x86_64", "--platform", "manylinux2014_x86_64",
                      "--implementation", "cp", "--python-version", "3.12", "--abi", "cp312",
                      "--timeout", "30", "--retries", "2",
                      "--index-url", "https://pypi.org/simple", "--target", "/package",
                      "-r", "/requirements.lock.txt"]


def check_docker(args):
    if not shutil.which("docker"):
        raise RuntimeError("Docker CLI is missing; no package was built")
    result = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}} {{.Os}} {{.Architecture}}", args.image_id],
                            capture_output=True, text=True, timeout=20, check=False, shell=False)
    if result.returncode or result.stdout.strip() != f"{args.image_id} linux amd64":
        raise RuntimeError("The reviewed image must already exist locally and be Linux amd64; no pull is performed")


def reject_source_links(source):
    if source.is_symlink() or any(path.is_symlink() for path in source.rglob("*")):
        raise ValueError("Package sources must not contain symlinks")


def check_native_files(stage):
    """Reject host/native architecture accidents before publishing the archive."""
    for path in stage.rglob("*"):
        if path.is_symlink():
            raise ValueError("The staged package must not contain symlinks")
        if not path.is_file():
            continue
        match = re.search(r"\.cpython-(\d+)[-.]", path.name)
        if match and match[1] != "312":
            raise ValueError("The package contains a native extension for another Python version")
        with path.open("rb") as stream:
            header = stream.read(20)
        if header[:4] == b"\x7fELF":
            if len(header) < 20 or header[4:6] != b"\x02\x01" or int.from_bytes(header[18:20], "little") != 62:
                raise ValueError("The package contains a non-amd64 ELF binary")
        elif (path.suffix.lower() in {".so", ".dll", ".dylib", ".pyd"}
              or header[:4] in {b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe"}
              or header[:2] == b"MZ"):
            raise ValueError("The package contains a non-Linux native binary")


def prepare_package(args, output, document):
    output.parent.mkdir(parents=True, exist_ok=True)
    # TemporaryDirectory owns only its newly-created child; existing build trees
    # are never recursively removed or reused.
    with tempfile.TemporaryDirectory(prefix="ecoguard-lambda-", dir=output.parent) as folder:
        stage = safe_mount_path(Path(folder) / "package")
        stage.mkdir()
        subprocess.run(docker_command(args, stage), check=True, shell=False, cwd=ROOT)
        for source in (ROOT / "packages/domain/ecoguard_domain", ROOT / "services/aws/ecoguard_aws"):
            reject_source_links(source)
            shutil.copytree(source, stage / source.name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
        (stage / "config").mkdir()
        (stage / "config/google-wif.json").write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        check_native_files(stage)
        subprocess.run(docker_command(args, stage, smoke=True), check=True, shell=False, cwd=ROOT)
        artifact = Path(folder) / "aws-lambda.zip"
        subprocess.run([sys.executable, "-B", str(ROOT / "scripts/package_lambda.py"), str(stage), str(artifact)],
                       check=True, shell=False, cwd=ROOT)
        if artifact.stat().st_size > 50 * 1024 * 1024:
            raise ValueError("ZIP exceeds the personal direct-upload gate's 50 MiB limit")
        # Exclusive creation preserves a concurrently-created output too.
        created = False
        try:
            with output.open("xb") as destination:
                created = True
                with artifact.open("rb") as source:
                    shutil.copyfileobj(source, destination)
        except BaseException:
            if created:
                output.unlink()
            raise
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main(argv=None):
    args = parse_args(argv)
    try:
        safe_mount_path(ROOT)
        lock = ROOT / "services/aws/requirements.lock.txt"
        if not lock.is_file() or lock.is_symlink():
            raise ValueError("The committed business dependency lock must be a regular file")
        if args.output.is_symlink():
            raise ValueError("--output cannot be an existing symlink")
        output = safe_mount_path(args.output)
        if output.suffix != ".zip" or output.exists():
            raise ValueError("--output must name a new .zip file; existing paths are never replaced")
        for source in (ROOT / "packages/domain/ecoguard_domain", ROOT / "services/aws/ecoguard_aws"):
            if not source.is_dir() or output.is_relative_to(source):
                raise ValueError("Package sources are missing or the output is inside a source directory")
            reject_source_links(source)
        with args.wif_config.open("rb") as stream:
            document = WIF.parse_personal_wif(stream.read(WIF.MAX_DOCUMENT_BYTES + 1))
        if not args.build:
            print("Dry run only; no Docker, downloads or files were created.")
            print("Reviewed identity configuration only; cloud trust/connectivity are unverified.")
            print(json.dumps({"imageId": args.image_id, "output": str(output), "project": WIF.PROJECT,
                              "operations": ["fresh temporary stage", "hash-locked CPython 3.12 manylinux amd64 wheels",
                                             "copy app/domain/calibration and explicit reviewed WIF",
                                             "offline isolated package smoke check", "deterministic ZIP; no overwrite"]}, indent=2))
            return 0
        check_docker(args)
        digest = prepare_package(args, output, document)
        print(f"Created {output}: SHA-256 {digest}")
        print("Local package checks passed; cloud trust/connectivity and deployment remain unverified.")
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # Never echo supplied JSON, Docker stderr, environment values or private inputs.
        print("Lambda ZIP preparation failed: check the reviewed inputs, local image and preceding build output.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
