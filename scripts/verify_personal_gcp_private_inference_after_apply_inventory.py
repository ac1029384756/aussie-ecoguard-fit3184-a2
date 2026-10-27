"""Inert by default; --verify performs read-only audit3 of the completed apply.

Preserves B4 and blocked audits1/2. Only inventory allowance added to audit2 is
the exact enabled, unprivileged default Compute account: no assigned role in
any captured project/repository/ancestor policy, no own IAM bindings or user
keys. Its retained creation record has no identified actor; none is invented.
No apply, state/IAM/API write, token fetch, invocation or retry is provided.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
BASE = Path.home() / "ecoguard-c-personal-20261023"
ROOT = BASE / "source/infra/gcp/environments/personal"
ORIGINAL = ROOT / "private/private-inference-plan-20261024-2/apply-20261024-1"
RESULT = ORIGINAL / "read-only-verification-20261024-3"
FROZEN1 = BASE / "frozen-verify-private-run-after-apply-20261024-1.py"
FROZEN2 = BASE / "frozen-verify-private-run-after-apply-20261024-2.py"
FROZEN1_SHA = "2e632cbc95ee200a24ca47a12a78419d77e48f30dd1d36151dd19cc93ef15b92"
FROZEN2_SHA = "e380ca06f4eb0f17f9e60d5f5c99d2a9495a41bb070d5f9ecda288ef1173bf6a"
AUDIT_SHA = "e5e676c2c83aba7d0418a180c6021f65bfece81ed333fb5544629a739b0c7608"
AUDIT = BASE / "run-automatic-service-agents-observation-20261024-1/audit-events-private.json"
DIAGNOSTIC = BASE / "private-run-live-diagnostic-20261024-1"
CREATION = DIAGNOSTIC / "iam-compute-audit-events-private.json"
DEFAULT_OBSERVATION = DIAGNOSTIC / "default-compute-private.json"
PROJECT, NUMBER = "ecoguard-fit3184-a2-2026", "995070689587"
DEFAULT = NUMBER + "-compute@developer.gserviceaccount.com"
CREATED = "2026-10-23T23:06:03.125884298Z"
STATE_SHA = "f3b6113be12f34b05701da2e095d0df5763a97d8efdcd6a38a7fdbfc0d1d8fad"


def require(ok, reason):
    if not ok: raise RuntimeError(reason)


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def stamp(value): return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load(name, path, expected):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size < 1024**2 and sha(path) == expected, "Frozen helper differs")
    spec = importlib.util.spec_from_file_location(name, path); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def http_evidence_paths():
    """Fixed additional dependencies only; no reads, writes or cloud calls."""
    return {FROZEN1, FROZEN2, AUDIT, CREATION, DEFAULT_OBSERVATION}


def http_identity_and_keys(a, m, after=True):
    """Standalone exact post-apply identity reader; only read-only gcloud calls."""
    require(after is True, "This reader is only for the existing post-apply inventory")
    g = a.GATE
    pool = m.cloud("iam", "workload-identity-pools", "describe", "ecoguard-aws", "--location=global", "--project=" + PROJECT)
    provider = m.cloud("iam", "workload-identity-pools", "providers", "describe", "aws-role", "--workload-identity-pool=ecoguard-aws", "--location=global", "--project=" + PROJECT)
    grant = m.cloud("iam", "service-accounts", "get-iam-policy", g.INVOKER_EMAIL, "--project=" + PROJECT)
    require(pool.get("name") == g.IDENTITY.POOL_NAME and pool.get("state") == "ACTIVE" and pool.get("disabled", False) is False, "Live WIF pool differs")
    require(provider.get("name") == g.IDENTITY.POOL_NAME + "/providers/aws-role" and provider.get("state") == "ACTIVE"
            and provider.get("disabled", False) is False and provider.get("aws", {}).get("accountId") == g.IDENTITY.AWS_ACCOUNT
            and provider.get("attributeMapping") == g.IDENTITY.MAPPING and provider.get("attributeCondition") == g.IDENTITY.CONDITION
            and not provider.get("oidc") and not provider.get("saml"), "Live WIF trust differs")
    require(a.edges(grant) == {("roles/iam.workloadIdentityUser", g.IDENTITY.PRINCIPAL, "null")}, "Invoker WIF grant differs")
    accounts = m.cloud("iam", "service-accounts", "list", "--project=" + PROJECT)
    allowed = {g.INVOKER_EMAIL, a.RUNTIME, DEFAULT}
    require(isinstance(accounts, list) and len(accounts) == 3 and {v.get("email") for v in accounts} == allowed
            and all(v.get("projectId") == PROJECT and v.get("disabled", False) is False for v in accounts), "Exact enabled three-account inventory differs")
    for email in sorted(allowed):
        require(m.cloud("iam", "service-accounts", "keys", "list", "--iam-account=" + email, "--managed-by=user", "--project=" + PROJECT) == [], "User-managed service-account key exists")
    default = m.cloud("iam", "service-accounts", "describe", DEFAULT, "--project=" + PROJECT)
    require(default.get("email") == DEFAULT and default.get("projectId") == PROJECT and default.get("disabled", False) is False
            and default.get("displayName") == "Default compute service account", "Default Compute account differs")
    own = m.cloud("iam", "service-accounts", "get-iam-policy", DEFAULT, "--project=" + PROJECT)
    require(not own.get("bindings"), "Default Compute account has own IAM bindings")
    policies = m.private_policies()
    require(not any(member == "serviceAccount:" + DEFAULT for policy in policies.values() for _, member, _ in a.edges(policy)), "Default Compute account has assigned roles")
    return {"pool": pool, "provider": provider, "grant": grant, "serviceAccountEmails": sorted(allowed), "userManagedKeyCount": 0,
            "defaultCompute": {"account": default, "accountPolicy": own, "assignedRoles": [], "userManagedKeyCount": 0}}


def creation_proof(m):
    events = m.local_json(CREATION)
    require(isinstance(events, list) and len(events) == 3, "Creation audit is not the retained three-event list")
    selected = [e for e in events if e.get("timestamp") == CREATED]
    require(len(selected) == 1, "Exact default Compute creation event missing/duplicated")
    event = selected[0]; payload = event.get("protoPayload", {}); request = payload.get("request", {})
    require(event.get("logName", "").startswith(f"projects/{PROJECT}/logs/")
            and event.get("resource", {}).get("labels", {}).get("project_id", PROJECT) == PROJECT
            and payload.get("methodName") == "google.iam.admin.v1.CreateServiceAccount"
            and payload.get("resourceName") in (f"projects/{PROJECT}", f"projects/{NUMBER}", PROJECT, NUMBER)
            and payload.get("authenticationInfo", {}) == {} and payload.get("status", {}).get("code", 0) == 0
            and request.get("account_id") == "service-" + NUMBER and request.get("name") == "projects/" + PROJECT
            and request.get("service_account", {}).get("display_name") == "Default compute service account"
            and request.get("service_account", {}).get("email") == DEFAULT
            and payload.get("response", {}).get("email") == DEFAULT, "Default Compute creation record differs")
    require(stamp("2026-10-23T23:06:02.436724Z") < stamp(CREATED) < stamp("2026-10-23T23:06:09.520034070Z"), "Default creation outside recorded Run enablement window")
    return {"path": str(CREATION), "sha256": sha(CREATION), "observedAtUtc": CREATED, "email": DEFAULT,
            "actor": None, "actorIdentified": False, "insideRunEnablementWindow": True, "creationRequestShapeVerified": True,
            "defaultObservationPath": str(DEFAULT_OBSERVATION), "defaultObservationSHA256": sha(DEFAULT_OBSERVATION)}


def http_local_proofs(m):
    """Only frozen helper imports and local JSON/hash reads; no cloud calls."""
    require(sha(AUDIT) == AUDIT_SHA, "Retained automatic-agent audit SHA differs")
    second = load("frozen_audit2_local_proof", FROZEN2, FROZEN2_SHA)
    return {"auditProof": second.audit_proof(m), "defaultComputeCreationProof": creation_proof(m)}


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--verify", action="store_true"); args = parser.parse_args()
    if not args.verify:
        print(json.dumps({"status": "dry-run", "cloudInvoked": False, "applyExecuted": False, "result": str(RESULT)})); return 0
    second = load("frozen_audit2", FROZEN2, FROZEN2_SHA)
    old = load("frozen_audit1", FROZEN1, FROZEN1_SHA)
    require(second.RESULT == ORIGINAL / "read-only-verification-20261024-2" and old.ORIGINAL == ORIGINAL, "Prior audit scope differs")
    old.RESULT = RESULT
    a, m, pre, old_raw, prior_values, image, post, hashes = old.preflight()
    require(sha(a.STATE) == STATE_SHA, "Observed post-apply state SHA differs")
    for directory, timestamp, error in ((ORIGINAL / "read-only-verification-20261024-1", "2026-10-23T23:12:48.957026+00:00", "Unexpected project IAM delta"),
            (ORIGINAL / "read-only-verification-20261024-2", "2026-10-23T23:20:39.220938+00:00", "Unexpected/missing/disabled project service account")):
        failed = m.local_json(directory / "summary.json")
        require(failed.get("status") == "blocked" and failed.get("errorType") == "RuntimeError" and failed.get("error") == error
                and failed.get("applyExecuted") is False and stamp(failed["observedAtUtc"]) == stamp(timestamp), "Retained prior audit failure differs")
    local_proofs = http_local_proofs(m); proof = local_proofs["auditProof"]; created = local_proofs["defaultComputeCreationProof"]
    require(m.local_json(second.RESULT / "summary.json").get("auditProof") == proof, "Previously verified automatic-agent proof changed")
    for path in http_evidence_paths():
        require(path.is_file() and not path.is_symlink(), "Retained additional evidence missing/symlinked")
        hashes[path] = sha(path)
    RESULT.mkdir(mode=0o700); a.RESULT = RESULT
    for name in ("STATE", "raw_state", "state_values", "GATE", "save", "edges", "meta", "RUNTIME", "live_run", "clean_source", "digest"):
        setattr(second, name, getattr(a, name))
    second.identity_and_keys = lambda module, after=False: http_identity_and_keys(a, module, after)
    a.save("original-evidence-sha256-private.json", {str(p): value for p, value in hashes.items()})
    a.save("automatic-agent-audit-proof-private.json", proof); a.save("default-compute-creation-proof-private.json", created)
    summary = {"status": "blocked", "project": PROJECT, "projectNumber": NUMBER, "sourceRevision": old.HEAD,
        "savedPlanSHA256": old.PLAN_SHA, "imageUri": image, "originalApplyExitCode": 0, "originalApplySummaryPreserved": True,
        "applyExecuted": False, "stateModified": False, "iamModified": False, "apisModified": False,
        "authenticatedInvocationAttempted": False, "awsActivated": False, "normalization": "exact canonical IAM grant.name on deep copy only",
        "auditProof": proof, "defaultComputeCreationProof": created,
        "autoGrantScopeVariance": {"previousExpectedProjectAdditions": 1, "observedProjectAdditions": 3,
            "additionalGoogleManagedAgents": [e["member"] for e in proof["addedProjectEdges"] if e["role"] != "roles/run.serviceAgent"],
            "newGrantPerformedByVerifier": False, "notIndividuallyListedInOriginalApproval": True},
        "inventoryVariance": {"additionalAccount": DEFAULT, "assignedRoleCount": 0, "ownIamBindingCount": 0, "userManagedKeyCount": 0,
            "creationActorIdentified": False, "createdByVerifier": False}}
    try:
        detail = second.verify_after(m, old_raw, prior_values, pre["iamBefore"], pre["identityBefore"], image)
        detail.update(auditProof=proof, defaultComputeCreationProof=created, autoGrantScopeVariance=summary["autoGrantScopeVariance"], inventoryVariance=summary["inventoryVariance"])
        a.save("post-verification-private.json", detail)
        require(a.STATE.read_bytes() == post and all(p.is_file() and not p.is_symlink() and sha(p) == value for p, value in hashes.items()), "Original state/evidence changed during read-only verification")
        summary.update(status="private-run-configuration-readonly-verification-passed", configurationVerified=True, managedResources=13,
            stateSHA256=STATE_SHA, userManagedKeyCount=0, url=detail["run"]["url"], readyRevision=detail["run"]["readyRevision"],
            originalEvidenceUnchanged=True, cloudInferenceVerified=False, crossCloudVerified=False)
    except Exception as error:
        summary.update(configurationVerified=False, errorType=type(error).__name__, error=str(error) if isinstance(error, RuntimeError) else "Inspect new private evidence; no mutation/retry")
    finally:
        try: (RESULT / "post-state-private-backup.tfstate").write_bytes(a.STATE.read_bytes())
        except Exception as error: summary["status"] = "blocked"; summary["stateCaptureErrorType"] = type(error).__name__
        summary["observedAtUtc"] = datetime.now(timezone.utc).isoformat(); a.save("summary.json", summary); print(json.dumps(summary, separators=(",", ":")), flush=True)
    return 0 if summary["status"] == "private-run-configuration-readonly-verification-passed" else 1


if __name__ == "__main__":
    os.umask(0o077)
    try: raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"status": "blocked", "applyExecuted": False, "errorType": type(error).__name__, "error": str(error) if isinstance(error, RuntimeError) else "Invalid/incomplete exact audit proof"})); raise SystemExit(1)
