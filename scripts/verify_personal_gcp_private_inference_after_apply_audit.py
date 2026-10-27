"""Read-only audit2; no grants, state writes, invocations or apply retries.

Retains original B4 and blocked audit1. Reuses pinned audit1 preflight/canonical
name adapter. B4.verify_after is copied below with ONLY its expected project IAM
delta changed from one to exactly three Google-managed service-agent ADD edges,
after validating the exact observed Google-manager audit events in the Run API
enablement window. This reports a scope variance; it does not claim that those
already-existing grants were individually authorized or create new grants.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
BASE = Path.home() / "ecoguard-c-personal-20261023"
FROZEN1 = BASE / "frozen-verify-private-run-after-apply-20261024-1.py"
FROZEN1_SHA = "2e632cbc95ee200a24ca47a12a78419d77e48f30dd1d36151dd19cc93ef15b92"
ROOT = BASE / "source/infra/gcp/environments/personal"
ORIGINAL = ROOT / "private/private-inference-plan-20261024-2/apply-20261024-1"
AUDIT1 = ORIGINAL / "read-only-verification-20261024-1"
RESULT = ORIGINAL / "read-only-verification-20261024-2"
AUDIT = BASE / "run-automatic-service-agents-observation-20261024-1/audit-events-private.json"
PROJECT, NUMBER = "ecoguard-fit3184-a2-2026", "995070689587"
STATE_SHA = "f3b6113be12f34b05701da2e095d0df5763a97d8efdcd6a38a7fdbfc0d1d8fad"
MANAGER = "service-agent-manager@system.gserviceaccount.com"
START, END = "2026-10-23T23:06:02.436724Z", "2026-10-23T23:06:09.520034070Z"
OPERATION = "operations/acf.p2-995070689587-71624cdc-4319-4ab8-a20b-e7af7c454e6b"
ENABLE_ENTRIES = {(START, "1u1nmccd1wak"): True, (END, "ka87vrdrip2"): False, (END, "ka87vrdrip0"): False}
EXPECTED = {
    ("roles/containerregistry.ServiceAgent", f"serviceAccount:service-{NUMBER}@containerregistry.iam.gserviceaccount.com", "null"): "2026-10-23T23:06:03.544765Z",
    ("roles/pubsub.serviceAgent", f"serviceAccount:service-{NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com", "null"): "2026-10-23T23:06:05.345511Z",
    ("roles/run.serviceAgent", f"serviceAccount:service-{NUMBER}@serverless-robot-prod.iam.gserviceaccount.com", "null"): "2026-10-23T23:06:06.940033Z",
}


def require(ok, reason):
    if not ok: raise RuntimeError(reason)


def file_sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def stamp(value): return datetime.fromisoformat(value.replace("Z", "+00:00"))


def audit_proof(m):
    events = m.local_json(AUDIT)
    require(isinstance(events, list) and len(events) == 11, "Expected exact retained eleven audit events")
    found, enable = {}, {}
    for event in events:
        payload = event.get("protoPayload", {})
        require(event.get("logName", "").startswith(f"projects/{PROJECT}/logs/")
                and event.get("resource", {}).get("labels", {}).get("project_id", PROJECT) == PROJECT, "Audit event project differs")
        delta = []
        for key in ("serviceData", "metadata"):
            delta.extend(payload.get(key, {}).get("policyDelta", {}).get("bindingDeltas", []))
        if delta:
            require(payload.get("authenticationInfo", {}).get("principalEmail") == MANAGER
                    and payload.get("serviceName") == "cloudresourcemanager.googleapis.com"
                    and payload.get("methodName", "").endswith("SetIamPolicy")
                    and payload.get("resourceName") in (f"projects/{PROJECT}", f"projects/{NUMBER}", PROJECT, NUMBER)
                    and payload.get("status", {}).get("code", 0) == 0, "IAM delta actor/resource/method/status differs")
            for item in delta:
                edge = (item.get("role"), item.get("member"), json.dumps(item.get("condition"), sort_keys=True))
                require(item.get("action") == "ADD" and edge in EXPECTED and edge not in found
                        and event.get("timestamp") == EXPECTED[edge] and stamp(START) < stamp(event["timestamp"]) < stamp(END), "Audit delta is not an exact observed automatic ADD")
                found[edge] = event["timestamp"]
        if payload.get("methodName", "").endswith(".EnableService"):
            key = (event.get("timestamp"), event.get("insertId"))
            require(key in ENABLE_ENTRIES and key not in enable, "Unexpected/duplicate Run enablement log identity")
            resource = payload.get("request", {}).get("name", payload.get("resourceName", ""))
            operation = event.get("operation", {})
            require(payload.get("serviceName") == "serviceusage.googleapis.com"
                    and payload.get("authenticationInfo", {}).get("principalEmail") == m.OPERATOR
                    and resource in (f"projects/{PROJECT}/services/run.googleapis.com", f"projects/{NUMBER}/services/run.googleapis.com")
                    and payload.get("status", {}).get("code", 0) == 0 and operation.get("id") == OPERATION
                    and operation.get("producer") == "serviceusage.googleapis.com"
                    and operation.get("first", False) is ENABLE_ENTRIES[key]
                    and operation.get("last", False) is (not ENABLE_ENTRIES[key]), "Run enablement audit differs")
            enable[key] = operation
    require(found == EXPECTED and set(enable) == set(ENABLE_ENTRIES), "Missing exact automatic-agent/Run-enable audit proof")
    return {"path": str(AUDIT), "sha256": file_sha(AUDIT), "eventCount": 11, "actor": MANAGER,
            "enableServiceStartUtc": START, "enableServiceEndUtc": END, "removedProjectEdges": 0,
            "enableServiceEventCount": 3, "enableServiceOperationId": OPERATION,
            "enableServiceOperationProducer": "serviceusage.googleapis.com",
            "enableServiceEntries": [{"timestamp": t, "insertId": iid, "first": first, "last": not first} for (t, iid), first in ENABLE_ENTRIES.items()],
            "addedProjectEdges": [{"role": r, "member": member, "condition": None, "observedAtUtc": t} for (r, member, _), t in EXPECTED.items()]}


def verify_after(m, original_raw, prior_values, policies, identities, image):
    post = STATE.read_bytes(); raw = raw_state(post, 13); values = state_values(STATE)
    require(raw["lineage"] == original_raw["lineage"] and raw["serial"] > original_raw["serial"], "Post-state lineage/serial differs")
    require(set(values) == set(prior_values) | GATE.RUNTIME_ADDITIONS and all(values[a] == v for a, v in prior_values.items())
            and GATE.runtime_is_exact(values, image), "Exact thirteen state resources or unchanged prior nine differ")
    after = m.private_policies(); save("post-iam-private.json", after)
    expected = set(EXPECTED)
    require(set(after) == set(policies), "Project ancestry/policy scope changed")
    for key, old in policies.items():
        new = after[key]
        require(meta(old) == meta(new), "IAM metadata changed")
        if key == "project":
            require(not (edges(old) - edges(new)) and edges(new) - edges(old) == expected, "Unexpected project IAM delta")
        else:
            require(edges(old) == edges(new), "Repository/ancestor IAM changed")
        require(not any(v == "serviceAccount:" + RUNTIME for _, v, _ in edges(new)), "Runtime service account received an assigned role")
    current = identity_and_keys(m, after=True)
    save("post-identity-private.json", current)
    require(current["pool"] == identities["pool"] and current["provider"] == identities["provider"]
            and edges(current["grant"]) == edges(identities["grant"]) and meta(current["grant"]) == meta(identities["grant"]), "Existing WIF/grant changed")
    runtime = m.cloud("iam", "service-accounts", "describe", RUNTIME, "--project=" + PROJECT)
    require(runtime.get("email") == RUNTIME and runtime.get("disabled", False) is False, "Runtime service account differs")
    require(not edges(m.cloud("iam", "service-accounts", "get-iam-policy", RUNTIME, "--project=" + PROJECT)), "Unexpected runtime account IAM grant")
    run = live_run(m, image)
    services = m.cloud("services", "list", "--enabled", "--project=" + PROJECT)
    enabled = {s.get("config", {}).get("name") for s in services if s.get("state") == "ENABLED"}
    require({"run.googleapis.com", "artifactregistry.googleapis.com"} <= enabled and not
            enabled.intersection({"containerscanning.googleapis.com", "ondemandscanning.googleapis.com"}), "Run/registry/scanning API state differs")
    clean_source(m); require(STATE.read_bytes() == post, "State changed during post-verification")
    return {"stateSHA256": digest(post), "lineage": raw["lineage"], "serial": raw["serial"], "managedResources": 13,
            "iamAfter": after, "identityAfter": current, "runtimeAccount": runtime, "run": run}


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--verify", action="store_true"); args = parser.parse_args()
    if not args.verify:
        print(json.dumps({"status": "dry-run", "cloudInvoked": False, "applyExecuted": False, "result": str(RESULT)})); return 0
    require(FROZEN1.is_file() and not FROZEN1.is_symlink() and file_sha(FROZEN1) == FROZEN1_SHA, "Frozen audit1 changed")
    import importlib.util
    spec = importlib.util.spec_from_file_location("frozen_audit1", FROZEN1); old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
    require(old.RESULT == AUDIT1 and old.ORIGINAL == ORIGINAL, "Frozen audit1 scope differs")
    old.RESULT = RESULT
    a, m, pre, old_raw, prior_values, image, post, hashes = old.preflight()
    require(file_sha(a.STATE) == STATE_SHA, "Observed post-apply state SHA differs")
    failed = m.local_json(AUDIT1 / "summary.json")
    require(failed.get("status") == "blocked" and failed.get("errorType") == "RuntimeError" and failed.get("error") == "Unexpected project IAM delta"
            and stamp(failed["observedAtUtc"]) == stamp("2026-10-23T23:12:48.957026+00:00") and failed.get("applyExecuted") is False, "Original audit1 failure differs")
    proof = audit_proof(m)
    hashes.update({FROZEN1: file_sha(FROZEN1), AUDIT: proof["sha256"]})
    RESULT.mkdir(mode=0o700); a.RESULT = RESULT
    for name in ("STATE", "raw_state", "state_values", "GATE", "save", "edges", "meta", "identity_and_keys", "RUNTIME", "live_run", "clean_source", "digest"):
        globals()[name] = getattr(a, name)
    a.save("original-evidence-sha256-private.json", {str(p): value for p, value in hashes.items()})
    a.save("automatic-agent-audit-proof-private.json", proof)
    summary = {"status": "blocked", "project": PROJECT, "projectNumber": NUMBER, "sourceRevision": old.HEAD,
        "savedPlanSHA256": old.PLAN_SHA, "imageUri": image, "originalApplyExitCode": 0, "originalApplySummaryPreserved": True,
        "applyExecuted": False, "stateModified": False, "iamModified": False, "apisModified": False,
        "authenticatedInvocationAttempted": False, "awsActivated": False, "normalization": "exact canonical IAM grant.name on deep copy only",
        "auditProof": proof, "autoGrantScopeVariance": {"previousExpectedProjectAdditions": 1, "observedProjectAdditions": 3,
            "additionalGoogleManagedAgents": [e["member"] for e in proof["addedProjectEdges"] if e["role"] != "roles/run.serviceAgent"],
            "newGrantPerformedByVerifier": False, "notIndividuallyListedInOriginalApproval": True}}
    try:
        detail = verify_after(m, old_raw, prior_values, pre["iamBefore"], pre["identityBefore"], image)
        detail["auditProof"] = proof; detail["autoGrantScopeVariance"] = summary["autoGrantScopeVariance"]
        a.save("post-verification-private.json", detail)
        require(a.STATE.read_bytes() == post and all(p.is_file() and not p.is_symlink() and file_sha(p) == h for p, h in hashes.items()), "Original state/evidence changed during read-only verification")
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
