"""Isolated refresh of exactly two observed Artifact Registry computed fields.

Default prints scope only. --prepare creates a fresh saved REFRESH-ONLY plan at
source00, registry stage/image empty. --review-existing --plan-sha256 requires
the exact retained c56a... binary and finishes its missing review artifacts;
it never regenerates a plan or overwrites existing evidence.
--apply --plan-sha256 ACTUAL_REVIEWED_SHA
requires its passing exact offline review and applies that binary once. It does
not create/change cloud resources, grant IAM, enable APIs, invoke services or
relax the forward runtime gate. Keep historical state/blocked Run plan evidence.
Only labels null -> {} and the exact upload update_time transition below are
allowed. The resulting private attestation links old/new state SHA, lineage and
serial; future Run helpers must use this explicit checkpoint chain.
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
FROZEN = BASE / "frozen-publish-inference-20261024-1.py"
FROZEN_SHA = "f180a9ac01473e468bca17c6a4a1a8f5154422bfafb6b986f9a469b48444b462"
ROOT = BASE / "source/infra/gcp/environments/personal"
STATE = ROOT / "state/terraform.tfstate"
DIRECTORY = ROOT / "private/registry-publication-refresh-20261024-1"
BINARY = DIRECTORY / "refresh-only.tfplan"
APPLY = DIRECTORY / "apply-20261024-1"
MARKER = DIRECTORY / "apply-started.json"
PUBLICATION = BASE / "image-publication-20261024-3/summary.json"
TF = "/tmp/ecoguard-c-personal-20261023/tools/terraform"
DATA = Path("/tmp/ecoguard-c-personal-20261023/terraform-data-gcp")
HEAD = "00d58e0e8c65321cc759d575eafaba801c1e8253"
PROJECT, NUMBER = "ecoguard-fit3184-a2-2026", "995070689587"
REPO = "module.ecoguard.google_artifact_registry_repository.images[0]"
OLD_TIME, NEW_TIME = "2026-10-23T22:17:27.541917Z", "2026-10-23T22:42:43.012721Z"
EXISTING_PLAN_SHA = "c56a85845bc415daff55ff1302ee7aab9b52dcd5c0da50f59021b1e47e955b6c"
ENV = {**os.environ, "TF_DATA_DIR": str(DATA), "TF_IN_AUTOMATION": "1", "CHECKPOINT_DISABLE": "1",
       "CLOUDSDK_CORE_DISABLE_PROMPTS": "1", "PYTHONDONTWRITEBYTECODE": "1"}
STARTED = False


def require(ok, reason):
    if not ok: raise RuntimeError(reason)


def sha(data): return hashlib.sha256(data).hexdigest()
def now(): return datetime.now(timezone.utc).isoformat()


def save(path, value):
    with path.open("x") as output: json.dump(value, output, indent=2); output.write("\n")


def read(args):
    result = subprocess.run([str(x) for x in args], env=ENV, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=90, shell=False)
    require(result.returncode == 0, "Read failed: " + str(args[0]))
    return result.stdout.strip()


def values(document):
    items = GATE.managed(document)
    require(len(items) == 9 and len({r["address"] for r in items}) == 9, "Expected exactly nine managed resources")
    return {r["address"]: r["values"] for r in items}


def state_values(path):
    return values(json.loads(read([TF, "-chdir=" + str(ROOT), "show", "-json", path]))["values"]["root_module"])


def raw_state(data):
    raw = json.loads(data)
    entries = [i for r in raw["resources"] if r.get("mode") == "managed" for i in r.get("instances", [])]
    require(len(entries) == 9 and all(i.get("status") in (None, "ready") and not i.get("deposed") for i in entries), "Nine-state taint/deposed/count mismatch")
    require(isinstance(raw.get("lineage"), str) and raw["lineage"] and type(raw.get("serial")) is int, "Missing state lineage/serial")
    return raw


def identity(m):
    pool = m.cloud("iam", "workload-identity-pools", "describe", "ecoguard-aws", "--location=global", "--project=" + PROJECT)
    provider = m.cloud("iam", "workload-identity-pools", "providers", "describe", "aws-role", "--workload-identity-pool=ecoguard-aws", "--location=global", "--project=" + PROJECT)
    grant = m.cloud("iam", "service-accounts", "get-iam-policy", GATE.INVOKER_EMAIL, "--project=" + PROJECT)
    require(pool.get("name") == GATE.IDENTITY.POOL_NAME and pool.get("state") == "ACTIVE" and pool.get("disabled", False) is False, "Live WIF pool differs")
    require(provider.get("name") == GATE.IDENTITY.POOL_NAME + "/providers/aws-role" and provider.get("state") == "ACTIVE"
            and provider.get("disabled", False) is False and provider.get("aws", {}).get("accountId") == GATE.IDENTITY.AWS_ACCOUNT
            and provider.get("attributeMapping") == GATE.IDENTITY.MAPPING and provider.get("attributeCondition") == GATE.IDENTITY.CONDITION
            and not provider.get("oidc") and not provider.get("saml"), "Live WIF trust differs")
    require(grant.get("bindings") == [{"members": [GATE.IDENTITY.PRINCIPAL], "role": "roles/iam.workloadIdentityUser"}], "Sole live WIF grant differs")
    accounts = m.cloud("iam", "service-accounts", "list", "--project=" + PROJECT)
    emails = {a["email"] for a in accounts}
    require(GATE.INVOKER_EMAIL in emails and emails <= {GATE.INVOKER_EMAIL, f"service-{NUMBER}@gcp-sa-artifactregistry.iam.gserviceaccount.com"}
            and all(a.get("disabled", False) is False for a in accounts), "Unexpected/disabled service account")
    for email in emails:
        require(m.cloud("iam", "service-accounts", "keys", "list", "--iam-account=" + email, "--managed-by=user", "--project=" + PROJECT) == [], "User-managed SA key exists")
    return {"pool": pool, "provider": provider, "grant": grant, "serviceAccountEmails": sorted(emails), "userManagedKeyCount": 0}


def common():
    global GATE
    require(sys.platform == "linux" and os.environ.get("CLOUD_SHELL") == "true", "Existing Google CloudShell required")
    for k, v in os.environ.items():
        require(not (v and (k.startswith(("TF_CLI_ARGS", "TF_VAR_")) or k in ("TF_WORKSPACE", "TF_LOG", "TF_LOG_PATH", "TF_CLI_CONFIG_FILE", "TF_REATTACH_PROVIDERS"))), "Terraform environment override")
    for k in ("GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_OAUTH_ACCESS_TOKEN", "GOOGLE_CREDENTIALS", "GOOGLE_IMPERSONATE_SERVICE_ACCOUNT", "GOOGLE_IMPERSONATE_SERVICE_ACCOUNT_DELEGATES", "GOOGLE_CLOUD_KEYFILE_JSON", "GCLOUD_KEYFILE_JSON", "CLOUDSDK_AUTH_ACCESS_TOKEN", "CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT", "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE"):
        require(not os.environ.get(k), "Credential override")
    require(not (Path.home() / ".terraformrc").exists(), "Unreviewed Terraform CLI configuration")
    require(FROZEN.is_file() and not FROZEN.is_symlink() and sha(FROZEN.read_bytes()) == FROZEN_SHA, "Frozen publisher changed")
    spec = importlib.util.spec_from_file_location("frozen_publisher", FROZEN); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    require(m.SOURCE_REVISION == HEAD and m.PROJECT == PROJECT and m.NUMBER == NUMBER, "Frozen scope differs")
    m.clean_source(); m.approved_registry_state()
    require(read(["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"]) == m.OPERATOR
            and read(["gcloud", "config", "get-value", "project"]) == PROJECT, "Operator/project differs")
    for setting in ("auth/impersonate_service_account", "auth/credential_file_override"):
        require(read(["gcloud", "config", "get-value", setting]) in ("", "(unset)"), "Configured credential override")
    project = m.cloud("projects", "describe", PROJECT)
    require(project.get("projectId") == PROJECT and str(project.get("projectNumber")) == NUMBER and project.get("lifecycleState") == "ACTIVE", "Live project differs")
    require(not any(list(ROOT.glob(p)) for p in ("*.auto.tfvars", "*.auto.tfvars.json", "terraform.tfvars", "terraform.tfvars.json")), "Unexpected root input")
    require(read(["git", "-C", m.SOURCE, "hash-object", ROOT / ".terraform.lock.hcl"]) == read(["git", "-C", m.SOURCE, "rev-parse", HEAD + ":infra/gcp/environments/personal/.terraform.lock.hcl"]), "Provider lock changed")
    version = json.loads(read([TF, "-chdir=" + str(ROOT), "version", "-json"]))
    backend = json.loads((DATA / "terraform.tfstate").read_text())["backend"]
    require(version.get("terraform_version") == "1.17.0" and version.get("provider_selections") == {"registry.terraform.io/hashicorp/google": "7.46.1"}
            and backend.get("type") == "local" and backend["config"]["path"] == "state/terraform.tfstate"
            and read([TF, "-chdir=" + str(ROOT), "workspace", "show"]) == "default", "Tool/provider/backend/workspace differs")
    spec = importlib.util.spec_from_file_location("frozen_increment_gate", ROOT / "check_runtime_plan.py"); GATE = importlib.util.module_from_spec(spec); spec.loader.exec_module(GATE)
    publication = m.local_json(PUBLICATION)
    require(publication.get("status") == "private-inference-image-published-and-verified" and publication.get("registryDigest") == m.OCI_DIGEST
            and publication.get("imageUri") == m.IMAGE + "@" + m.OCI_DIGEST and publication.get("remoteManifestAndConfigBytesMatch") is True
            and publication.get("stateFileUnchanged") is True, "Actual successful publication proof missing")
    original = STATE.read_bytes(); raw = raw_state(original); prior = state_values(STATE)
    require(set(prior) == GATE.IDENTITY.expected_addresses() | GATE.REGISTRY_ADDITIONS and GATE.identity_is_exact(prior) and GATE.registry_is_exact(prior), "Exact nine baseline differs")
    require(prior[REPO].get("labels") is None and prior[REPO].get("update_time") == OLD_TIME, "Old computed metadata is not the observed exact baseline")
    repo = m.cloud("artifacts", "repositories", "describe", "ecoguard", "--location=us-central1", "--project=" + PROJECT)
    require(repo.get("name") == m.REPOSITORY and repo.get("format") == "DOCKER" and repo.get("mode") == "STANDARD_REPOSITORY"
            and prior[REPO].get("effective_labels") == {"goog-terraform-provisioned": "true"}
            and repo.get("labels") == prior[REPO]["effective_labels"] and repo.get("updateTime") == NEW_TIME
            and not repo.get("remoteRepositoryConfig") and not repo.get("virtualRepositoryConfig"), "Live repository metadata/config differs")
    policies, identities = m.private_policies(), identity(m)
    require(STATE.read_bytes() == original, "State changed during preflight")
    return m, original, raw, prior, repo, policies, identities


def inspect(document, prior):
    expected = {a: dict(v) for a, v in prior.items()}
    expected[REPO] = {**prior[REPO], "labels": {}, "update_time": NEW_TIME}
    require(document.get("complete") is True and document.get("errored") is not True and not document.get("deferred_changes"), "Incomplete/error/deferred refresh plan")
    drift = document.get("resource_drift", [])
    require(len(drift) == 1 and drift[0].get("address") == REPO and not drift[0].get("previous_address") and not drift[0].get("deposed"), "Drift is not the sole exact repository")
    change = drift[0]["change"]
    require(change.get("actions") == ["update"] and change.get("before") == prior[REPO] and change.get("after") == expected[REPO]
            and not GATE.has_unknown(change.get("after_unknown")) and not change.get("importing") and not drift[0].get("importing"), "Drift is not EXACT labels/update_time transition")
    refreshed = values(document["prior_state"]["values"]["root_module"])
    require(refreshed == expected, "Refreshed nine values changed outside exact metadata")
    all_changes = document.get("resource_changes", [])
    require(isinstance(all_changes, list), "Malformed refresh resource changes")
    planned_values = document.get("planned_values", {})
    if "root_module" in planned_values and planned_values["root_module"] != {}:
        planned = values(planned_values["root_module"])
        require(planned == expected, "Planned nine values changed outside exact metadata")
    else:
        # Terraform v1.17.0 jsonplan/plan.go: marshalPlannedValues uses changes;
        # refresh-only has none, so its authoritative nine are in prior_state.
        require(not all_changes, "Empty planned root requires zero resource changes")
        planned = refreshed
    changes = [r for r in all_changes if r.get("mode") == "managed"]
    require(not changes or len(changes) == 9 and {r.get("address") for r in changes} == set(prior), "Cloud action resource set differs")
    for resource in changes:
        action = resource.get("change", {})
        require(action.get("actions") == ["no-op"] and action.get("before") == action.get("after") == expected[resource["address"]]
                and not GATE.has_unknown(action.get("after_unknown")) and not resource.get("previous_address") and not resource.get("deposed")
                and not resource.get("importing") and not action.get("importing"), "Any managed cloud mutation/move/import/unknown is forbidden")
    require(all(r.get("actions") == ["no-op"] for r in document.get("output_changes", {}).values()), "Unexpected output change")
    variables = document.get("variables", {})
    require(variables.get("deployment_stage", {}).get("value") == "registry" and variables.get("inference_image", {}).get("value") == "", "Refresh inputs differ")
    require(GATE.identity_is_exact(planned) and GATE.registry_is_exact(planned), "Identity/registry semantics differ")
    return expected, len(changes)


def main():
    global STARTED
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(); group.add_argument("--prepare", action="store_true"); group.add_argument("--apply", action="store_true")
    group.add_argument("--review-existing", action="store_true")
    parser.add_argument("--plan-sha256"); args = parser.parse_args()
    if not (args.prepare or args.apply or args.review_existing):
        print(json.dumps({"status": "dry-run", "cloudInvoked": False, "applyExecuted": False, "directory": str(DIRECTORY),
            "scope": "state-only exact repository labels null-to-empty and upload update_time", "oldUpdateTime": OLD_TIME, "newUpdateTime": NEW_TIME})); return 0
    require(not MARKER.exists() and not MARKER.is_symlink() and not APPLY.exists(), "Refresh apply attempt exists; no retry")
    if args.prepare: require(not DIRECTORY.exists() and not DIRECTORY.is_symlink(), "Refresh plan exists; no overwrite")
    else: require(isinstance(args.plan_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", args.plan_sha256), "Explicit actual reviewed refresh plan SHA required")
    if args.review_existing:
        require(args.plan_sha256 == EXISTING_PLAN_SHA and DIRECTORY.is_dir() and not DIRECTORY.is_symlink(), "Exact retained refresh binary/directory required")
        require(not (DIRECTORY / "review-summary.json").exists(), "Refresh review summary already exists; no overwrite")
    m, original, raw, prior, repo, policies, identities = common()
    if args.prepare:
        DIRECTORY.mkdir(mode=0o700)
        (DIRECTORY / "state-before-private-backup.json").write_bytes(original)
        save(DIRECTORY / "preflight-private.json", {"sourceRevision": HEAD, "stateSHA256": sha(original), "lineage": raw["lineage"], "serial": raw["serial"],
            "priorValues": prior, "repositoryLive": repo, "iamBefore": policies, "identityBefore": identities, "publicationEvidenceSHA256": sha(PUBLICATION.read_bytes())})
        code = None
        try:
            with (DIRECTORY / "plan-private.log").open("x") as log:
                result = subprocess.run([TF, "-chdir=" + str(ROOT), "plan", "-refresh-only", "-input=false", "-no-color", "-lock-timeout=60s",
                    "-var=deployment_stage=registry", "-var=inference_image=", "-out=" + str(BINARY)], env=ENV, stdin=subprocess.DEVNULL,
                    stdout=log, stderr=subprocess.STDOUT, timeout=600, shell=False); code = result.returncode
        finally:
            save(DIRECTORY / "plan-exit.json", {"returnCode": code, "stateFileUnchanged": STATE.read_bytes() == original})
        require(code == 0 and STATE.read_bytes() == original, "Refresh plan failed or wrote state; inspect private log")
    else:
        require(sha(BINARY.read_bytes()) == args.plan_sha256, "Reviewed refresh binary SHA mismatch")
        require((DIRECTORY / "state-before-private-backup.json").read_bytes() == original, "Original refresh state checkpoint changed")
        checkpoint = m.local_json(DIRECTORY / "preflight-private.json")
        require(checkpoint.get("sourceRevision") == HEAD and checkpoint.get("stateSHA256") == sha(original)
                and checkpoint.get("lineage") == raw["lineage"] and checkpoint.get("serial") == raw["serial"]
                and checkpoint.get("priorValues") == prior and checkpoint.get("repositoryLive") == repo
                and checkpoint.get("iamBefore") == policies and checkpoint.get("identityBefore") == identities
                and checkpoint.get("publicationEvidenceSHA256") == sha(PUBLICATION.read_bytes()), "Retained refresh preflight evidence changed")
        if args.review_existing:
            plan_exit = m.local_json(DIRECTORY / "plan-exit.json")
            require(plan_exit.get("returnCode") == 0 and plan_exit.get("stateFileUnchanged") is True, "Retained refresh plan did not complete read-only")
        else:
            previous = m.local_json(DIRECTORY / "review-summary.json")
            require(previous.get("status") == "exact-publication-metadata-refresh-plan-passed" and previous.get("savedPlanSHA256") == args.plan_sha256,
                    "Matching passed refresh review missing")
    document = json.loads(read([TF, "-chdir=" + str(ROOT), "show", "-json", BINARY]))
    expected, noops = inspect(document, prior)
    if args.prepare or args.review_existing:
        json_path, text_path = DIRECTORY / "refresh-only.json", DIRECTORY / "refresh-only-show.txt"
        if json_path.exists() or json_path.is_symlink():
            require(m.local_json(json_path) == document, "Retained refresh JSON differs; no overwrite")
        else:
            save(json_path, document)
        text = read([TF, "-chdir=" + str(ROOT), "show", "-no-color", BINARY]) + "\n"
        if text_path.exists() or text_path.is_symlink():
            require(text_path.is_file() and not text_path.is_symlink() and text_path.read_text() == text, "Retained refresh text differs; no overwrite")
        else:
            with text_path.open("x") as output: output.write(text)
        require("Warning:" not in (DIRECTORY / "plan-private.log").read_text(), "Refresh plan warned; inspect privately")
        m.clean_source(); require(STATE.read_bytes() == original, "State changed during refresh review")
        report = {"status": "exact-publication-metadata-refresh-plan-passed", "savedPlanSHA256": sha(BINARY.read_bytes()), "sourceRevision": HEAD,
            "managedResources": 9, "managedNoopEntries": noops, "managedCloudMutations": 0, "driftResources": 1,
            "changedFields": ["labels", "update_time"], "stateSHA256": sha(original), "stateFileUnchanged": True, "applyExecuted": False,
            "existingBinaryReviewed": args.review_existing, "planRegenerated": args.prepare, "observedAtUtc": now()}
        save(DIRECTORY / "review-summary.json", report); print(json.dumps(report)); return 0
    APPLY.mkdir(mode=0o700)
    save(APPLY / "preflight-private.json", {"iamBefore": policies, "identityBefore": identities, "repositoryLive": repo, "stateSHA256": sha(original)})
    m.clean_source(); require(STATE.read_bytes() == original and sha(BINARY.read_bytes()) == args.plan_sha256, "Source/state/binary changed before state-only apply")
    save(MARKER, {"startedAtUtc": now(), "savedPlanSHA256": args.plan_sha256, "scope": "exact-state-only-publication-metadata-refresh"}); STARTED = True
    outcome = {"status": "blocked", "applyExecuted": True, "savedPlanSHA256": args.plan_sha256, "sourceRevision": HEAD,
        "oldStateSHA256": sha(original), "cloudResourcesMutated": False, "runtimeCreated": False, "retryAttempted": False, "applyExitCode": None}
    try:
        with (APPLY / "apply-private.log").open("x") as log:
            result = subprocess.run([TF, "-chdir=" + str(ROOT), "apply", "-input=false", "-no-color", "-lock-timeout=60s", str(BINARY)],
                env=ENV, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, timeout=300, shell=False)
        outcome["applyExitCode"] = result.returncode
    except Exception as error:
        outcome["executionErrorType"] = type(error).__name__
        if isinstance(error, subprocess.TimeoutExpired): outcome["processOutcomeUncertain"] = True
    finally:
        try: (APPLY / "post-state-immediate.tfstate").write_bytes(STATE.read_bytes())
        except Exception as error: outcome["postStateCaptureErrorType"] = type(error).__name__
    try:
        post = STATE.read_bytes(); after = raw_state(post)
        require(after["lineage"] == raw["lineage"] and after["serial"] > raw["serial"] and state_values(STATE) == expected, "New state differs outside exact repository computed fields")
        require(m.private_policies() == policies and identity(m) == identities, "Live IAM/identity/key state changed")
        require(m.cloud("artifacts", "repositories", "describe", "ecoguard", "--location=us-central1", "--project=" + PROJECT) == repo, "Live repository changed during state-only apply")
        m.clean_source(); require(STATE.read_bytes() == post, "State changed during post-verification")
        outcome.update(newStateSHA256=sha(post), lineage=after["lineage"], oldSerial=raw["serial"], newSerial=after["serial"], managedResources=9,
            changedFields=["labels", "update_time"], oldUpdateTime=OLD_TIME, newUpdateTime=NEW_TIME, configurationVerified=True)
        if outcome["applyExitCode"] == 0 and not outcome.get("processOutcomeUncertain"):
            outcome["status"] = "exact-publication-metadata-state-refresh-passed"
    except Exception as error:
        outcome["verificationError"] = str(error) if isinstance(error, RuntimeError) else type(error).__name__
    finally:
        try: (APPLY / "post-state-final.tfstate").write_bytes(STATE.read_bytes())
        except Exception as error: outcome["status"] = "blocked"; outcome["finalStateCaptureErrorType"] = type(error).__name__
        outcome["observedAtUtc"] = now(); save(APPLY / "summary.json", outcome); print(json.dumps(outcome))
    return 0 if outcome["status"] == "exact-publication-metadata-state-refresh-passed" else 1


if __name__ == "__main__":
    os.umask(0o077)
    try: raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"status": "blocked", "applyExecuted": STARTED, "errorType": type(error).__name__,
            "error": str(error) if isinstance(error, RuntimeError) else "Invalid/incomplete exact refresh evidence"})); raise SystemExit(1)
