"""Read-only audit of the one completed 988d... apply; default is inert.

--verify retains the original blocked B4 summary and every original artifact.
Only on a deep copy, the exact canonical service IAM resource name is converted
to the short configured name for B4's frozen strict state predicate. Provider
7.46.1 intentionally canonicalizes that field (iam_cloud_run_v2_service.go).
All other B4 state/IAM/WIF/key/configuration/readiness checks remain in force.
No apply, plan, refresh, IAM/API write, state write, HTTP request, token fetch,
AWS activation, patch or retry is provided. Unknown metadata shapes block.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
BASE = Path.home() / "ecoguard-c-personal-20261023"
FROZEN = BASE / "frozen-apply-private-inference-20261024-1.py"
FROZEN_SHA = "b4b3a00db6c849e4b154c93975df86c88454c78d101207f03ce693f249130c99"
ROOT = BASE / "source/infra/gcp/environments/personal"
PLAN = ROOT / "private/private-inference-plan-20261024-2"
ORIGINAL = PLAN / "apply-20261024-1"
RESULT = ORIGINAL / "read-only-verification-20261024-1"
HEAD = "3dd63c805b625fb3b378ac977d51c6959d599f0c"
PLAN_SHA = "988d8f63902c705443d70d53b03ebc30440b281f8445d6f78b443e24f64ec518"
PROJECT, NUMBER = "ecoguard-fit3184-a2-2026", "995070689587"
CANONICAL = f"projects/{PROJECT}/locations/us-central1/services/ecoguard-inference"
ORIGINAL_TIME = datetime.fromisoformat("2026-10-23T23:07:53.566104+00:00")


def require(ok, reason):
    if not ok: raise RuntimeError(reason)


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name, path, expected=None):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size < 1024**2, "Frozen/local helper missing or unbounded")
    if expected: require(sha(path) == expected, "Frozen helper SHA differs")
    spec = importlib.util.spec_from_file_location(name, path); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class ExactCanonicalNameProxy:
    def __init__(self, gate): self.gate = gate
    def __getattr__(self, name): return getattr(self.gate, name)
    def runtime_is_exact(self, values, image):
        address = self.gate.MODULE + self.gate.INVOKER
        require(values.get(address, {}).get("name") == CANONICAL, "Grant name is not the sole exact canonical service")
        normalized = copy.deepcopy(values)
        normalized[address]["name"] = "ecoguard-inference"
        return self.gate.runtime_is_exact(normalized, image)


def preflight():
    require(sys.platform == "linux" and os.environ.get("CLOUD_SHELL") == "true", "Existing Google CloudShell required")
    require(not RESULT.exists() and not RESULT.is_symlink(), "Read-only audit result exists; no overwrite")
    for key, value in os.environ.items():
        require(not (value and (key.startswith(("TF_CLI_ARGS", "TF_VAR_")) or key in ("TF_WORKSPACE", "TF_LOG", "TF_LOG_PATH", "TF_CLI_CONFIG_FILE", "TF_REATTACH_PROVIDERS"))), "Terraform environment override")
    for key in ("GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_OAUTH_ACCESS_TOKEN", "GOOGLE_CREDENTIALS", "GOOGLE_IMPERSONATE_SERVICE_ACCOUNT", "GOOGLE_IMPERSONATE_SERVICE_ACCOUNT_DELEGATES", "GOOGLE_CLOUD_KEYFILE_JSON", "GCLOUD_KEYFILE_JSON", "CLOUDSDK_AUTH_ACCESS_TOKEN", "CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT", "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE"):
        require(not os.environ.get(key), "Credential override")
    require(not (Path.home() / ".terraformrc").exists(), "Unreviewed Terraform CLI configuration")
    a = load("frozen_apply_B4", FROZEN, FROZEN_SHA)
    require(a.HEAD == HEAD and a.PLAN == PLAN and a.RESULT == ORIGINAL and a.PROJECT == PROJECT and a.NUMBER == NUMBER, "Frozen B4 scope differs")
    m = load("frozen_publisher", a.FROZEN, a.FROZEN_SHA)
    a.clean_source(m)
    require(a.read(["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"]) == m.OPERATOR
            and a.read(["gcloud", "config", "get-value", "project"]) == PROJECT, "Active operator/project differs")
    for setting in ("auth/impersonate_service_account", "auth/credential_file_override"):
        require(a.read(["gcloud", "config", "get-value", setting]) in ("", "(unset)"), "Configured credential override")
    project = m.cloud("projects", "describe", PROJECT)
    require(project.get("projectId") == PROJECT and str(project.get("projectNumber")) == NUMBER and project.get("lifecycleState") == "ACTIVE", "Live project differs")
    require(a.read(["git", "-C", m.SOURCE, "hash-object", ROOT / ".terraform.lock.hcl"]) == a.read(["git", "-C", m.SOURCE, "rev-parse", HEAD + ":infra/gcp/environments/personal/.terraform.lock.hcl"]), "Provider lock differs")
    version = json.loads(a.read([a.TF, "-chdir=" + str(ROOT), "version", "-json"]))
    backend = json.loads((a.DATA / "terraform.tfstate").read_text())["backend"]
    require(version.get("terraform_version") == "1.17.0" and version.get("provider_selections") == {"registry.terraform.io/hashicorp/google": "7.46.1"}
            and backend.get("type") == "local" and backend["config"]["path"] == "state/terraform.tfstate"
            and a.read([a.TF, "-chdir=" + str(ROOT), "workspace", "show"]) == "default", "Tool/provider/backend/workspace differs")
    gate = load("frozen_increment_gate", ROOT / "check_runtime_plan.py")
    original = m.local_json(ORIGINAL / "summary.json"); pre = m.local_json(ORIGINAL / "preflight-private.json")
    fixed = {"status": "blocked", "sourceRevision": HEAD, "project": PROJECT, "projectNumber": NUMBER,
        "savedPlanSHA256": PLAN_SHA, "applyExecuted": True, "applyExitCode": 0, "configurationVerified": False,
        "retryAttempted": False, "authenticatedInvocationAttempted": False, "awsActivated": False,
        "verificationErrorType": "RuntimeError", "verificationError": "Exact thirteen state resources or unchanged prior nine differ"}
    require(all(type(original.get(k)) is type(v) and original[k] == v for k, v in fixed.items())
            and datetime.fromisoformat(original["observedAtUtc"].replace("Z", "+00:00")) == ORIGINAL_TIME
            and not original.get("processOutcomeUncertain"), "Original result is not the exact completed apply/known verifier failure")
    image = m.IMAGE + "@" + m.OCI_DIGEST
    require(original.get("imageUri") == image and pre.get("sourceRevision") == HEAD and pre.get("imageUri") == image
            and pre.get("savedPlanSHA256") == PLAN_SHA and sha(a.BINARY) == PLAN_SHA
            and sha(a.PUBLICATION) == pre.get("publicationEvidenceSHA256"), "Original plan/publication binding differs")
    approval = m.local_json(PLAN / "apply-approval.json")
    require(approval == pre.get("approval") and approval.get("approved") is True
            and approval.get("approvedScope") == "private-inference-four-create-with-google-run-service-agent"
            and approval.get("savedPlanSHA256") == PLAN_SHA and approval.get("sourceRevision") == HEAD
            and approval.get("project") == PROJECT and approval.get("projectNumber") == NUMBER and approval.get("imageUri") == image
            and approval.get("publicationEvidenceSHA256") == pre["publicationEvidenceSHA256"]
            and isinstance(approval.get("approvalReference"), str) and approval["approvalReference"].strip(), "Actual recorded approval differs")
    publication = m.local_json(a.PUBLICATION)
    require(publication.get("status") == "private-inference-image-published-and-verified" and publication.get("imageUri") == image
            and publication.get("configDigest") == m.CONFIG_DIGEST and publication.get("remoteManifestAndConfigBytesMatch") is True, "Actual publication evidence differs")
    document = json.loads(a.read([a.TF, "-chdir=" + str(ROOT), "show", "-json", a.BINARY]))
    report = gate.inspect_plan(document, "private-inference", image)
    require(report["status"] == "offline-increment-plan-passed" and len(report["checks"]) == 13 and all(c["passed"] for c in report["checks"]), "Frozen actual saved-plan gate no longer passes")
    before_path = ORIGINAL / "state-before-private-backup.json"; before = before_path.read_bytes()
    require(sha(before_path) == pre.get("stateSHA256") and before == (PLAN / "state-before-private-backup.json").read_bytes(), "Original nine-state checkpoint differs")
    a.GATE = ExactCanonicalNameProxy(gate)
    old_raw = a.raw_state(before, 9); prior_values = a.state_values(before_path)
    require(set(prior_values) == gate.IDENTITY.expected_addresses() | gate.REGISTRY_ADDITIONS, "Prior state is not exact nine")
    post = a.STATE.read_bytes(); a.raw_state(post, 13)
    require(post == (ORIGINAL / "post-state-immediate.tfstate").read_bytes() == (ORIGINAL / "post-state-final.tfstate").read_bytes(), "Current thirteen state differs from retained original post-state")
    require(a.GATE.runtime_is_exact(a.state_values(a.STATE), image), "Canonical name normalization did not satisfy all frozen runtime conditions")
    files = [p for p in ORIGINAL.rglob("*") if p.is_file()] + [a.STATE, a.BINARY, a.PUBLICATION, PLAN / "apply-approval.json", PLAN / "state-before-private-backup.json", PLAN / "apply-started.json", FROZEN, a.FROZEN]
    require(all(not p.is_symlink() for p in files), "Original evidence contains a symlink")
    hashes = {p: sha(p) for p in files}
    return a, m, pre, old_raw, prior_values, image, post, hashes


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--verify", action="store_true"); args = parser.parse_args()
    if not args.verify:
        print(json.dumps({"status": "dry-run", "cloudInvoked": False, "applyExecuted": False, "result": str(RESULT), "savedPlanSHA256": PLAN_SHA})); return 0
    a, m, pre, old_raw, prior_values, image, post, hashes = preflight()
    RESULT.mkdir(mode=0o700); a.RESULT = RESULT
    a.save("original-evidence-sha256-private.json", {str(p): value for p, value in hashes.items()})
    summary = {"status": "blocked", "project": PROJECT, "projectNumber": NUMBER, "sourceRevision": HEAD,
        "savedPlanSHA256": PLAN_SHA, "imageUri": image, "originalApplyExitCode": 0, "originalApplySummaryPreserved": True,
        "applyExecuted": False, "stateModified": False, "iamModified": False, "apisModified": False,
        "authenticatedInvocationAttempted": False, "awsActivated": False, "normalization": "exact canonical IAM grant.name on deep copy only"}
    try:
        detail = a.verify_after(m, old_raw, prior_values, pre["iamBefore"], pre["identityBefore"], image)
        a.save("post-verification-private.json", detail)
        require(a.STATE.read_bytes() == post and all(p.is_file() and not p.is_symlink() and sha(p) == h for p, h in hashes.items()), "Original state/evidence changed during read-only verification")
        summary.update(status="private-run-configuration-readonly-verification-passed", configurationVerified=True, managedResources=13,
            stateSHA256=sha(a.STATE), userManagedKeyCount=0, url=detail["run"]["url"], readyRevision=detail["run"]["readyRevision"],
            originalEvidenceUnchanged=True, cloudInferenceVerified=False, crossCloudVerified=False)
    except Exception as error:
        summary.update(configurationVerified=False, errorType=type(error).__name__, error=str(error) if isinstance(error, RuntimeError) else "Inspect new private evidence; no mutation or retry")
    finally:
        try: (RESULT / "post-state-private-backup.tfstate").write_bytes(a.STATE.read_bytes())
        except Exception as error: summary["status"] = "blocked"; summary["stateCaptureErrorType"] = type(error).__name__
        summary["observedAtUtc"] = datetime.now(timezone.utc).isoformat(); a.save("summary.json", summary)
        print(json.dumps(summary, separators=(",", ":")), flush=True)
    return 0 if summary["status"] == "private-run-configuration-readonly-verification-passed" else 1


if __name__ == "__main__":
    os.umask(0o077)
    try: raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"status": "blocked", "applyExecuted": False, "errorType": type(error).__name__, "error": str(error) if isinstance(error, RuntimeError) else "Invalid/incomplete frozen evidence"})); raise SystemExit(1)
