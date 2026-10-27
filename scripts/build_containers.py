"""Print, or explicitly build, the repository's linux/amd64 service images.

Uses only the Python standard library. No registry login, push, container start,
or deployment is performed. Printing the command does not require Docker.
"""

import argparse
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
RIC_LOCK = ROOT / "services/aws/requirements-ric.lock.txt"
DOCKERFILES = {
    "inference": ROOT / "services/inference/Dockerfile",
    "aws-ingest": ROOT / "services/aws/Dockerfile",
}
# PowerShell recognizes these smart quotes as single-quote delimiters too.
POWERSHELL_LITERAL_ESCAPES = str.maketrans({quote: quote * 2 for quote in "'\u2018\u2019\u201a\u201b"})


def image_tag(value):
    repository, separator, tag = value.rpartition(":")
    if (not separator or not repository or "/" in tag
            or not re.fullmatch(r"[a-z0-9][a-z0-9._:/-]*", repository)
            or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", tag)
            or tag.lower() == "latest"):
        raise argparse.ArgumentTypeError(
            "--image requires an explicit non-latest tag, e.g. ecoguard-inference:20261023-1"
        )
    return value


def ric_version(value):
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value):
        raise argparse.ArgumentTypeError(
            "--aws-lambda-ric-version requires an exact stable X.Y.Z version; no latest, ranges or wildcards"
        )
    try:
        pinned = re.findall(r"^awslambdaric==([0-9]+\.[0-9]+\.[0-9]+)(?:\s|$)",
                            RIC_LOCK.read_text(encoding="utf-8"), re.MULTILINE)
    except OSError as error:
        raise argparse.ArgumentTypeError("cannot read services/aws/requirements-ric.lock.txt") from error
    if len(pinned) != 1:
        raise argparse.ArgumentTypeError("requirements-ric.lock.txt must contain exactly one awslambdaric pin")
    if value != pinned[0]:
        raise argparse.ArgumentTypeError(
            f"--aws-lambda-ric-version must match services/aws/requirements-ric.lock.txt ({pinned[0]})"
        )
    return value


def base_image(value):
    if not re.fullmatch(r"python:3\.12-slim(?:-bookworm)?@sha256:[0-9a-fA-F]{64}", value):
        raise argparse.ArgumentTypeError(
            "--base-image requires python:3.12-slim[-bookworm]@sha256:<64 hex characters>; tags alone are not accepted"
        )
    return value.lower()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", choices=DOCKERFILES)
    parser.add_argument("--image", required=True, type=image_tag)
    parser.add_argument("--base-image", type=base_image,
                        help="optional official Python 3.12 slim base pinned by sha256 digest")
    parser.add_argument("--aws-lambda-ric-version", type=ric_version,
                        help="committed awslambdaric lock version (currently 4.2.2); required only for aws-ingest")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="print only (the default); Docker is not contacted")
    mode.add_argument("--build", action="store_true", help="check Docker, then build and load the image; never push")
    args = parser.parse_args(argv)
    if args.service == "aws-ingest" and not args.aws_lambda_ric_version:
        parser.error("aws-ingest requires --aws-lambda-ric-version matching requirements-ric.lock.txt (currently 4.2.2)")
    if args.service != "aws-ingest" and args.aws_lambda_ric_version:
        parser.error("--aws-lambda-ric-version applies only to aws-ingest")
    return args


def build_command(args):
    command = ["docker", "buildx", "build", "--platform", "linux/amd64",
               "--load", "--provenance=false", "--file", str(DOCKERFILES[args.service]),
               "--tag", args.image]
    if args.base_image:
        command += ["--build-arg", f"BASE_IMAGE={args.base_image}"]
    if args.service == "aws-ingest":
        command += ["--build-arg", f"AWS_LAMBDA_RIC_VERSION={args.aws_lambda_ric_version}"]
    return command + [str(ROOT)]


def format_command(command):
    """Render for display/copy only; this string is never executed by main."""
    if os.name == "nt":
        # PowerShell single quotes preserve spaces and metacharacters in paths.
        arguments = ("'" + argument.translate(POWERSHELL_LITERAL_ESCAPES) + "'" for argument in command)
        return "& " + " ".join(arguments)
    return shlex.join(command)


def check_docker():
    if not shutil.which("docker"):
        raise RuntimeError("Docker CLI is missing. Install Docker separately; no image was built.")
    try:
        engine = subprocess.run(["docker", "info", "--format", "{{.OSType}}"],
                                capture_output=True, text=True, timeout=15, check=False)
        if engine.returncode:
            raise RuntimeError("Docker engine is unavailable. Start the intended Linux engine yourself and retry.")
        if engine.stdout.strip() != "linux":
            raise RuntimeError("A Linux Docker engine is required for linux/amd64 images.")
        buildx = subprocess.run(["docker", "buildx", "version"],
                                capture_output=True, text=True, timeout=15, check=False)
        if buildx.returncode:
            raise RuntimeError("Docker Buildx is unavailable. Install/configure it separately before building.")
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("Docker preflight timed out; no build was started.") from error
    except OSError as error:
        raise RuntimeError("Docker could not be executed; no build was started.") from error


def main(argv=None):
    args = parse_args(argv)
    command = build_command(args)
    if not args.build:
        print("Dry run only; Docker was not contacted.")
        print(format_command(command))
        return 0
    try:
        check_docker()
        print(format_command(command), flush=True)
        subprocess.run(command, cwd=ROOT, check=True, shell=False)
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print(f"Build failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
