"""One manually reviewed recovery of the same private image push.

Default only prints scope. --recover rechecks the frozen publisher, failed first
attempt, a fresh unauthenticated daemon probe, funding, image and private cloud
state. It never reloads, retags, changes IAM, runs containers or loops/retries.
The original attempt is retained; this is explicitly the second push attempt.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys

sys.dont_write_bytecode = True
BASE = Path.home() / "ecoguard-c-personal-20261023"
FROZEN = BASE / "frozen-publish-inference-20261024-1.py"
FROZEN_SHA = "f180a9ac01473e468bca17c6a4a1a8f5154422bfafb6b986f9a469b48444b462"
PRIOR = BASE / "image-publication-20261024-1"
RESULT = BASE / "image-publication-20261024-2"
PROBE = BASE / "registry-daemon-network-probe-20261024-1.json"
SOCKET = "unix:///var/run/docker.sock"
TARGET = "us-central1-docker.pkg.dev/ecoguard-fit3184-a2-2026/ecoguard/inference:c-20261024-1"


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def frozen_module():
    require(FROZEN.is_file() and not FROZEN.is_symlink()
            and hashlib.sha256(FROZEN.read_bytes()).hexdigest() == FROZEN_SHA,
            "Frozen publication helper missing or changed")
    spec = importlib.util.spec_from_file_location("frozen_private_publisher", FROZEN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(module.TARGET == TARGET and module.RESULT == PRIOR, "Frozen publication scope differs")
    return module


def reviewed_failure_and_probe(m):
    require(PRIOR.is_dir() and not PRIOR.is_symlink(), "Original attempt missing or symlinked")
    prior = m.local_json(PRIOR / "summary.json")
    expected = {"status": "blocked", "target": m.TARGET, "archiveSHA256": m.ARCHIVE_SHA,
        "loadAttempted": True, "pushAttempted": True, "pushReturnedSuccess": False,
        "registryDigest": None, "runtimeActivated": False, "iamModified": False,
        "retryAttempted": False, "errorType": "RuntimeError",
        "error": "Docker operation failed; see private push-private.log"}
    require(all(type(prior.get(k)) is type(v) and prior[k] == v for k, v in expected.items()),
            "Original attempt is not the reviewed single network failure")
    marker = m.local_json(PRIOR / "push-started.json")
    require(marker.get("target") == m.TARGET, "Original push marker scope differs")
    log = PRIOR / "push-private.log"
    require(log.is_file() and not log.is_symlink() and log.stat().st_size < 65536,
            "Original bounded push log missing")
    blob = f'https://{m.HOST}/v2/{m.PROJECT}/ecoguard/inference/blobs/{m.CONFIG_DIGEST}'
    require(any(f'Head "{blob}"' in line and "dial tcp" in line
                and "connect: connection refused" in line for line in log.read_text().splitlines()),
            "Original log is not the exact reviewed pre-TLS config-blob refusal")
    probe = m.local_json(PROBE)
    exact = {"kind": "read-only-docker-daemon-registry-distribution-probe", "status": 403,
             "authenticationSupplied": False, "imageOrRegistryMutated": False}
    require(all(type(probe.get(k)) is type(v) and probe[k] == v for k, v in exact.items()),
            "Read-only daemon recovery probe differs")
    message = (f'Head "https://{m.HOST}/v2/{m.PROJECT}/ecoguard/inference/manifests/c-20261024-1": '
        'denied: Unauthenticated request. Unauthenticated requests do not have permission '
        f'"artifactregistry.repositories.downloadArtifacts" on resource "{m.REPOSITORY}" (or it may not exist)')
    require(probe.get("message") == message, "Probe is not the exact unauthenticated registry response")
    stamp = datetime.fromisoformat(probe["observedAtUtc"].replace("Z", "+00:00"))
    require(stamp.tzinfo is not None and 0 <= (datetime.now(timezone.utc) - stamp).total_seconds() <= 600,
            "Successful read-only daemon probe is older than ten minutes")
    failed_at = datetime.fromisoformat(prior["observedAtUtc"].replace("Z", "+00:00"))
    require(failed_at.tzinfo is not None and failed_at < stamp, "Recovery probe predates the failed push")
    names = ("summary.json", "push-started.json", "push-private.log", "loaded-image-private.json",
             "private-iam-before.json", "approval-copy.json", "attempt-started.json")
    require(all((PRIOR / name).is_file() and not (PRIOR / name).is_symlink() for name in names),
            "Original evidence missing or symlinked")
    return probe, {name: m.sha_file(PRIOR / name) for name in names}


def inspected_image(m, tag, config):
    loaded = json.loads(m.read(["docker", "image", "inspect", tag], docker=True, timeout=30))
    require(isinstance(loaded, list) and len(loaded) == 1, "Loaded tag schema differs")
    image = loaded[0]
    require(image.get("Id") in (m.CONFIG_DIGEST, m.OCI_DIGEST) and image.get("Os") == "linux"
        and image.get("Architecture") == "amd64" and image.get("RootFS", {}).get("Layers") == m.DIFF_IDS
        and all(image.get("Config", {}).get(k) == config.get(k)
                for k in ("User", "WorkingDir", "Cmd", "Entrypoint", "Env")), "Loaded tag identity differs")
    if image["Id"] == m.OCI_DIGEST:
        require(image.get("Descriptor", {}).get("annotations", {}).get("config.digest") == m.CONFIG_DIGEST,
                "OCI loaded tag config linkage differs")
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recover", action="store_true", help="One manually reviewed second push; no automatic retries")
    args = parser.parse_args()
    if not args.recover:
        print(json.dumps({"status": "dry-run", "cloudInvoked": False, "dockerInvoked": False,
            "target": TARGET, "frozenHelperSHA256": FROZEN_SHA, "result": str(RESULT),
            "priorFailedPushAttempts": 1, "manuallyReviewedRecoveryRequired": True, "automaticRetry": False,
            "scope": "same already-loaded image, same private target, one second push; no load/tag/run/IAM/runtime"}))
        return 0
    require(sys.platform == "linux" and os.environ.get("CLOUD_SHELL") == "true", "Existing CloudShell required")
    require(not RESULT.exists() and not RESULT.is_symlink(), "Recovery attempt exists; no further retry")
    for command in ("git", "gcloud", "docker", "docker-credential-gcloud"):
        require(shutil.which(command), "Required executable missing: " + command)
    for key in ("DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH", "DOCKER_AUTH_CONFIG",
                "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_OAUTH_ACCESS_TOKEN", "GOOGLE_CREDENTIALS",
                "GOOGLE_IMPERSONATE_SERVICE_ACCOUNT", "GOOGLE_IMPERSONATE_SERVICE_ACCOUNT_DELEGATES",
                "GOOGLE_CLOUD_KEYFILE_JSON", "GCLOUD_KEYFILE_JSON", "CLOUDSDK_AUTH_ACCESS_TOKEN",
                "CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT", "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE"):
        require(not os.environ.get(key), "Unreviewed credential/daemon override: " + key)
    require(os.environ.get("DOCKER_HOST", "") in ("", SOCKET), "Unexpected CloudShell Docker endpoint")
    m = frozen_module()
    m.ENV = {k: v for k, v in m.ENV.items() if k != "DOCKER_HOST"}  # Child environment only.
    client = PRIOR / "docker-client"
    require(client.is_dir() and not client.is_symlink() and m.local_json(client / "config.json")
            == {"credHelpers": {m.HOST: "gcloud"}}, "Original private credential-helper configuration differs")
    m.DOCKER_ENV = {**m.ENV, "DOCKER_CONFIG": str(client), "DOCKER_CLI_HINTS": "false"}
    endpoint = json.loads(m.read(["docker", "context", "inspect", "default", "--format={{json .Endpoints.docker}}"], docker=True))
    require(endpoint.get("Host") == SOCKET and endpoint.get("SkipTLSVerify") is False,
            "Default Docker endpoint is not the exact local socket")
    probe, prior_hashes = reviewed_failure_and_probe(m)
    approval = m.budget_record()
    m.clean_source()
    config, layers = m.uploaded_archive()
    state_sha = m.approved_registry_state()
    policies = m.live_preflight(approval)
    require(policies == m.local_json(PRIOR / "private-iam-before.json"), "IAM changed since original attempt")
    info = json.loads(m.read(["docker", "info", "--format={{json .}}"], docker=True, timeout=30))
    require(info.get("OSType") == "linux" and info.get("Architecture") == "x86_64"
            and isinstance(info.get("DockerRootDir"), str), "Docker daemon platform/schema differs")
    require(shutil.disk_usage(info["DockerRootDir"]).free >= 3 * 1024**3
            and shutil.disk_usage(m.HOME_DIR).free >= 256 * 1024**2, "Insufficient reviewed working storage")
    local, target = inspected_image(m, m.LOCAL_TAG, config), inspected_image(m, m.TARGET, config)
    require(local["Id"] == target["Id"], "Existing local and destination tags differ")
    os.umask(0o077)
    RESULT.mkdir(mode=0o700)
    m.RESULT = RESULT
    summary = {"status": "blocked", "target": m.TARGET, "archiveSHA256": m.ARCHIVE_SHA,
        "priorFailedPushAttempts": 1, "manuallyReviewedRecovery": True, "automaticRetry": False,
        "retryAttempted": True, "loadAttempted": False, "tagAttempted": False,
        "pushAttempted": False, "pushReturnedSuccess": False, "registryDigest": None,
        "runtimeActivated": False, "iamModified": False}
    try:
        m.save("attempt-started.json", {**summary, "startedAtUtc": datetime.now(timezone.utc).isoformat(), "retryPermitted": False})
        m.save("preflight-private.json", {"sourceRevision": m.SOURCE_REVISION, "stateSHA256": state_sha,
            "archiveSHA256": m.ARCHIVE_SHA, "approval": approval, "iamBefore": policies,
            "priorEvidenceSHA256": prior_hashes, "networkProbe": probe, "dockerEndpoint": SOCKET,
            "docker": {k: info.get(k) for k in ("ID", "ServerVersion", "OSType", "Architecture", "DockerRootDir")}})
        m.save("loaded-image-private.json", target)
        m.budget_record(); m.clean_source()
        require(m.sha_file(m.STATE) == state_sha and m.private_policies() == policies, "State/IAM changed before recovery push")
        require(m.cloud("artifacts", "docker", "images", "list", m.REGISTRY, "--include-tags", "--project=" + m.PROJECT) == [],
                "Image/version appeared; refuse overwrite")
        reviewed_failure_and_probe(m)
        m.save("push-started.json", {"target": m.TARGET, "startedAtUtc": datetime.now(timezone.utc).isoformat(),
            "globalPushAttempt": 2, "automaticRetry": False})
        summary["pushAttempted"] = True
        m.docker_log(["image", "push", m.TARGET], "push-private.log", 1200)
        summary["pushReturnedSuccess"] = True
        described = m.cloud("artifacts", "docker", "images", "describe", m.TARGET, "--project=" + m.PROJECT)
        m.save("registry-image-private.json", described)
        image_summary = described.get("image_summary", {})
        digest = image_summary.get("digest")
        require(isinstance(digest, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
                and image_summary.get("fully_qualified_digest") == m.IMAGE + "@" + digest,
                "Unrecognized registry image schema; inspect privately without another push")
        summary["registryDigest"] = digest
        remote = json.loads(m.read(["docker", "manifest", "inspect", m.IMAGE + "@" + digest], docker=True))
        m.save("registry-manifest-private.json", remote)
        require(remote.get("schemaVersion") == 2 and remote.get("config", {}).get("digest") == m.CONFIG_DIGEST
                and isinstance(remote.get("layers"), list) and len(remote["layers"]) == 10,
                "Remote manifest/config/layer identity differs")
        summary["remoteCompressedLayersMatchArchive"] = m.same_layers(remote["layers"], layers)
        m.clean_source()
        require(m.sha_file(m.STATE) == state_sha and m.sha_file(m.SAVED_PLAN) == m.SAVED_PLAN_SHA
                and m.private_policies() == policies, "Source/state/plan/IAM changed during recovery")
        require(all(m.sha_file(PRIOR / name) == digest for name, digest in prior_hashes.items()),
                "Original attempt evidence changed")
        summary.update(status="private-inference-image-published-and-verified", configDigest=m.CONFIG_DIGEST,
            imageUri=m.IMAGE + "@" + digest, cloudInferenceVerified=False)
    except Exception as error:
        summary["errorType"] = type(error).__name__
        summary["error"] = str(error) if isinstance(error, RuntimeError) else "Inspect private logs/metadata; no further retry"
    finally:
        summary["observedAtUtc"] = datetime.now(timezone.utc).isoformat()
        m.save("summary.json", summary)
        print(json.dumps(summary, separators=(",", ":")), flush=True)
    return 0 if summary["status"] == "private-inference-image-published-and-verified" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"status": "blocked", "errorType": type(error).__name__,
            "error": str(error) if isinstance(error, RuntimeError) else "Invalid/incomplete recovery preflight input"}), flush=True)
        raise SystemExit(1)
