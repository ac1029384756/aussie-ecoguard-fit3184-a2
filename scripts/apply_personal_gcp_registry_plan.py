"""Frozen registry-only execution helper. Default is read-only preflight.

Run only in the existing Google CloudShell state-owning workspace. --apply
requires an actual approval record at PLAN/apply-approval.json with these fields:
approved=true, project, projectNumber, sourceRevision, savedPlanSHA256,
approvedScope="registry-two-create-with-google-service-agent", approvedAtUtc,
approvalReference, additionalPersonalSpendLimitAUD=0, creditExpiryDate="2026-10-28",
creditsVerifiedAtUtc, cleanupByDateAustraliaMelbourne="2026-10-27".
The operator writes that record only after the user's real approval and a fresh
funding check. This script never creates an approval record or publishes images.
No init, checkout, plan, API-enable, IAM write, retry, or runtime action is used.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

sys.dont_write_bytecode = True
BASE = Path.home() / "ecoguard-c-personal-20261023"
SOURCE = BASE / "source"
ROOT = SOURCE / "infra/gcp/environments/personal"
STATE = ROOT / "state/terraform.tfstate"
PLAN = ROOT / "private/registry-plan-20261024-1"
BINARY = PLAN / "registry.tfplan"
BEFORE = PLAN / "state-before-private-backup.json"
APPLY = PLAN / "apply-20261024-1"
MARKER = PLAN / "apply-started.json"
TF = Path("/tmp/ecoguard-c-personal-20261023/tools/terraform")
DATA = Path("/tmp/ecoguard-c-personal-20261023/terraform-data-gcp")
HEAD = "00d58e0e8c65321cc759d575eafaba801c1e8253"
SHA = "0f62543fe74a7b0fc71e9e8c2b1930de853448d1ab4c257b9d215399c9d5ba86"
PROJECT, NUMBER, REGION = "ecoguard-fit3184-a2-2026", "995070689587", "us-central1"
API = "artifactregistry.googleapis.com"
REPOSITORY = f"projects/{PROJECT}/locations/{REGION}/repositories/ecoguard"
INVOKER = f"ecoguard-aws-invoker@{PROJECT}.iam.gserviceaccount.com"
AGENT = f"service-{NUMBER}@gcp-sa-artifactregistry.iam.gserviceaccount.com"
AGENT_ROLE = "roles/artifactregistry.serviceAgent"
ENV = {**os.environ, "TF_DATA_DIR": str(DATA), "TF_IN_AUTOMATION": "1",
       "CHECKPOINT_DISABLE": "1", "CLOUDSDK_CORE_DISABLE_PROMPTS": "1"}
EXECUTION_STARTED = False


def require(value, reason):
    if not value:
        raise RuntimeError(reason)


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(argv, timeout=90):
    result = subprocess.run([str(a) for a in argv], env=ENV, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=timeout, shell=False)
    require(result.returncode == 0, "Read failed: " + " ".join(str(a) for a in argv[:3]))
    return result.stdout.strip()


def cloud(*args):
    return json.loads(read(["gcloud", *args, "--quiet", "--format=json"]))


def save(path, value):
    with path.open("x") as output:
        json.dump(value, output, indent=2)
        output.write("\n")


def canonical(value):
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return sorted((canonical(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True))
    return value


def policy_edges(policy):
    return {(b["role"], member, json.dumps(canonical(b.get("condition")), sort_keys=True))
            for b in policy.get("bindings", []) for member in b.get("members", [])}


def policy_meta(policy):
    return canonical({k: v for k, v in policy.items() if k not in ("bindings", "etag", "version")})


def no_public(policy):
    return all(member not in ("allUsers", "allAuthenticatedUsers")
               for _, member, _ in policy_edges(policy))


def policy_same(left, right):
    return policy_edges(left) == policy_edges(right) and policy_meta(left) == policy_meta(right)


def state_values(path):
    document = json.loads(read([TF, "-chdir=" + str(ROOT), "show", "-json", path]))
    items = [r for r in GATE.managed(document["values"]["root_module"])]
    require(len(items) == len({r["address"] for r in items}), "Duplicate managed state address")
    return {r["address"]: r["values"] for r in items}


def raw_state(data, expected_count):
    raw = json.loads(data)
    items = [i for r in raw["resources"] if r.get("mode") == "managed" for i in r.get("instances", [])]
    require(len(items) == expected_count and all(i.get("status") in (None, "ready")
            and not i.get("deposed") for i in items), "Raw state count/taint/deposed mismatch")
    require(isinstance(raw.get("lineage"), str) and raw["lineage"] and isinstance(raw.get("serial"), int),
            "State lineage/serial missing")
    return raw


def live_baseline():
    ancestors = cloud("projects", "get-ancestors", PROJECT)
    require(any(a.get("type") == "project" and str(a.get("id")) in (PROJECT, NUMBER)
                for a in ancestors), "Unexpected project ancestry")
    policies = {"project": cloud("projects", "get-iam-policy", PROJECT)}
    for item in ancestors:
        kind, identifier = item.get("type"), str(item.get("id"))
        if kind == "folder":
            policies["folder/" + identifier] = cloud("resource-manager", "folders", "get-iam-policy", identifier)
        elif kind == "organization":
            policies["organization/" + identifier] = cloud("organizations", "get-iam-policy", identifier)
        else:
            require(kind == "project", "Unknown ancestor type")
    require(all(no_public(p) for p in policies.values()), "Public inherited/project IAM binding")
    pool = cloud("iam", "workload-identity-pools", "describe", "ecoguard-aws", "--location=global", "--project=" + PROJECT)
    provider = cloud("iam", "workload-identity-pools", "providers", "describe", "aws-role",
                     "--workload-identity-pool=ecoguard-aws", "--location=global", "--project=" + PROJECT)
    account = cloud("iam", "service-accounts", "describe", INVOKER, "--project=" + PROJECT)
    grant = cloud("iam", "service-accounts", "get-iam-policy", INVOKER, "--project=" + PROJECT)
    require(pool.get("name") == GATE.IDENTITY.POOL_NAME and pool.get("state") == "ACTIVE"
            and pool.get("disabled", False) is False, "Pool identity/state mismatch")
    require(provider.get("name") == GATE.IDENTITY.POOL_NAME + "/providers/aws-role"
            and provider.get("state") == "ACTIVE" and provider.get("disabled", False) is False
            and provider.get("aws", {}).get("accountId") == GATE.IDENTITY.AWS_ACCOUNT
            and provider.get("attributeMapping") == GATE.IDENTITY.MAPPING
            and provider.get("attributeCondition") == GATE.IDENTITY.CONDITION
            and not provider.get("oidc") and not provider.get("saml"), "Live WIF trust mismatch")
    require(account.get("email") == INVOKER and account.get("disabled", False) is False,
            "Invoker identity/state mismatch")
    require(policy_edges(grant) == {("roles/iam.workloadIdentityUser", GATE.IDENTITY.PRINCIPAL, "null")},
            "Invoker grant is not the sole exact WIF principal")
    accounts = cloud("iam", "service-accounts", "list", "--project=" + PROJECT)
    emails = {a["email"] for a in accounts}
    require(INVOKER in emails and emails <= {INVOKER, AGENT}, "Unexpected project service account")
    for email in sorted(emails):
        require(cloud("iam", "service-accounts", "keys", "list", "--iam-account=" + email,
                      "--managed-by=user", "--project=" + PROJECT) == [], "User-managed service-account key exists")
    return {"ancestors": canonical(ancestors), "policies": policies, "pool": pool,
            "provider": provider, "account": account, "grant": grant, "serviceAccountEmails": sorted(emails),
            "userManagedKeyCount": 0}


def preflight():
    global GATE
    for key, value in os.environ.items():
        require(not (value and (key.startswith(("TF_CLI_ARGS", "TF_VAR_")) or key in (
            "TF_WORKSPACE", "TF_LOG", "TF_LOG_PATH", "TF_CLI_CONFIG_FILE", "TF_REATTACH_PROVIDERS"))),
            "Unreviewed Terraform environment override")
    for key in ("GOOGLE_CREDENTIALS", "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_OAUTH_ACCESS_TOKEN",
                "GOOGLE_IMPERSONATE_SERVICE_ACCOUNT", "GOOGLE_IMPERSONATE_SERVICE_ACCOUNT_DELEGATES",
                "GOOGLE_CLOUD_KEYFILE_JSON", "GCLOUD_KEYFILE_JSON", "CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT",
                "CLOUDSDK_AUTH_ACCESS_TOKEN", "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE"):
        require(not os.environ.get(key), "Unreviewed provider credential override")
    require(not (Path.home() / ".terraformrc").exists(), "Unreviewed Terraform CLI configuration")
    require(ROOT.is_dir() and PLAN.is_dir() and TF.is_file(), "Existing state-owning workspace/tool missing")
    require(not MARKER.exists() and not APPLY.exists(), "An execution attempt already exists; no retry")
    require(read(["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"])
            == "hoshigahoshii@163.com", "Unexpected active operator")
    require(read(["gcloud", "config", "get-value", "project"]) == PROJECT, "Unexpected active project")
    require(read(["gcloud", "config", "get-value", "auth/impersonate_service_account"])
            in ("", "(unset)"), "Unreviewed gcloud impersonation")
    project = cloud("projects", "describe", PROJECT)
    require(project.get("projectId") == PROJECT and str(project.get("projectNumber")) == NUMBER
            and project.get("lifecycleState") == "ACTIVE", "Project identity mismatch")
    require(read(["git", "-C", SOURCE, "rev-parse", "HEAD"]) == HEAD, "Wrong state-owning source revision")
    require(not read(["git", "-C", SOURCE, "status", "--porcelain", "--untracked-files=no"]), "Tracked source changed")
    require(not any(list(ROOT.glob(p)) for p in ("*.auto.tfvars", "*.auto.tfvars.json", "terraform.tfvars", "terraform.tfvars.json")), "Unexpected root input file")
    require(read(["git", "-C", SOURCE, "hash-object", ROOT / ".terraform.lock.hcl"])
            == read(["git", "-C", SOURCE, "rev-parse", HEAD + ":infra/gcp/environments/personal/.terraform.lock.hcl"]), "Provider lock differs from source")
    spec = importlib.util.spec_from_file_location("frozen_runtime_increment_gate", ROOT / "check_runtime_plan.py")
    GATE = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(GATE)
    version = json.loads(read([TF, "-chdir=" + str(ROOT), "version", "-json"]))
    require(version.get("terraform_version") == "1.17.0" and version.get("provider_selections")
            == {"registry.terraform.io/hashicorp/google": "7.46.1"}, "Unexpected Terraform/provider version")
    backend = json.loads((DATA / "terraform.tfstate").read_text())["backend"]
    require(backend["type"] == "local" and backend["config"]["path"] == "state/terraform.tfstate"
            and read([TF, "-chdir=" + str(ROOT), "workspace", "show"]) == "default", "Wrong backend/workspace")
    original = STATE.read_bytes()
    require(original == BEFORE.read_bytes(), "State no longer matches reviewed plan checkpoint")
    raw = raw_state(original, 7)
    checkpoint = json.loads((PLAN / "preflight.json").read_text())
    require(checkpoint["stateSHA256"] == sha(original) and checkpoint["lineage"] == raw["lineage"]
            and checkpoint["serial"] == raw["serial"], "State hash/lineage/serial changed")
    require(sha(BINARY.read_bytes()) == SHA, "Saved plan binary hash changed")
    document = json.loads(read([TF, "-chdir=" + str(ROOT), "show", "-json", BINARY]))
    report = GATE.inspect_plan(document, "registry")
    require(report["status"] == "offline-increment-plan-passed" and len(report["checks"]) == 12
            and all(c["passed"] for c in report["checks"]), "Saved plan gate failed")
    values = state_values(STATE)
    require(set(values) == GATE.IDENTITY.expected_addresses(), "Existing seven state addresses differ")
    baseline = live_baseline()
    require(STATE.read_bytes() == original and sha(BINARY.read_bytes()) == SHA, "Plan/state changed during preflight")
    return original, raw, values, baseline


def approval():
    record = json.loads((PLAN / "apply-approval.json").read_text())
    expected = {"approved": True, "project": PROJECT, "projectNumber": NUMBER,
                "sourceRevision": HEAD, "savedPlanSHA256": SHA,
                "approvedScope": "registry-two-create-with-google-service-agent",
                "additionalPersonalSpendLimitAUD": 0, "creditExpiryDate": "2026-10-28",
                "cleanupByDateAustraliaMelbourne": "2026-10-27"}
    require(all(type(record.get(k)) is type(v) and record[k] == v for k, v in expected.items()), "Approval scope/funding record mismatch")
    require(isinstance(record.get("approvalReference"), str) and record["approvalReference"].strip(), "Actual user approval reference missing")
    for key in ("approvedAtUtc", "creditsVerifiedAtUtc"):
        timestamp = datetime.fromisoformat(record[key].replace("Z", "+00:00"))
        require(timestamp.tzinfo is not None and timestamp <= datetime.now(timezone.utc), "Approval/funding timestamp invalid")
        if key == "creditsVerifiedAtUtc":
            require((datetime.now(timezone.utc) - timestamp).total_seconds() <= 3600,
                    "Funding observation older than one hour; refresh read-only check")
    require(datetime.now(ZoneInfo("Australia/Melbourne")).date().isoformat() < "2026-10-28", "Recorded credits have expired")
    return record


def verify_after(before_raw, before_values, before_live):
    post_bytes = STATE.read_bytes()
    raw = raw_state(post_bytes, 9)
    require(raw["lineage"] == before_raw["lineage"] and raw["serial"] > before_raw["serial"], "Post-state lineage/serial mismatch")
    values = state_values(STATE)
    require(set(values) == GATE.IDENTITY.expected_addresses() | GATE.REGISTRY_ADDITIONS, "Post-state is not exactly nine addresses")
    require(all(values[a] == v for a, v in before_values.items()), "Existing seven state resources changed")
    require(GATE.registry_is_exact(values), "Post-state registry settings differ")
    services = cloud("services", "list", "--enabled", "--project=" + PROJECT)
    require(any(s.get("config", {}).get("name") == API and s.get("state") == "ENABLED" for s in services), "Artifact Registry API not enabled")
    repo = cloud("artifacts", "repositories", "describe", "ecoguard", "--location=" + REGION, "--project=" + PROJECT)
    require(repo.get("name") == REPOSITORY and repo.get("format") == "DOCKER" and repo.get("mode") == "STANDARD_REPOSITORY"
            and not repo.get("remoteRepositoryConfig") and not repo.get("virtualRepositoryConfig"), "Live repository settings differ")
    repo_policy = cloud("artifacts", "repositories", "get-iam-policy", "ecoguard", "--location=" + REGION, "--project=" + PROJECT)
    require(no_public(repo_policy) and not policy_edges(repo_policy), "Unexpected explicit repository IAM grant")
    images = cloud("artifacts", "docker", "images", "list", f"{REGION}-docker.pkg.dev/{PROJECT}/ecoguard", "--project=" + PROJECT)
    require(images == [], "Repository is not initially empty")
    after = live_baseline()
    require(after["ancestors"] == before_live["ancestors"], "Project ancestry changed")
    for key in before_live["policies"]:
        old, new = before_live["policies"][key], after["policies"][key]
        if key == "project":
            expected = (AGENT_ROLE, "serviceAccount:" + AGENT, "null")
            require(not (policy_edges(old) - policy_edges(new)) and policy_edges(new) - policy_edges(old) <= {expected}
                    and expected in policy_edges(new) and policy_meta(old) == policy_meta(new), "Unexpected project IAM delta")
        else:
            require(policy_same(old, new), "Ancestor IAM changed")
    for key in ("pool", "provider", "account"):
        require(after[key] == before_live[key], "Existing live identity changed: " + key)
    require(policy_same(after["grant"], before_live["grant"]), "Existing invoker grant changed")
    require(STATE.read_bytes() == post_bytes, "State changed during post-apply verification")
    return {"lineage": raw["lineage"], "serial": raw["serial"], "stateSHA256": sha(post_bytes),
            "managedResources": 9, "apiEnabled": True, "repositoryInitiallyEmpty": True,
            "repository": repo, "repositoryPolicy": repo_policy, "live": after,
            "expectedServiceAgent": AGENT, "expectedServiceAgentRole": AGENT_ROLE}


def main():
    global EXECUTION_STARTED
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Requires actual matching approval record; exact saved binary once")
    args = parser.parse_args()
    original, before_raw, before_values, baseline = preflight()
    if not args.apply:
        print(json.dumps({"status": "read-only-preflight-passed", "project": PROJECT, "projectNumber": NUMBER,
                          "sourceRevision": HEAD, "savedPlanSHA256": SHA, "managedResources": 7,
                          "gateChecksPassed": 12, "applyExecuted": False, "approvalChecked": False,
                          "observedAtUtc": now()}, separators=(",", ":")))
        return 0
    record = approval()
    APPLY.mkdir(mode=0o700)
    save(APPLY / "approval-copy.json", record)
    save(APPLY / "live-before.json", baseline)
    (APPLY / "state-before.tfstate").write_bytes(original)
    require(STATE.read_bytes() == original and sha(BINARY.read_bytes()) == SHA, "Plan/state changed immediately before execution")
    require(read(["git", "-C", SOURCE, "rev-parse", "HEAD"]) == HEAD and not
            read(["git", "-C", SOURCE, "status", "--porcelain", "--untracked-files=no"]),
            "Source changed immediately before execution")
    save(MARKER, {"startedAtUtc": now(), "savedPlanSHA256": SHA, "applyDirectory": str(APPLY)})
    EXECUTION_STARTED = True
    outcome = {"status": "blocked", "project": PROJECT, "projectNumber": NUMBER, "sourceRevision": HEAD,
               "savedPlanSHA256": SHA, "applyExecuted": True, "applyExitCode": None,
               "retryAttempted": False, "runtimeActivated": False, "imagePublished": False}
    print("REGISTRY_EXACT_SAVED_PLAN_APPLY_STARTED; no retries or image/runtime actions.", flush=True)
    try:
        with (APPLY / "apply.log").open("x") as log:
            result = subprocess.run([str(TF), "-chdir=" + str(ROOT), "apply", "-input=false", "-no-color",
                                     "-lock-timeout=60s", str(BINARY)], env=ENV, stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=subprocess.STDOUT, timeout=900, shell=False)
        outcome["applyExitCode"] = result.returncode
    except subprocess.TimeoutExpired:
        outcome["processOutcomeUncertain"] = True
        outcome["error"] = "Apply timed out; no retry; inspect state and live operations"
    except Exception as error:
        outcome["error"] = "Execution exception: " + type(error).__name__
    finally:
        try:
            (APPLY / "post-state-immediate.tfstate").write_bytes(STATE.read_bytes())
            outcome["postStateCaptured"] = True
        except Exception as error:
            outcome["postStateCaptured"] = False
            outcome["postStateCaptureError"] = type(error).__name__
    try:
        details = verify_after(before_raw, before_values, baseline)
        save(APPLY / "post-verification-private.json", details)
        outcome.update({"configurationVerified": True, "managedResources": 9, "userManagedKeyCount": 0,
                        "repositoryInitiallyEmpty": True, "onlyExpectedProjectIAMDelta": True})
        if outcome["applyExitCode"] == 0 and not outcome.get("processOutcomeUncertain"):
            outcome["status"] = "registry-only-apply-and-verification-passed"
    except Exception as error:
        outcome["configurationVerified"] = False
        outcome["verificationError"] = str(error) if isinstance(error, RuntimeError) else type(error).__name__
    finally:
        try:
            (APPLY / "post-state-final.tfstate").write_bytes(STATE.read_bytes())
        except Exception as error:
            outcome["finalStateCaptureError"] = type(error).__name__
        outcome["observedAtUtc"] = now()
        save(APPLY / "summary.json", outcome)
        print(json.dumps(outcome, separators=(",", ":")), flush=True)
    return 0 if outcome["status"] == "registry-only-apply-and-verification-passed" else 1


if __name__ == "__main__":
    os.umask(0o077)
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"status": "blocked", "applyExecuted": EXECUTION_STARTED,
                          "reason": str(error) if isinstance(error, RuntimeError) else type(error).__name__}, separators=(",", ":")))
        raise SystemExit(1)
