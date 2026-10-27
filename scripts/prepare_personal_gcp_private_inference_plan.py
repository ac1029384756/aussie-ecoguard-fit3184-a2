"""Prepare one frozen private-inference saved plan; never apply or enable APIs.

Run only in the existing Google CloudShell state-owning workspace, after the
operator has published the image and completed the exact state-only metadata refresh:
  python3 THIS_FILE --image us-central1-docker.pkg.dev/ecoguard-fit3184-a2-2026/ecoguard/inference@sha256:ACTUAL_DIGEST
The image argument has no default. This helper checks its exact path/digest form,
actual image provenance from the retained successful publication and refresh checkpoint. It retains private artifacts and refuses to overwrite an
attempt. A blocked plan, missing API, unknown security field or failed gate stops
the workflow; this helper cannot enable APIs, change source, retry or apply.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
BASE = Path.home() / "ecoguard-c-personal-20261023"
SOURCE = BASE / "source"
ROOT = SOURCE / "infra/gcp/environments/personal"
STATE = ROOT / "state/terraform.tfstate"
PRIVATE = ROOT / "private"
ORIGINAL = PRIVATE / "registry-plan-20261024-1/apply-20261024-1"
REFRESH = PRIVATE / "registry-publication-refresh-20261024-1"
PREVIOUS = REFRESH / "apply-20261024-1"
ATTEMPT = PRIVATE / "private-inference-plan-20261024-2"
TF = Path("/tmp/ecoguard-c-personal-20261023/tools/terraform")
DATA = Path("/tmp/ecoguard-c-personal-20261023/terraform-data-gcp")
HEAD = "3dd63c805b625fb3b378ac977d51c6959d599f0c"
HISTORICAL_HEAD = "00d58e0e8c65321cc759d575eafaba801c1e8253"
PROJECT, NUMBER = "ecoguard-fit3184-a2-2026", "995070689587"
REGISTRY_PLAN_SHA = "0f62543fe74a7b0fc71e9e8c2b1930de853448d1ab4c257b9d215399c9d5ba86"
IMAGE_PATTERN = re.compile(r"us-central1-docker\.pkg\.dev/ecoguard-fit3184-a2-2026/ecoguard/inference@sha256:[0-9a-f]{64}")
ENV = {**os.environ, "TF_DATA_DIR": str(DATA), "CHECKPOINT_DISABLE": "1",
       "TF_IN_AUTOMATION": "1", "CLOUDSDK_CORE_DISABLE_PROMPTS": "1",
       "PYTHONDONTWRITEBYTECODE": "1"}
ATTEMPT_CREATED = False


def require(value, reason):
    if not value:
        raise RuntimeError(reason)


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def run(args, timeout=90):
    result = subprocess.run([str(a) for a in args], env=ENV, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=timeout, shell=False)
    require(result.returncode == 0, "Read/preparation failed: " + str(args[0]))
    return result.stdout.strip()


def save(name, value):
    with (ATTEMPT / name).open("x") as output:
        json.dump(value, output, indent=2)
        output.write("\n")


def cloud(*args):
    return json.loads(run(["gcloud", *args, "--quiet", "--format=json"]))


def source_is_frozen():
    return (run(["git", "-C", SOURCE, "rev-parse", "HEAD"]) == HEAD
            and not run(["git", "-C", SOURCE, "status", "--porcelain", "--untracked-files=no"]))


def preflight(image):
    global GATE
    require(bool(IMAGE_PATTERN.fullmatch(image)), "An actual immutable digest in the exact personal inference path is required")
    for key, value in os.environ.items():
        require(not (value and (key.startswith(("TF_CLI_ARGS", "TF_VAR_")) or key in (
            "TF_WORKSPACE", "TF_LOG", "TF_LOG_PATH", "TF_CLI_CONFIG_FILE", "TF_REATTACH_PROVIDERS"))),
            "Unexpected Terraform environment override")
    for key in ("GOOGLE_CREDENTIALS", "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_OAUTH_ACCESS_TOKEN",
                "GOOGLE_IMPERSONATE_SERVICE_ACCOUNT", "GOOGLE_IMPERSONATE_SERVICE_ACCOUNT_DELEGATES",
                "GOOGLE_CLOUD_KEYFILE_JSON", "GCLOUD_KEYFILE_JSON", "CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT",
                "CLOUDSDK_AUTH_ACCESS_TOKEN", "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE"):
        require(not os.environ.get(key), "Unreviewed provider credential override")
    require(not (Path.home() / ".terraformrc").exists(), "Unreviewed Terraform CLI configuration")
    require(ROOT.is_dir() and PRIVATE.is_dir() and PREVIOUS.is_dir() and TF.is_file(), "Existing state-owning workspace/tool missing")
    require(not ATTEMPT.exists(), "Plan attempt already exists; no overwrite or retry")
    require(run(["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"])
            == "hoshigahoshii@163.com", "Unexpected active operator")
    require(run(["gcloud", "config", "get-value", "project"]) == PROJECT, "Unexpected active project")
    require(run(["gcloud", "config", "get-value", "auth/impersonate_service_account"])
            in ("", "(unset)"), "Unreviewed gcloud impersonation")
    project = cloud("projects", "describe", PROJECT)
    require(project.get("projectId") == PROJECT and str(project.get("projectNumber")) == NUMBER
            and project.get("lifecycleState") == "ACTIVE", "Project identity mismatch")
    require(source_is_frozen(), "Wrong or modified state-owning source revision")
    require(not any(list(ROOT.glob(p)) for p in ("*.auto.tfvars", "*.auto.tfvars.json", "terraform.tfvars", "terraform.tfvars.json")), "Unexpected root input file")
    require(run(["git", "-C", SOURCE, "hash-object", ROOT / ".terraform.lock.hcl"])
            == run(["git", "-C", SOURCE, "rev-parse", HEAD + ":infra/gcp/environments/personal/.terraform.lock.hcl"]), "Provider lock differs from frozen source")
    original = STATE.read_bytes()
    require(original == (PREVIOUS / "post-state-final.tfstate").read_bytes(), "State differs from exact publication-metadata refresh checkpoint")
    raw = json.loads(original)
    instances = [i for r in raw["resources"] if r.get("mode") == "managed" for i in r.get("instances", [])]
    require(len(instances) == 9 and all(i.get("status") in (None, "ready") and not i.get("deposed")
            for i in instances), "Expected nine untainted current state instances")
    old = (ORIGINAL / "post-state-final.tfstate").read_bytes()
    old_raw = json.loads(old)
    proof = json.loads((ORIGINAL / "post-verification-private.json").read_text())
    previous = json.loads((ORIGINAL / "summary.json").read_text())
    require(previous.get("status") == "registry-only-apply-and-verification-passed"
            and previous.get("applyExitCode") == 0 and previous.get("managedResources") == 9
            and previous.get("sourceRevision") == HISTORICAL_HEAD and previous.get("savedPlanSHA256") == REGISTRY_PLAN_SHA,
            "Historical registry apply was not verified")
    require(proof.get("stateSHA256") == digest(old) and proof.get("lineage") == old_raw.get("lineage")
            and proof.get("serial") == old_raw.get("serial") and proof.get("managedResources") == 9
            and old == (REFRESH / "state-before-private-backup.json").read_bytes(), "Historical state checkpoint differs")
    refreshed = json.loads((PREVIOUS / "summary.json").read_text())
    review = json.loads((REFRESH / "review-summary.json").read_text())
    expected_refresh = {"status": "exact-publication-metadata-state-refresh-passed", "applyExitCode": 0,
        "configurationVerified": True, "managedResources": 9, "cloudResourcesMutated": False, "runtimeCreated": False,
        "sourceRevision": HISTORICAL_HEAD, "changedFields": ["labels", "update_time"], "retryAttempted": False,
        "oldUpdateTime": "2026-10-23T22:17:27.541917Z", "newUpdateTime": "2026-10-23T22:42:43.012721Z"}
    require(all(type(refreshed.get(k)) is type(v) and refreshed[k] == v for k,v in expected_refresh.items()),
            "Exact state-only refresh attestation missing or different")
    refresh_sha = digest((REFRESH / "refresh-only.tfplan").read_bytes())
    require(review.get("status") == "exact-publication-metadata-refresh-plan-passed"
            and review.get("savedPlanSHA256") == refreshed.get("savedPlanSHA256") == refresh_sha
            and review.get("stateSHA256") == refreshed.get("oldStateSHA256") == digest(old)
            and refreshed.get("newStateSHA256") == digest(original)
            and raw.get("lineage") == old_raw.get("lineage") == refreshed.get("lineage")
            and raw.get("serial") == refreshed.get("newSerial") > refreshed.get("oldSerial") == old_raw.get("serial"),
            "State A-to-B refresh hash/lineage/serial chain differs")
    publication = BASE / "image-publication-20261024-3/summary.json"
    publication_value = json.loads(publication.read_text())
    require(json.loads((REFRESH / "preflight-private.json").read_text()).get("publicationEvidenceSHA256") == digest(publication.read_bytes())
            and publication_value.get("status") == "private-inference-image-published-and-verified"
            and publication_value.get("imageUri") == image and publication_value.get("remoteManifestAndConfigBytesMatch") is True,
            "Actual verified image/publication continuity differs")
    version = json.loads(run([TF, "-chdir=" + str(ROOT), "version", "-json"]))
    require(version.get("terraform_version") == "1.17.0" and version.get("provider_selections")
            == {"registry.terraform.io/hashicorp/google": "7.46.1"}, "Unexpected Terraform/provider version")
    backend = json.loads((DATA / "terraform.tfstate").read_text())["backend"]
    require(backend.get("type") == "local" and backend["config"]["path"] == "state/terraform.tfstate"
            and run([TF, "-chdir=" + str(ROOT), "workspace", "show"]) == "default", "Wrong backend/workspace")
    spec = importlib.util.spec_from_file_location("frozen_runtime_increment_gate", ROOT / "check_runtime_plan.py")
    GATE = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(GATE)
    state = json.loads(run([TF, "-chdir=" + str(ROOT), "show", "-json", STATE]))
    resources = GATE.managed(state["values"]["root_module"])
    values = {r["address"]: r["values"] for r in resources}
    require(len(resources) == 9 and set(values) == GATE.IDENTITY.expected_addresses() | GATE.REGISTRY_ADDITIONS
            and GATE.identity_is_exact(values) and GATE.registry_is_exact(values), "Existing nine state resources differ")
    before = json.loads(run([TF, "-chdir=" + str(ROOT), "show", "-json", ORIGINAL / "post-state-final.tfstate"]))
    old_resources = GATE.managed(before["values"]["root_module"])
    old_values = {r["address"]: r["values"] for r in old_resources}
    repo = GATE.MODULE + GATE.REPOSITORY
    require(len(old_resources) == 9 and old_values.get(repo, {}).get("labels") is None
            and old_values[repo].get("update_time") == expected_refresh["oldUpdateTime"], "Original repository state differs")
    expected_values = dict(old_values)
    expected_values[repo] = {**old_values[repo], "labels": {}, "update_time": expected_refresh["newUpdateTime"]}
    require(values == expected_values, "Refresh changed managed values outside exact two metadata fields")
    require(STATE.read_bytes() == original and source_is_frozen(), "State/source changed during preflight")
    return original, raw


def exported(name, args):
    result = subprocess.run([str(a) for a in args], env=ENV, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=90, shell=False)
    (ATTEMPT / (name + ".stderr.log")).write_text(result.stderr)
    require(result.returncode == 0, "Saved-plan export failed; inspect private stderr log")
    return result.stdout, result.stderr


def main():
    global ATTEMPT_CREATED
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Actual independently verified immutable published inference digest")
    args = parser.parse_args()
    original, raw = preflight(args.image)
    ATTEMPT.mkdir(mode=0o700)
    ATTEMPT_CREATED = True
    (ATTEMPT / "state-before-private-backup.json").write_bytes(original)
    save("preflight.json", {"project": PROJECT, "projectNumber": NUMBER, "sourceRevision": HEAD,
         "image": args.image, "stateSHA256": digest(original), "lineage": raw["lineage"],
         "serial": raw["serial"], "managedResources": 9, "observedAtUtc": now()})
    lock_before = (ROOT / ".terraform.lock.hcl").read_bytes()
    with (ATTEMPT / "init.log").open("x") as log:
        init = subprocess.run([str(TF), "-chdir=" + str(ROOT), "init", "-input=false", "-lockfile=readonly", "-no-color"],
                              env=ENV, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                              timeout=240, shell=False)
    require(init.returncode == 0 and (ROOT / ".terraform.lock.hcl").read_bytes() == lock_before, "Readonly initialization failed or lock changed")
    backend = json.loads((DATA / "terraform.tfstate").read_text())["backend"]
    version = json.loads(run([TF, "-chdir=" + str(ROOT), "version", "-json"]))
    require(backend.get("type") == "local" and backend["config"]["path"] == "state/terraform.tfstate"
            and run([TF, "-chdir=" + str(ROOT), "workspace", "show"]) == "default"
            and version.get("terraform_version") == "1.17.0" and version.get("provider_selections")
            == {"registry.terraform.io/hashicorp/google": "7.46.1"}, "Backend/workspace/tool/provider changed during init")
    validation = json.loads(run([TF, "-chdir=" + str(ROOT), "validate", "-json"]))
    save("validate.json", validation)
    require(validation.get("valid") and validation.get("error_count") == 0 and validation.get("warning_count") == 0,
            "Validation failed or warned; inspect private report")
    require(STATE.read_bytes() == original and source_is_frozen(), "State/source changed before plan")
    print("PRIVATE_INFERENCE_PLAN_STARTED: read-only plan; no API enable or apply.", flush=True)
    binary = ATTEMPT / "private-inference.tfplan"
    result_code = None
    try:
        with (ATTEMPT / "plan.log").open("x") as log:
            result = subprocess.run([str(TF), "-chdir=" + str(ROOT), "plan", "-input=false", "-no-color", "-lock-timeout=60s",
                                     "-var=deployment_stage=private-inference", "-var=inference_image=" + args.image,
                                     "-out=" + str(binary)], env=ENV, stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=subprocess.STDOUT, timeout=600, shell=False)
            result_code = result.returncode
    finally:
        after = STATE.read_bytes()
        (ATTEMPT / "state-after-plan-private-backup.json").write_bytes(after)
        save("plan-exit.json", {"returnCode": result_code, "stateFileUnchanged": after == original})
    require(result_code == 0, "Terraform plan failed; inspect private plan.log. No API enablement or retry performed")
    require(STATE.read_bytes() == original, "Planning changed the authoritative state")
    text, text_stderr = exported("show-text", [TF, "-chdir=" + str(ROOT), "show", "-no-color", binary])
    (ATTEMPT / "private-inference-show.txt").write_text(text)
    json_text, json_stderr = exported("show-json", [TF, "-chdir=" + str(ROOT), "show", "-json", binary])
    document = json.loads(json_text)
    save("private-inference.json", document)
    report = GATE.inspect_plan(document, "private-inference", args.image)
    save("gate-report.json", report)
    changes = [r for r in document.get("resource_changes", []) if r.get("mode") == "managed"]
    headers = re.findall(r"^  # (.+) will be created$", text, re.MULTILINE)
    summary = {"status": "blocked", "project": PROJECT, "projectNumber": NUMBER, "sourceRevision": HEAD,
        "image": args.image, "savedPlanSHA256": digest(binary.read_bytes()),
        "creates": sum(r["change"]["actions"] == ["create"] for r in changes),
        "noops": sum(r["change"]["actions"] == ["no-op"] for r in changes),
        "otherChanges": [{"address": r["address"], "actions": r["change"]["actions"]} for r in changes
                         if r["change"]["actions"] not in (["create"], ["no-op"])],
        "gateStatus": report["status"], "gateChecksPassed": sum(c["passed"] for c in report["checks"]),
        "gateChecksTotal": len(report["checks"]), "failedChecks": [c["name"] for c in report["checks"] if not c["passed"]],
        "securityUnknownPaths": [{"address": r["address"], "path": list(path)} for r in changes
            if r["address"] in GATE.RUNTIME_ADDITIONS for path in GATE.required_paths(r["address"])
            if GATE.unknown_at(r["change"].get("after_unknown", {}), path)],
        "textCreateHeaders": headers,
        "warnings": any("Warning:" in output for output in (text, text_stderr, json_stderr, (ATTEMPT / "plan.log").read_text())),
        "stateFileUnchanged": STATE.read_bytes() == original, "sourceUnchanged": source_is_frozen(),
        "resourceDriftEntries": len(document.get("resource_drift", [])), "observedAtUtc": now(),
        "applyExecuted": False, "applyAuthorized": False, "apiEnabledByHelper": False,
        "runtimeCreated": False, "imageProvenanceVerified": True, "registryMetadataRefreshVerified": True}
    passed = (report["status"] == "offline-increment-plan-passed" and summary["gateChecksPassed"] == 13
              and summary["gateChecksTotal"] == 13 and summary["creates"] == 4 and summary["noops"] == 9
              and not summary["otherChanges"] and len(headers) == 4 and set(headers) == GATE.RUNTIME_ADDITIONS
              and not summary["warnings"] and summary["stateFileUnchanged"] and summary["sourceUnchanged"])
    if passed:
        summary["status"] = "private-inference-saved-plan-review-passed"
    save("review-summary.json", summary)
    print(json.dumps(summary, separators=(",", ":")), flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    os.umask(0o077)
    try:
        raise SystemExit(main())
    except Exception as error:
        failure = {"status": "blocked", "applyExecuted": False, "apiEnabledByHelper": False,
                   "reason": str(error) if isinstance(error, RuntimeError) else type(error).__name__, "observedAtUtc": now()}
        if ATTEMPT_CREATED and not (ATTEMPT / "blocked-summary.json").exists():
            save("blocked-summary.json", failure)
        print(json.dumps(failure, separators=(",", ":")), flush=True)
        raise SystemExit(1)
