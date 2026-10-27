"""Manually reviewed third publication attempt, using a userland registry client.

Default prints scope only: no imports of task helpers, network, extraction or
cloud calls. --publish reuses the hash-pinned publisher's approved fixed scope,
actual approval/funding record, archive/state/source and private-IAM guards.
It preserves attempts 1 and 2, validates a fresh OCI layout, downloads official
crane v0.22.1 with fixed release checksums, and issues ONE push command. Normal
TLS and the existing private gcloud Docker credential helper remain in use.
No Docker daemon call/change, auth/key export, IAM/API change, container run,
image build, new tag, Cloud Run action, or push-command retry is provided.
The upstream client has its ordinary bounded HTTP request retry behavior.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tarfile

sys.dont_write_bytecode = True
BASE = Path.home() / "ecoguard-c-personal-20261023"
FROZEN = BASE / "frozen-publish-inference-20261024-1.py"
FROZEN_SHA = "f180a9ac01473e468bca17c6a4a1a8f5154422bfafb6b986f9a469b48444b462"
PRIORS = [BASE / f"image-publication-20261024-{n}" for n in (1, 2)]
RESULT = BASE / "image-publication-20261024-3"
TARGET = "us-central1-docker.pkg.dev/ecoguard-fit3184-a2-2026/ecoguard/inference:c-20261024-1"
VERSION = "v0.22.1"
ASSET = "go-containerregistry_Linux_x86_64.tar.gz"
ASSET_SHA = "0ab7a1d6932a213aed964ce97666c3077fe691c8606413674a8b3e0b9ec4cda0"
CHECKSUMS_SHA = "889e6996ef939c12d613f4cae657cc2ecce822e69ea74a58a453a95d723a857d"
RELEASE = "https://github.com/google/go-containerregistry/releases/download/" + VERSION


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def now():
    return datetime.now(timezone.utc).isoformat()


def frozen_module():
    require(FROZEN.is_file() and not FROZEN.is_symlink()
            and hashlib.sha256(FROZEN.read_bytes()).hexdigest() == FROZEN_SHA, "Frozen publisher missing or changed")
    spec = importlib.util.spec_from_file_location("frozen_private_publisher", FROZEN)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    require(m.TARGET == TARGET and m.RESULT == PRIORS[0], "Frozen publication scope differs")
    return m


def prior_failures(m):
    hashes = {}
    names = [
        ("summary.json", "attempt-started.json", "push-started.json", "push-private.log",
         "loaded-image-private.json", "private-iam-before.json", "approval-copy.json", "docker-client/config.json"),
        ("summary.json", "attempt-started.json", "push-started.json", "push-private.log",
         "loaded-image-private.json", "preflight-private.json"),
    ]
    blob = f'https://{m.HOST}/v2/{m.PROJECT}/ecoguard/inference/blobs/{m.CONFIG_DIGEST}'
    for number, (directory, required_files) in enumerate(zip(PRIORS, names), 1):
        require(directory.is_dir() and not directory.is_symlink(), "Reviewed prior attempt missing")
        summary = m.local_json(directory / "summary.json")
        expected = {"status": "blocked", "target": TARGET, "archiveSHA256": m.ARCHIVE_SHA,
            "pushAttempted": True, "pushReturnedSuccess": False, "registryDigest": None,
            "runtimeActivated": False, "iamModified": False, "errorType": "RuntimeError",
            "error": "Docker operation failed; see private push-private.log"}
        require(all(type(summary.get(k)) is type(v) and summary[k] == v for k, v in expected.items()),
                "Prior attempt is not the reviewed failed push")
        require(m.local_json(directory / "push-started.json").get("target") == TARGET, "Prior marker target differs")
        log = directory / "push-private.log"
        require(log.is_file() and not log.is_symlink() and log.stat().st_size < 65536, "Prior bounded push log missing")
        require(any(f'Head "{blob}"' in line and "dial tcp" in line and "connect: connection refused" in line
                    for line in log.read_text().splitlines()), "Prior log is not the exact reviewed pre-TLS blob refusal")
        for name in required_files:
            path = directory / name
            require(path.is_file() and not path.is_symlink() and path.stat().st_size < 4 * 1024**2,
                    "Prior evidence missing or outside bounded size")
            hashes[f"{number}/{name}"] = m.sha_file(path)
    return hashes


def extract_layout(archive, layout, m, config, layers):
    """Local-only bounded extraction; paths are arguments to permit offline review."""
    require(not layout.exists() and not layout.is_symlink(), "OCI output exists")
    require(archive.is_file() and not archive.is_symlink() and archive.stat().st_size == 373265304
            and m.sha_file(archive) == m.ARCHIVE_SHA, "Fixed archive changed before extraction")
    required = {"index.json", "oci-layout", "blobs/sha256/" + m.OCI_DIGEST[7:],
                "blobs/sha256/" + m.CONFIG_DIGEST[7:], *["blobs/sha256/" + d["digest"][7:] for d in layers]}
    require(len(required) == 14 and len(layers) == 10, "Expected exactly twelve blobs")
    expected_sizes = {"blobs/sha256/" + d["digest"][7:]: d["size"] for d in layers}
    layout.mkdir(mode=0o700)
    seen, total = set(), 0
    with tarfile.open(archive, "r|gz") as package:
        for entry in package:
            path = PurePosixPath(entry.name)
            require(not path.is_absolute() and ".." not in path.parts and "\\" not in entry.name,
                    "Unsafe archive path")
            name = str(path)
            if entry.isdir():
                require(name in (".", "blobs", "blobs/sha256"), "Unexpected archive directory")
                continue
            require(entry.isfile() and name not in seen and name in required | {"manifest.json"},
                    "Archive link/duplicate/unexpected file")
            seen.add(name)
            require(0 < entry.size <= 512 * 1024**2, "Archive entry outside size bounds")
            if name == "manifest.json":
                require(entry.size < 1024**2, "Classic metadata too large")
                continue  # Never copy the classic Docker archive manifest.
            if name in expected_sizes:
                require(entry.size == expected_sizes[name], "Compressed layer size mismatch")
            else:
                require(entry.size < 1024**2, "OCI metadata too large")
            total += entry.size
            require(total < 512 * 1024**2, "OCI extraction total limit exceeded")
            output = layout / name
            output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            sha, count = hashlib.sha256(), 0
            with output.open("xb") as destination:
                source = package.extractfile(entry)
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    count += len(block)
                    require(count <= entry.size, "Archive stream exceeded declared size")
                    sha.update(block)
                    destination.write(block)
            require(count == entry.size, "Truncated archive entry")
            if name.startswith("blobs/"):
                require(sha.hexdigest() == path.name, "OCI blob hash mismatch")
    require(seen == required | {"manifest.json"}, "OCI/archive file set differs")
    index = json.loads((layout / "index.json").read_bytes())
    require(json.loads((layout / "oci-layout").read_bytes()) == {"imageLayoutVersion": "1.0.0"}, "OCI layout version differs")
    require(index.get("schemaVersion") == 2 and len(index.get("manifests", [])) == 1, "OCI index must contain one image")
    descriptor = index["manifests"][0]
    manifest_bytes = (layout / "blobs/sha256" / m.OCI_DIGEST[7:]).read_bytes()
    config_bytes = (layout / "blobs/sha256" / m.CONFIG_DIGEST[7:]).read_bytes()
    manifest, document = json.loads(manifest_bytes), json.loads(config_bytes)
    require(descriptor.get("digest") == m.OCI_DIGEST and descriptor.get("size") == len(manifest_bytes)
            and descriptor.get("mediaType") == manifest.get("mediaType") == "application/vnd.oci.image.manifest.v1+json",
            "OCI image descriptor differs")
    require(manifest.get("schemaVersion") == 2 and manifest.get("config", {}).get("digest") == m.CONFIG_DIGEST
            and manifest["config"].get("size") == len(config_bytes) and manifest.get("layers") == layers,
            "OCI manifest/config/layer chain differs")
    require(document.get("os") == "linux" and document.get("architecture") == "amd64"
            and document.get("rootfs", {}).get("diff_ids") == m.DIFF_IDS and document.get("config") == config,
            "OCI config/platform/rootfs differs")
    return {"files": len(required), "blobs": 12, "extractedBytes": total,
            "manifestDigest": m.OCI_DIGEST, "configDigest": m.CONFIG_DIGEST}


def fetch_crane(m, env):
    def fetch(filename):
        result = subprocess.run(["curl", "--disable", "--fail", "--silent", "--show-error", "--location",
            "--proto", "=https", "--proto-redir", "=https", "--max-time", "120", "--output", str(RESULT / filename),
            RELEASE + "/" + filename], env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=150, shell=False)
        require(result.returncode == 0, "Official release download failed; no retry")
    fetch("checksums.txt")
    require(m.sha_file(RESULT / "checksums.txt") == CHECKSUMS_SHA, "Official checksums file digest mismatch")
    entries = [line.split() for line in (RESULT / "checksums.txt").read_text().splitlines()]
    require([line for line in entries if len(line) == 2 and line[1].lstrip("*") == ASSET]
            == [[ASSET_SHA, ASSET]], "Official asset checksum line differs")
    fetch(ASSET)
    require(m.sha_file(RESULT / ASSET) == ASSET_SHA, "Official crane archive digest mismatch")
    with tarfile.open(RESULT / ASSET, "r:gz") as package:
        entries = [entry for entry in package.getmembers() if entry.name == "crane"]
        require(len(entries) == 1 and entries[0].isfile() and 0 < entries[0].size < 64 * 1024**2,
                "Official crane binary entry differs")
        binary = package.extractfile(entries[0]).read()
    require(binary.startswith(b"\x7fELF"), "Expected Linux ELF crane executable")
    crane = RESULT / "crane"
    with crane.open("xb") as output:
        output.write(binary)
    crane.chmod(0o700)
    result = subprocess.run([str(crane), "version"], env=env, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=20, shell=False)
    require(result.returncode == 0 and result.stdout.strip().lstrip("v") == VERSION[1:], "Crane version differs")
    return crane, hashlib.sha256(binary).hexdigest()


def remote_bytes(crane, operation, reference, env, filename):
    result = subprocess.run([str(crane), operation, reference], env=env, stdin=subprocess.DEVNULL,
                            capture_output=True, timeout=120, shell=False)
    (RESULT / (filename + ".stderr.log")).write_bytes(result.stderr)
    require(result.returncode == 0 and len(result.stdout) < 1024**2, "Remote metadata read failed or exceeded bound; no push retry")
    (RESULT / filename).write_bytes(result.stdout)
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true", help="One reviewed userland push of the already-approved exact artifact")
    args = parser.parse_args()
    if not args.publish:
        print(json.dumps({"status": "dry-run", "cloudInvoked": False, "dockerInvoked": False, "target": TARGET,
            "priorFailedPushAttempts": 2, "result": str(RESULT), "toolVersion": VERSION, "toolAssetSHA256": ASSET_SHA,
            "sameExistingPublicationApprovalRequired": True, "automaticPushCommandRetry": False}))
        return 0
    require(sys.platform == "linux" and platform.machine() == "x86_64" and os.environ.get("CLOUD_SHELL") == "true", "Existing Linux x86_64 CloudShell required")
    require(not RESULT.exists() and not RESULT.is_symlink(), "Third attempt exists; no retry")
    for command in ("git", "gcloud", "docker-credential-gcloud", "curl"):
        require(shutil.which(command), "Required executable absent: " + command)
    for key in ("DOCKER_AUTH_CONFIG", "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_OAUTH_ACCESS_TOKEN", "GOOGLE_CREDENTIALS",
                "GOOGLE_IMPERSONATE_SERVICE_ACCOUNT", "GOOGLE_IMPERSONATE_SERVICE_ACCOUNT_DELEGATES", "GOOGLE_CLOUD_KEYFILE_JSON",
                "GCLOUD_KEYFILE_JSON", "CLOUDSDK_AUTH_ACCESS_TOKEN", "CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT",
                "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE", "REGISTRY_AUTH_FILE", "SSL_CERT_FILE", "SSL_CERT_DIR", "CURL_CA_BUNDLE",
                "HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "https_proxy", "http_proxy", "all_proxy"):
        require(not os.environ.get(key), "Unreviewed credential/TLS/proxy override: " + key)
    m = frozen_module()
    hashes = prior_failures(m)
    client = PRIORS[0] / "docker-client"
    require(client.is_dir() and not client.is_symlink() and m.local_json(client / "config.json")
            == {"credHelpers": {m.HOST: "gcloud"}}, "Existing private credential-helper configuration differs")
    env = {**m.ENV, "DOCKER_CONFIG": str(client), "NO_COLOR": "1"}
    approval = m.budget_record()
    m.clean_source()
    config, layers = m.uploaded_archive()
    state_sha = m.approved_registry_state()
    policies = m.live_preflight(approval)
    require(policies == m.local_json(PRIORS[0] / "private-iam-before.json"), "Private IAM changed since original attempt")
    require(shutil.disk_usage(m.HOME_DIR).free >= 768 * 1024**2, "Less than 768 MiB home working space")
    RESULT.mkdir(mode=0o700)
    m.RESULT = RESULT
    summary = {"status": "blocked", "target": TARGET, "archiveSHA256": m.ARCHIVE_SHA,
        "priorFailedPushAttempts": 2, "globalPushAttempt": 3, "client": "crane", "toolVersion": VERSION,
        "toolAssetSHA256": ASSET_SHA, "dockerInvoked": False, "automaticPushCommandRetry": False,
        "pushAttempted": False, "pushReturnedSuccess": False, "registryDigest": None,
        "runtimeActivated": False, "iamModified": False, "apisModified": False}
    try:
        m.save("attempt-started.json", {**summary, "startedAtUtc": now()})
        m.save("preflight-private.json", {"approval": approval, "iamBefore": policies, "stateSHA256": state_sha,
            "sourceRevision": m.SOURCE_REVISION, "priorEvidenceSHA256": hashes, "frozenHelperSHA256": FROZEN_SHA})
        (RESULT / "state-before-private-backup.json").write_bytes(m.STATE.read_bytes())
        layout = RESULT / "oci-layout"
        m.save("oci-layout-verification.json", extract_layout(m.ARCHIVE, layout, m, config, layers))
        crane, binary_sha = fetch_crane(m, env)
        summary["toolBinarySHA256"] = binary_sha
        m.budget_record(); m.clean_source()
        require(m.sha_file(m.STATE) == state_sha and m.private_policies() == policies, "State/IAM changed before userland push")
        require(m.cloud("artifacts", "docker", "images", "list", m.REGISTRY, "--include-tags", "--project=" + m.PROJECT) == [], "Repository no longer empty; refuse overwrite")
        require(prior_failures(m) == hashes, "Prior attempt evidence changed")
        m.save("push-started.json", {"target": TARGET, "globalPushAttempt": 3, "startedAtUtc": now(), "client": "crane"})
        summary["pushAttempted"] = True
        with (RESULT / "push-private.log").open("xb") as log:
            result = subprocess.run([str(crane), "push", str(layout), TARGET, "--image-refs", str(RESULT / "published-reference.txt")],
                env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, timeout=1200, shell=False)
        require(result.returncode == 0, "Userland push failed; inspect private log; no retry")
        summary["pushReturnedSuccess"] = True
        expected = m.IMAGE + "@" + m.OCI_DIGEST
        require((RESULT / "published-reference.txt").read_text().strip() == expected, "Published reference is not the exact OCI digest")
        described = m.cloud("artifacts", "docker", "images", "describe", TARGET, "--project=" + m.PROJECT)
        m.save("registry-image-private.json", described)
        require(described.get("image_summary", {}).get("digest") == m.OCI_DIGEST
                and described["image_summary"].get("fully_qualified_digest") == expected, "Actual registry digest differs; no repush")
        raw_manifest = remote_bytes(crane, "manifest", expected, env, "registry-manifest-private.json")
        raw_config = remote_bytes(crane, "config", expected, env, "registry-config-private.json")
        require("sha256:" + hashlib.sha256(raw_manifest).hexdigest() == m.OCI_DIGEST
                and "sha256:" + hashlib.sha256(raw_config).hexdigest() == m.CONFIG_DIGEST,
                "Remote raw manifest/config digests differ")
        require(raw_manifest == (layout / "blobs/sha256" / m.OCI_DIGEST[7:]).read_bytes()
                and raw_config == (layout / "blobs/sha256" / m.CONFIG_DIGEST[7:]).read_bytes(), "Remote bytes differ from the audited archive")
        m.clean_source()
        require(m.sha_file(m.STATE) == state_sha and m.sha_file(m.SAVED_PLAN) == m.SAVED_PLAN_SHA
                and m.private_policies() == policies and prior_failures(m) == hashes, "Source/state/plan/IAM/prior evidence changed")
        summary.update(status="private-inference-image-published-and-verified", registryDigest=m.OCI_DIGEST,
            configDigest=m.CONFIG_DIGEST, imageUri=expected, remoteManifestAndConfigBytesMatch=True,
            remoteCompressedLayersMatchArchive=True, cloudInferenceVerified=False)
    except Exception as error:
        summary["errorType"] = type(error).__name__
        summary["error"] = str(error) if isinstance(error, RuntimeError) else "Inspect private logs/metadata; no further push retry"
        if isinstance(error, subprocess.TimeoutExpired):
            summary["processOutcomeUncertain"] = True
    finally:
        try:
            (RESULT / "state-after-private-backup.json").write_bytes(m.STATE.read_bytes())
            summary["stateFileUnchanged"] = m.sha_file(m.STATE) == state_sha
            if not summary["stateFileUnchanged"]:
                summary["status"] = "blocked"
        except Exception as error:
            summary["status"] = "blocked"
            summary["stateCaptureErrorType"] = type(error).__name__
        summary["observedAtUtc"] = now()
        m.save("summary.json", summary)
        print(json.dumps(summary, separators=(",", ":")), flush=True)
    return 0 if summary["status"] == "private-inference-image-published-and-verified" else 1


if __name__ == "__main__":
    os.umask(0o077)
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"status": "blocked", "errorType": type(error).__name__, "dockerInvoked": False,
            "error": str(error) if isinstance(error, RuntimeError) else "Invalid/incomplete local or preflight input"}))
        raise SystemExit(1)
