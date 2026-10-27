"""One approved private image publication in the existing GCP CloudShell.

Default: print the fixed scope and approval schema, optionally verify uploaded
local inputs. No Docker/cloud calls or writes without --publish. This helper
never writes an approval record, exports a token/key, runs a container, enables
APIs, grants IAM, builds images, deploys Cloud Run or retries a push.

The existing approval record must have the exact fields shown by the default
output. The operator records the user's actual approval and a fresh read-only
funding observation; JSON alone does not confer authorization.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
from zoneinfo import ZoneInfo

sys.dont_write_bytecode = True
HOME_DIR = Path.home()
BASE = HOME_DIR / "ecoguard-c-personal-20261023"
SOURCE = BASE / "source"
ROOT = SOURCE / "infra/gcp/environments/personal"
APPLY = ROOT / "private/registry-plan-20261024-1/apply-20261024-1"
SAVED_PLAN = APPLY.parent / "registry.tfplan"
SOURCE_REVISION = "00d58e0e8c65321cc759d575eafaba801c1e8253"
SAVED_PLAN_SHA = "0f62543fe74a7b0fc71e9e8c2b1930de853448d1ab4c257b9d215399c9d5ba86"
STATE = ROOT / "state/terraform.tfstate"
RESULT = BASE / "image-publication-20261024-1"
ARCHIVE = HOME_DIR / "inference-amd64-20261024-1.tar.gz"
METADATA = HOME_DIR / "inference-amd64-20261024-1.json"
APPROVAL = BASE / "image-publication-approval-20261024-1.json"
PROJECT, NUMBER, REGION = "ecoguard-fit3184-a2-2026", "995070689587", "us-central1"
OPERATOR = "hoshigahoshii@163.com"
HOST = REGION + "-docker.pkg.dev"
REPOSITORY = f"projects/{PROJECT}/locations/{REGION}/repositories/ecoguard"
REGISTRY = f"{HOST}/{PROJECT}/ecoguard"
IMAGE = REGISTRY + "/inference"
TARGET = IMAGE + ":c-20261024-1"
LOCAL_TAG = "ecoguard-inference:c-20261023-3"
OCI_DIGEST = "sha256:7e481399309c8a90276c864e9765545657e44c00e9061ee668b4e56db4f22fdb"
CONFIG_DIGEST = "sha256:3633f5354e5af61775e661925c9fc39ef96a243f1b23aa712e6fdd210c858643"
ARCHIVE_SHA = "41ef8c5f4e1c0d0b9b6d3e8d1d814a0e7c5d1889082f1ab77882a122db6d94aa"
DIFF_IDS = ["sha256:" + value for value in (
    "9b35de7893378218e365c34c2c735fb0032a859112fb7345ca8ea73f9aa1db70",
    "535ecd2088497f5955e24fd33c534fc9ba37fb717a33a841315a358dd4ff8b35",
    "536ebec0f9d8119e620ed0e261faa2cfdeab88621f35924fb0ec74f646b5c53b",
    "b8a5c0b25a3657c3b43a3a4cf1815f27fd7ca6c8bc3ffd36164f90731ca83db4",
    "da8c08e28c0a6c61f86f385343a731e0450bc3461c2d216798facbd11921f606",
    "39d1fdfa08be1bb1e4773c6152f3a45aaeffc619347b0f65dd669f378920d4dd",
    "5d57a0c04203e8704c2d9317212e7f75040b267d46afb74c1a40d079bdabc64d",
    "7e517c0ed54044bb9b934b401c07f21f9ce41f7fd11454b24c6fd8ab1bf56d1b",
    "4c1dd7b032cc1f6c749d2b8f107e94d4763e3cd773c7979d254a03143a9a1dae",
    "3c55acc2791c21d3062e77a41d72ea8cfa731e399c0bd998b69d747c018b8e6e")]
EXPECTED_APPROVAL = {
    "approved": True, "approvedScope": "upload-fixed-archive-and-push-one-private-inference-image",
    "project": PROJECT, "projectNumber": NUMBER, "operator": OPERATOR,
    "archiveName": ARCHIVE.name, "archiveBytes": 373265304, "archiveSHA256": ARCHIVE_SHA,
    "imageTag": TARGET, "additionalPersonalSpendLimitAUD": 0,
    "creditExpiryDate": "2026-10-28", "cleanupByDateAustraliaMelbourne": "2026-10-27",
    "remainingCreditVerifiedPositive": True,
}
ENV = {**os.environ, "CLOUDSDK_CORE_DISABLE_PROMPTS": "1"}
DOCKER_ENV = None


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def sha_file(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def local_json(path):
    require(path.is_file() and not path.is_symlink(), "Missing or symlinked local input: " + path.name)
    require(path.stat().st_size < 4 * 1024**2, "Local JSON exceeds bounded input size")
    return json.loads(path.read_text())


def save(name, value):
    path = RESULT / name
    with path.open("x") as output:
        json.dump(value, output, indent=2)
        output.write("\n")


def read(argv, *, docker=False, timeout=90):
    result = subprocess.run(argv, env=DOCKER_ENV if docker else ENV,
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout, shell=False)
    require(result.returncode == 0, "Read failed; inspect privately: " + " ".join(argv[:3]))
    return result.stdout.strip()


def cloud(*args):
    return json.loads(read(["gcloud", *args, "--quiet", "--format=json"]))


def budget_record():
    record = local_json(APPROVAL)
    require(all(type(record.get(k)) is type(v) and record[k] == v for k, v in EXPECTED_APPROVAL.items()),
            "Actual approval/funding record does not match this exact publication")
    require(isinstance(record.get("approvalReference"), str) and record["approvalReference"].strip(),
            "Actual user approval reference missing")
    require(isinstance(record.get("billingAccountName"), str) and re.fullmatch(
        r"billingAccounts/[0-9A-Fa-f]{6}-[0-9A-Fa-f]{6}-[0-9A-Fa-f]{6}", record["billingAccountName"]),
        "Verified existing billing-account resource name missing")
    now = datetime.now(timezone.utc)
    for key in ("approvedAtUtc", "creditsVerifiedAtUtc"):
        stamp = datetime.fromisoformat(record[key].replace("Z", "+00:00"))
        require(stamp.tzinfo is not None and stamp <= now, "Approval/funding timestamp invalid")
        if key == "creditsVerifiedAtUtc":
            require((now - stamp).total_seconds() <= 3600, "Funding evidence older than one hour")
    require(datetime.now(ZoneInfo("Australia/Melbourne")).date().isoformat() < "2026-10-28",
            "Recorded credits have expired")
    return record


def uploaded_archive():
    require(ARCHIVE.is_file() and not ARCHIVE.is_symlink() and ARCHIVE.stat().st_size == 373265304,
            "Fixed uploaded archive missing/size mismatch")
    require(sha_file(ARCHIVE) == ARCHIVE_SHA, "Uploaded archive SHA-256 mismatch")
    sidecar = ARCHIVE.with_name(ARCHIVE.name + ".sha256")
    # The embedded fixed values are authoritative; extra uploads are optional.
    if sidecar.exists() or sidecar.is_symlink():
        require(sidecar.is_file() and not sidecar.is_symlink() and sidecar.stat().st_size < 1024
                and sidecar.read_text().split() == [ARCHIVE_SHA, ARCHIVE.name], "Uploaded SHA sidecar mismatch")
    if METADATA.exists() or METADATA.is_symlink():
        metadata = local_json(METADATA)
        require(metadata.get("archiveBytes") == 373265304 and metadata.get("archiveSHA256") == ARCHIVE_SHA
                and metadata.get("imageId") == OCI_DIGEST and metadata.get("imageConfigDigest") == CONFIG_DIGEST
                and metadata.get("rootFsDiffIds") == DIFF_IDS and metadata.get("savedTag") == LOCAL_TAG,
                "Uploaded export metadata differs")
    # Stream only small metadata into memory; never extract anything to disk.
    small = {}
    wanted = {"index.json", "manifest.json", "blobs/sha256/" + OCI_DIGEST[7:],
              "blobs/sha256/" + CONFIG_DIGEST[7:]}
    with tarfile.open(ARCHIVE, "r|gz") as package:
        for entry in package:
            if entry.name in wanted:
                require(entry.isfile() and entry.size < 1024**2, "Unexpected archive metadata size/type")
                require(entry.name not in small, "Duplicate archive metadata")
                raw = package.extractfile(entry).read()
                if entry.name.startswith("blobs/"):
                    require(hashlib.sha256(raw).hexdigest() == entry.name.rsplit("/", 1)[1], "Archive blob mismatch")
                small[entry.name] = json.loads(raw)
    index, classic = small["index.json"], small["manifest.json"]
    require(len(index["manifests"]) == len(classic) == 1 and index["manifests"][0]["digest"] == OCI_DIGEST,
            "Archive manifest index differs")
    manifest = small["blobs/sha256/" + OCI_DIGEST[7:]]
    require(manifest["config"]["digest"] == CONFIG_DIGEST and len(manifest["layers"]) == 10
            and classic[0]["Config"] == "blobs/sha256/" + CONFIG_DIGEST[7:]
            and classic[0]["RepoTags"] == [LOCAL_TAG], "Archive tag/config chain differs")
    require(classic[0]["Layers"] == ["blobs/sha256/" + layer["digest"][7:] for layer in manifest["layers"]],
            "Archive layer manifest chain differs")
    config = small["blobs/sha256/" + CONFIG_DIGEST[7:]]
    require(config["architecture"] == "amd64" and config["os"] == "linux"
            and config["rootfs"]["diff_ids"] == DIFF_IDS, "Archive config/platform/rootfs differs")
    return config["config"], manifest["layers"]


def clean_source():
    require(SOURCE.is_dir() and read(["git", "-C", str(SOURCE), "rev-parse", "HEAD"]) == SOURCE_REVISION,
            "Wrong state-owning source revision")
    require(not read(["git", "-C", str(SOURCE), "status", "--porcelain", "--untracked-files=no"]),
            "Tracked state-owning source changed")


def same_layers(remote, expected):
    # Informational only: classic Docker may recompress the same diff IDs.
    # The fixed config digest cryptographically fixes the uncompressed rootfs.
    def normalize(layers):
        require(isinstance(layers, list), "Remote layer list schema differs")
        result = []
        for layer in layers:
            require(isinstance(layer, dict) and layer.get("mediaType") in (
                "application/vnd.oci.image.layer.v1.tar+gzip",
                "application/vnd.docker.image.rootfs.diff.tar.gzip"), "Remote layer media type differs")
            require(isinstance(layer.get("digest"), str) and re.fullmatch(r"sha256:[0-9a-f]{64}", layer["digest"])
                    and type(layer.get("size")) is int and layer["size"] > 0, "Remote layer descriptor schema differs")
            result.append({**layer, "mediaType": "gzip-layer"})
        return result
    return normalize(remote) == normalize(expected)


def approved_registry_state():
    summary = local_json(APPLY / "summary.json")
    expected = {"status": "registry-only-apply-and-verification-passed", "project": PROJECT,
        "projectNumber": NUMBER, "applyExecuted": True, "applyExitCode": 0,
        "configurationVerified": True, "managedResources": 9, "userManagedKeyCount": 0,
        "repositoryInitiallyEmpty": True, "onlyExpectedProjectIAMDelta": True,
        "runtimeActivated": False, "imagePublished": False,
        "sourceRevision": SOURCE_REVISION, "savedPlanSHA256": SAVED_PLAN_SHA}
    require(all(type(summary.get(k)) is type(v) and summary[k] == v for k, v in expected.items()),
            "Registry apply/post-verification is not a passing exact nine-resource result")
    require(SAVED_PLAN.is_file() and not SAVED_PLAN.is_symlink() and sha_file(SAVED_PLAN) == SAVED_PLAN_SHA,
            "Approved saved registry plan changed")
    detail = local_json(APPLY / "post-verification-private.json")
    require(STATE.is_file() and not STATE.is_symlink() and sha_file(STATE) == detail.get("stateSHA256"),
            "Registry Terraform state changed since verified apply")
    raw = json.loads(STATE.read_bytes())
    instances = [i for r in raw.get("resources", []) if r.get("mode") == "managed" for i in r.get("instances", [])]
    require(len(instances) == 9 and all(i.get("status") in (None, "ready") and not i.get("deposed") for i in instances),
            "Registry state count/taint/deposed mismatch")
    return detail["stateSHA256"]


def private_policies():
    ancestors = cloud("projects", "get-ancestors", PROJECT)
    require(any(a.get("type") == "project" and str(a.get("id")) in (PROJECT, NUMBER) for a in ancestors), "Project ancestry differs")
    policies = {"project": cloud("projects", "get-iam-policy", PROJECT),
        "repository": cloud("artifacts", "repositories", "get-iam-policy", "ecoguard", "--location=" + REGION, "--project=" + PROJECT)}
    for ancestor in ancestors:
        kind, value = ancestor.get("type"), str(ancestor.get("id"))
        if kind == "folder":
            policies[kind + value] = cloud("resource-manager", "folders", "get-iam-policy", value)
        elif kind == "organization":
            policies[kind + value] = cloud("organizations", "get-iam-policy", value)
        else:
            require(kind == "project", "Unknown ancestor schema")
    require(all(member not in ("allUsers", "allAuthenticatedUsers") for policy in policies.values()
        for binding in policy.get("bindings", []) for member in binding.get("members", [])), "Public effective IAM found")
    require(not policies["repository"].get("bindings"), "Unexpected explicit repository grant")
    return policies


def live_preflight(approval):
    require(read(["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"]) == OPERATOR,
            "Active CloudShell operator differs")
    require(read(["gcloud", "config", "get-value", "project"]) == PROJECT, "Active project differs")
    for setting in ("auth/impersonate_service_account", "auth/credential_file_override"):
        require(read(["gcloud", "config", "get-value", setting]) in ("", "(unset)"),
                "Unreviewed configured gcloud credential override: " + setting)
    project = cloud("projects", "describe", PROJECT)
    require(project.get("projectId") == PROJECT and str(project.get("projectNumber")) == NUMBER
            and project.get("lifecycleState") == "ACTIVE", "Live project identity differs")
    billing = cloud("billing", "projects", "describe", PROJECT)
    require(billing.get("billingEnabled") is True and billing.get("billingAccountName") == approval["billingAccountName"],
            "Project billing differs from the freshly verified existing-credit account")
    repo = cloud("artifacts", "repositories", "describe", "ecoguard", "--location=" + REGION, "--project=" + PROJECT)
    require(repo.get("name") == REPOSITORY and repo.get("format") == "DOCKER" and repo.get("mode") == "STANDARD_REPOSITORY"
            and not repo.get("remoteRepositoryConfig") and not repo.get("virtualRepositoryConfig"), "Live repository differs")
    services = cloud("services", "list", "--enabled", "--project=" + PROJECT)
    enabled = {s.get("config", {}).get("name") for s in services}
    require("artifactregistry.googleapis.com" in enabled and not enabled.intersection(
        {"containerscanning.googleapis.com", "ondemandscanning.googleapis.com"}), "Registry/scanning API state differs")
    require(cloud("artifacts", "docker", "images", "list", REGISTRY, "--include-tags", "--project=" + PROJECT) == [],
            "Repository has existing image/version; refuse overwrite")
    return private_policies()


def docker_log(args, filename, timeout):
    with (RESULT / filename).open("x") as log:
        outcome = subprocess.run(["docker", *args], env=DOCKER_ENV, stdin=subprocess.DEVNULL,
            stdout=log, stderr=subprocess.STDOUT, timeout=timeout, shell=False)
    require(outcome.returncode == 0, "Docker operation failed; see private " + filename)


def main():
    global DOCKER_ENV
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true", help="Use actual matching approval once; load/tag/push only")
    args = parser.parse_args()
    if not args.publish:
        if ARCHIVE.exists():
            uploaded_archive()
        print(json.dumps({"status": "dry-run", "dockerInvoked": False, "cloudInvoked": False,
            "archivePresent": ARCHIVE.exists(), "archive": str(ARCHIVE), "approvalFile": str(APPROVAL),
            "target": TARGET, "expectedApproval": {**EXPECTED_APPROVAL,
            "approvalReference": "actual user approval reference", "approvedAtUtc": "actual timestamp",
            "billingAccountName": "actual verified billingAccounts/XXXXXX-XXXXXX-XXXXXX",
            "creditsVerifiedAtUtc": "actual fresh read-only funding observation"}}, indent=2))
        return 0
    require(sys.platform == "linux" and os.environ.get("CLOUD_SHELL") == "true", "Run only in the existing Google CloudShell")
    require(not RESULT.exists() and not RESULT.is_symlink(), "Publication attempt exists; no retry")
    for command in ("git", "gcloud", "docker", "docker-credential-gcloud"):
        require(shutil.which(command, path=ENV.get("PATH")), "Required executable absent from PATH: " + command)
    for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH", "DOCKER_AUTH_CONFIG",
                "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_OAUTH_ACCESS_TOKEN", "GOOGLE_CREDENTIALS",
                "GOOGLE_IMPERSONATE_SERVICE_ACCOUNT", "GOOGLE_IMPERSONATE_SERVICE_ACCOUNT_DELEGATES",
                "GOOGLE_CLOUD_KEYFILE_JSON", "GCLOUD_KEYFILE_JSON",
                "CLOUDSDK_AUTH_ACCESS_TOKEN", "CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT", "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE"):
        require(not os.environ.get(key), "Unreviewed credential/daemon override: " + key)
    approval = budget_record()
    clean_source()
    config, archive_layers = uploaded_archive()
    state_sha = approved_registry_state()
    policies = live_preflight(approval)
    require(shutil.disk_usage(HOME_DIR).free >= 256 * 1024**2, "Insufficient home working space after upload")
    os.umask(0o077)
    RESULT.mkdir(mode=0o700)
    save("attempt-started.json", {"target": TARGET, "archiveSHA256": ARCHIVE_SHA,
        "startedAtUtc": datetime.now(timezone.utc).isoformat(), "retryPermitted": False})
    save("approval-copy.json", approval)
    save("private-iam-before.json", policies)
    client = RESULT / "docker-client"
    client.mkdir(mode=0o700)
    (client / "config.json").write_text(json.dumps({"credHelpers": {HOST: "gcloud"}}))
    DOCKER_ENV = {**ENV, "DOCKER_CONFIG": str(client), "DOCKER_CLI_HINTS": "false"}
    summary = {"status": "blocked", "target": TARGET, "archiveSHA256": ARCHIVE_SHA,
        "loadAttempted": False, "pushAttempted": False, "pushReturnedSuccess": False,
        "registryDigest": None, "runtimeActivated": False, "iamModified": False, "retryAttempted": False}
    try:
        info = json.loads(read(["docker", "info", "--format", "{{json .}}"], docker=True, timeout=30))
        require(info.get("OSType") == "linux" and info.get("Architecture") == "x86_64"
                and isinstance(info.get("DockerRootDir"), str), "Unexpected Docker daemon schema/platform")
        require(shutil.disk_usage(info["DockerRootDir"]).free >= 3 * 1024**3, "Docker storage has less than 3 GiB free")
        for tag in (LOCAL_TAG, TARGET):
            existing = read(["docker", "image", "ls", "--filter=reference=" + tag,
                "--no-trunc", "--format={{.ID}}"], docker=True, timeout=30).splitlines()
            require(not existing or len(existing) == 1 and existing[0] in (CONFIG_DIGEST, OCI_DIGEST),
                    "A local tag points to different content; refuse overwrite")
        summary["loadAttempted"] = True
        docker_log(["image", "load", "--input", str(ARCHIVE)], "load.log", 600)
        loaded = json.loads(read(["docker", "image", "inspect", LOCAL_TAG], docker=True, timeout=30))
        require(isinstance(loaded, list) and len(loaded) == 1, "Unexpected loaded-image schema")
        loaded = loaded[0]
        require(loaded.get("Id") in (CONFIG_DIGEST, OCI_DIGEST) and loaded.get("Os") == "linux"
            and loaded.get("Architecture") == "amd64" and loaded.get("RootFS", {}).get("Layers") == DIFF_IDS
            and all(loaded.get("Config", {}).get(k) == config.get(k) for k in ("User", "WorkingDir", "Cmd", "Entrypoint", "Env")),
            "Loaded image config/platform/rootfs differs")
        if loaded["Id"] == OCI_DIGEST:
            require(loaded.get("Descriptor", {}).get("annotations", {}).get("config.digest") == CONFIG_DIGEST,
                    "OCI image-store config linkage differs")
        save("loaded-image-private.json", loaded)
        budget_record()
        clean_source()
        require(sha_file(STATE) == state_sha, "Terraform state changed before push")
        require(cloud("artifacts", "docker", "images", "list", REGISTRY, "--include-tags", "--project=" + PROJECT) == [],
                "Image/version appeared; refuse overwrite")
        docker_log(["image", "tag", LOCAL_TAG, TARGET], "tag.log", 30)
        save("push-started.json", {"target": TARGET, "startedAtUtc": datetime.now(timezone.utc).isoformat()})
        summary["pushAttempted"] = True
        docker_log(["image", "push", TARGET], "push-private.log", 1200)
        summary["pushReturnedSuccess"] = True
        described = cloud("artifacts", "docker", "images", "describe", TARGET, "--project=" + PROJECT)
        save("registry-image-private.json", described)
        image_summary = described.get("image_summary", {})
        digest = image_summary.get("digest")
        require(isinstance(digest, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
            and image_summary.get("fully_qualified_digest") == IMAGE + "@" + digest,
            "Unrecognized gcloud image-summary schema; inspect saved metadata, do not repush")
        summary["registryDigest"] = digest
        remote = json.loads(read(["docker", "manifest", "inspect", IMAGE + "@" + digest], docker=True))
        save("registry-manifest-private.json", remote)
        require(remote.get("schemaVersion") == 2 and remote.get("config", {}).get("digest") == CONFIG_DIGEST
            and isinstance(remote.get("layers"), list) and len(remote["layers"]) == 10,
            "Remote manifest/config/layer schema or identity differs")
        summary["remoteCompressedLayersMatchArchive"] = same_layers(remote["layers"], archive_layers)
        require(sha_file(STATE) == state_sha and private_policies() == policies, "State/IAM changed during publication")
        summary.update(status="private-inference-image-published-and-verified", configDigest=CONFIG_DIGEST,
            imageUri=IMAGE + "@" + digest, cloudInferenceVerified=False)
    except Exception as error:
        summary["errorType"] = type(error).__name__
        summary["error"] = str(error) if isinstance(error, RuntimeError) else "Inspect private logs/metadata; no retry"
    finally:
        summary["observedAtUtc"] = datetime.now(timezone.utc).isoformat()
        save("summary.json", summary)
        print(json.dumps(summary, separators=(",", ":")), flush=True)
    return 0 if summary["status"] == "private-inference-image-published-and-verified" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"status": "blocked", "errorType": type(error).__name__,
            "error": str(error) if isinstance(error, RuntimeError) else "Invalid/incomplete local or read-only preflight input"}), flush=True)
        raise SystemExit(1)
