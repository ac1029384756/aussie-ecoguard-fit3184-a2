"""Prepare exactly three approved private Cloud Run HTTP checks; default is inert.

--verify requires the completed matching deployment, its original NEW approval
with approvedBoundedHttpTests=true, fresh existing credit evidence and frozen
helpers. The exact retained failed postchecks require a separate successful
read-only audit; their original summaries are never rewritten. One anonymous
health check, one user-authenticated health check and one
authenticated warmup are allowed, without retries. No IAM/API/AWS changes, keys,
impersonation, persistent tokens, deployments or inference-media requests occur.
Startup readiness is distinct from the warmup's model downloads/loading.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import ssl
import subprocess
import sys
import time
from urllib.parse import urlsplit

sys.dont_write_bytecode = True
BASE = Path.home() / "ecoguard-c-personal-20261023"
SOURCE = BASE / "source"
ROOT = SOURCE / "infra/gcp/environments/personal"
PLAN = ROOT / "private/private-inference-plan-20261024-2"
APPLY = PLAN / "apply-20261024-1"
STATE = ROOT / "state/terraform.tfstate"
RESULT = BASE / "private-inference-http-20261024-1"
FROZEN_APPLY = BASE / "frozen-apply-private-inference-20261024-1.py"
FROZEN_APPLY_SHA = "b4b3a00db6c849e4b154c93975df86c88454c78d101207f03ce693f249130c99"
FROZEN_PUBLISH = BASE / "frozen-publish-inference-20261024-1.py"
FROZEN_PUBLISH_SHA = "f180a9ac01473e468bca17c6a4a1a8f5154422bfafb6b986f9a469b48444b462"
READ_ONLY_AUDIT = APPLY / "read-only-verification-20261024-3"
FROZEN_READ_ONLY = BASE / "frozen-verify-private-run-after-apply-20261024-3.py"
FROZEN_READ_ONLY_SHA = "db43e6c1bd0e14246dd0fe0a11e6cda6a89157a66774fc26c809d6c8141fdddb"
READ_ONLY_PLAN_SHA = "988d8f63902c705443d70d53b03ebc30440b281f8445d6f78b443e24f64ec518"
HEAD = "3dd63c805b625fb3b378ac977d51c6959d599f0c"
PROJECT, NUMBER, OPERATOR = "ecoguard-fit3184-a2-2026", "995070689587", "hoshigahoshii@163.com"
IMAGE = ("us-central1-docker.pkg.dev/" + PROJECT + "/ecoguard/inference@"
         "sha256:7e481399309c8a90276c864e9765545657e44c00e9061ee668b4e56db4f22fdb")
MANIFEST_SHA = "639595e1e9ffe18cb11ead1c7480ffe7a31bf767f6cbaf6b8375829227a569ae"
MANIFEST_VERSION = "ecoguard-models-2026-10-08-v3"
ENV = {**os.environ, "CLOUDSDK_CORE_DISABLE_PROMPTS": "1", "CLOUDSDK_CORE_LOG_HTTP": "false",
       "PYTHONDONTWRITEBYTECODE": "1"}


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(argv):
    result = subprocess.run([str(v) for v in argv], env=ENV, stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=60, shell=False)
    require(result.returncode == 0, "A read-only metadata/source check failed")
    return result.stdout.strip()


def load_frozen(name, path, expected):
    require(re.fullmatch(r"[0-9a-f]{64}", expected) and path.is_file() and not path.is_symlink()
            and sha(path) == expected, "Final frozen helper is missing or changed: " + name)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def source_check():
    require(read(["git", "-C", SOURCE, "rev-parse", "HEAD"]) == HEAD
            and not read(["git", "-C", SOURCE, "status", "--porcelain", "--untracked-files=no"]),
            "State-owning release source differs")


def save(name, value):
    with (RESULT / name).open("x") as output:
        json.dump(value, output, indent=2); output.write("\n")


def exact_fields(record, fields):
    return all(type(record.get(key)) is type(value) and record[key] == value for key, value in fields.items())


def deployment_evidence(a, m):
    """Bind the exact retained apply/postcheck failures to successful audit3.

    Only the pinned audit's local proof predicates are called here. Its main,
    preflight, apply and verification entrypoints are never called.
    """
    original = m.local_json(APPLY / "summary.json")
    failed = {"status": "blocked", "project": PROJECT, "projectNumber": NUMBER, "sourceRevision": HEAD,
        "savedPlanSHA256": READ_ONLY_PLAN_SHA, "imageUri": IMAGE, "applyExecuted": True,
        "applyExitCode": 0, "configurationVerified": False, "retryAttempted": False,
        "authenticatedInvocationAttempted": False, "awsActivated": False,
        "verificationErrorType": "RuntimeError",
        "verificationError": "Exact thirteen state resources or unchanged prior nine differ"}
    require(exact_fields(original, failed) and not original.get("processOutcomeUncertain")
            and original.get("observedAtUtc") == "2026-10-23T23:07:53.566104+00:00",
            "Original apply is not the exact preserved successful apply/failed postcheck")
    for attempt, reason, stamp in (
            (1, "Unexpected project IAM delta", "2026-10-23T23:12:48.957026+00:00"),
            (2, "Unexpected/missing/disabled project service account", "2026-10-23T23:20:39.220938+00:00")):
        previous = m.local_json(APPLY / f"read-only-verification-20261024-{attempt}" / "summary.json")
        require(exact_fields(previous, {"status": "blocked", "project": PROJECT, "projectNumber": NUMBER,
                    "sourceRevision": HEAD, "savedPlanSHA256": READ_ONLY_PLAN_SHA, "imageUri": IMAGE,
                    "applyExecuted": False, "configurationVerified": False, "errorType": "RuntimeError",
                    "error": reason, "observedAtUtc": stamp}), "A retained failed read-only audit differs")
    audit = load_frozen("frozen_http_readonly_audit3", FROZEN_READ_ONLY, FROZEN_READ_ONLY_SHA)
    require(audit.RESULT == READ_ONLY_AUDIT and audit.ORIGINAL == APPLY and audit.ROOT == ROOT
            and audit.PROJECT == PROJECT and audit.NUMBER == NUMBER
            and audit.DEFAULT == NUMBER + "-compute@developer.gserviceaccount.com", "Frozen read-only audit scope differs")
    summary_path, detail_path = READ_ONLY_AUDIT / "summary.json", READ_ONLY_AUDIT / "post-verification-private.json"
    summary, detail = m.local_json(summary_path), m.local_json(detail_path)
    passed = {"status": "private-run-configuration-readonly-verification-passed", "project": PROJECT,
        "projectNumber": NUMBER, "sourceRevision": HEAD, "savedPlanSHA256": READ_ONLY_PLAN_SHA,
        "imageUri": IMAGE, "originalApplyExitCode": 0, "originalApplySummaryPreserved": True,
        "applyExecuted": False, "stateModified": False, "iamModified": False, "apisModified": False,
        "authenticatedInvocationAttempted": False, "awsActivated": False,
        "normalization": "exact canonical IAM grant.name on deep copy only", "configurationVerified": True,
        "managedResources": 13, "userManagedKeyCount": 0, "originalEvidenceUnchanged": True,
        "cloudInferenceVerified": False, "crossCloudVerified": False}
    require(exact_fields(summary, passed), "The exact new read-only configuration audit has not passed")
    require(summary.get("stateSHA256") == detail.get("stateSHA256") == audit.STATE_SHA == sha(STATE)
            and summary.get("readyRevision") == detail.get("run", {}).get("readyRevision"),
            "Read-only state/revision attestation differs")
    proof_fields = audit.http_local_proofs(m)
    require(isinstance(proof_fields, dict) and set(proof_fields) == {"auditProof", "defaultComputeCreationProof"},
            "Pinned read-only local proof interface differs")
    for key, value in proof_fields.items():
        require(json.dumps(summary.get(key), sort_keys=True) == json.dumps(value, sort_keys=True)
                and json.dumps(detail.get(key), sort_keys=True) == json.dumps(value, sort_keys=True),
                "Retained automatic-agent/default-account proof differs")
    for key, filename in (("auditProof", "automatic-agent-audit-proof-private.json"),
                          ("defaultComputeCreationProof", "default-compute-creation-proof-private.json")):
        require(m.local_json(READ_ONLY_AUDIT / filename) == proof_fields[key], "Retained local proof capture differs")
    variances = {
        "autoGrantScopeVariance": {"previousExpectedProjectAdditions": 1, "observedProjectAdditions": 3,
            "additionalGoogleManagedAgents": [edge["member"] for edge in proof_fields["auditProof"]["addedProjectEdges"]
                                               if edge["role"] != "roles/run.serviceAgent"],
            "newGrantPerformedByVerifier": False, "notIndividuallyListedInOriginalApproval": True},
        "inventoryVariance": {"additionalAccount": audit.DEFAULT, "assignedRoleCount": 0, "ownIamBindingCount": 0,
            "userManagedKeyCount": 0, "creationActorIdentified": False, "createdByVerifier": False}}
    for key, value in variances.items():
        require(json.dumps(summary.get(key), sort_keys=True) == json.dumps(value, sort_keys=True)
                and json.dumps(detail.get(key), sort_keys=True) == json.dumps(value, sort_keys=True),
                "Reported automatic-agent/default-account scope variance differs")
    dependencies = set(audit.http_evidence_paths())
    require(all(isinstance(path, Path) and path.is_absolute() and path.resolve().is_relative_to(BASE.resolve())
                and not path.resolve().is_relative_to(READ_ONLY_AUDIT.resolve()) for path in dependencies),
            "Read-only proof dependency escaped the fixed task scope")
    originals = {path for path in APPLY.rglob("*") if path.is_file() and not path.is_relative_to(READ_ONLY_AUDIT)}
    originals |= {STATE, a.BINARY, a.PUBLICATION, PLAN / "apply-approval.json", PLAN / "state-before-private-backup.json",
                  PLAN / "apply-started.json", FROZEN_APPLY, FROZEN_PUBLISH} | dependencies
    manifest_path = READ_ONLY_AUDIT / "original-evidence-sha256-private.json"
    preserved = m.local_json(manifest_path)
    require(isinstance(preserved, dict) and set(preserved) == {str(path) for path in originals},
            "Original-evidence manifest is not the complete fixed path set")
    require(all(path.is_file() and not path.is_symlink()
                and isinstance(preserved[str(path)], str) and re.fullmatch(r"[0-9a-f]{64}", preserved[str(path)])
                and sha(path) == preserved[str(path)] for path in originals), "Original evidence hash chain changed")
    captured_state = READ_ONLY_AUDIT / "post-state-private-backup.tfstate"
    require(captured_state.is_file() and not captured_state.is_symlink() and sha(captured_state) == sha(STATE),
            "Read-only post-state capture differs")
    audit_files = {path for path in READ_ONLY_AUDIT.rglob("*") if path.is_file()}
    require(all(not path.is_symlink() for path in audit_files), "Read-only audit evidence is symlinked")
    # This exact independently callable reader includes all three real accounts;
    # do not sanitize the inventory or fall back to B4's superseded allowlist.
    a.HTTP_IDENTITY_READER = lambda reader_m, after=True: audit.http_identity_and_keys(a, reader_m, after=after)
    return summary, detail_path, originals | audit_files | {FROZEN_READ_ONLY}


def local_inputs(a, m):
    require(a.HEAD == HEAD and a.PLAN == PLAN and a.RESULT == APPLY and a.STATE == STATE
            and a.PROJECT == PROJECT and a.NUMBER == NUMBER, "Frozen apply helper scope differs")
    summary, detail_path, evidence_files = deployment_evidence(a, m)
    pre = m.local_json(APPLY / "preflight-private.json")
    detail = m.local_json(detail_path)
    publication_sha, plan_sha = pre.get("publicationEvidenceSHA256"), summary.get("savedPlanSHA256")
    require(all(isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v) for v in (publication_sha, plan_sha))
            and pre.get("sourceRevision") == HEAD and pre.get("imageUri") == IMAGE
            and pre.get("savedPlanSHA256") == plan_sha and sha(a.PUBLICATION) == publication_sha
            and sha(a.BINARY) == plan_sha, "Actual deployment/plan/publication binding differs")
    publication = m.local_json(a.PUBLICATION)
    require(publication.get("status") == "private-inference-image-published-and-verified"
            and publication.get("imageUri") == IMAGE and publication.get("configDigest") == m.CONFIG_DIGEST,
            "Actual verified publication differs")
    require(STATE.is_file() and not STATE.is_symlink() and sha(STATE) == detail.get("stateSHA256")
            and detail.get("managedResources") == 13, "Verified thirteen-resource state changed")
    raw = a.raw_state(STATE.read_bytes(), 13)
    require(raw["lineage"] == detail.get("lineage") and raw["serial"] == detail.get("serial"),
            "Verified deployment lineage/serial differs")
    url = detail.get("run", {}).get("url")
    require(isinstance(url, str) and url == summary.get("url")
            and url == detail.get("run", {}).get("service", {}).get("status", {}).get("url"),
            "Verified Ready URL evidence differs")
    parsed = urlsplit(url)
    require(parsed.scheme == "https" and parsed.hostname and parsed.hostname.endswith(".run.app")
            and not parsed.username and not parsed.password and parsed.port is None
            and parsed.path in ("", "/") and not parsed.query and not parsed.fragment,
            "Verified service URL is not an exact HTTPS run.app origin")
    manifest_path = SOURCE / "config/model.locked.json"
    require(sha(manifest_path) == MANIFEST_SHA, "Locked source manifest differs")
    manifest = m.local_json(manifest_path)
    require(manifest.get("manifestVersion") == MANIFEST_VERSION, "Locked manifest version differs")
    feature = (manifest["embedding"]["featureVersion"] + ":" + manifest["embedding"]["revision"]
               + ":" + manifest["preprocessingVersion"])
    record = a.approval_record(m, plan_sha, IMAGE, publication_sha)
    require(record.get("approvedBoundedHttpTests") is True, "Actual new approval excludes these bounded HTTP tests")
    files = {APPLY / "summary.json", APPLY / "preflight-private.json", detail_path,
             PLAN / "apply-approval.json", a.BINARY, a.PUBLICATION, STATE} | evidence_files
    require(all(p.is_file() and not p.is_symlink() for p in files), "Evidence is missing or symlinked")
    return detail, url, feature, plan_sha, publication_sha, {p: sha(p) for p in files}


def stable_files(files):
    source_check()
    require(all(sha(p) == value for p, value in files.items()), "Source/state/approval/plan/publication evidence changed")


def live_metadata(a, m, detail, url, directory):
    directory.mkdir(mode=0o700)
    a.RESULT = directory
    run = a.live_run(m, IMAGE)
    require(run["url"] == url and run["readyRevision"] == detail["run"]["readyRevision"],
            "Ready service URL/revision changed")
    policies = m.private_policies()
    require(policies == detail["iamAfter"], "Project/repository/ancestor IAM changed after deployment")
    identity = getattr(a, "HTTP_IDENTITY_READER", a.identity_and_keys)(m, after=True)
    require(identity == detail["identityAfter"], "WIF/identities/keys changed after deployment")
    require(not a.edges(m.cloud("iam", "service-accounts", "get-iam-policy", a.RUNTIME,
            "--project=" + PROJECT)), "Runtime service-account grant changed")


def request_once(host, method, path, timeout, records, token=None):
    expected = [("GET", "/healthz", False), ("GET", "/healthz", True), ("POST", "/v1/warmup", True)]
    require(len(records) < 3 and (method, path, token is not None) == expected[len(records)],
            "HTTP check sequence/count differs; no further request allowed")
    record = {"method": method, "path": path, "authenticated": token is not None,
              "clientTimeoutSeconds": timeout, "attempt": len(records) + 1}
    records.append(record)
    start = time.monotonic()
    connection = http.client.HTTPSConnection(host, timeout=timeout, context=ssl.create_default_context())
    headers = {"Accept": "application/json", "User-Agent": "ecoguard-bounded-private-check/1"}
    if token is not None:
        headers["X-Serverless-Authorization"] = "Bearer " + token
    body = b"{}" if method == "POST" else None
    if body is not None:
        headers["Content-Type"] = "application/json"
    require(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), "Unreviewed process timer exists")
    def deadline_expired(signum, frame):
        raise TimeoutError("Bounded HTTP wall-time deadline exceeded")
    previous_handler = signal.signal(signal.SIGALRM, deadline_expired)
    signal.setitimer(signal.ITIMER_REAL, timeout)
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        record["httpStatus"] = response.status
        raw = response.read(65537)
        require(len(raw) <= 65536, "HTTP response exceeded the bounded diagnostic limit")
        record["responseBytes"] = len(raw)
        # No raw response, headers, token or exception URL is written or printed.
        if token is None:
            return response.status, None
        require(response.status == 200, "Authenticated HTTP check failed; stop without IAM changes or retries")
        value = json.loads(raw)
        require(isinstance(value, dict), "Authenticated response schema differs")
        return response.status, value
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        record["elapsedSeconds"] = round(time.monotonic() - start, 3)
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Use actual bundled approval once for exactly three requests")
    args = parser.parse_args()
    if not args.verify:
        print(json.dumps({"status": "dry-run", "cloudInvoked": False, "httpInvoked": False,
            "requiredSourceRevision": HEAD, "requiresNewActualApproval": True,
            "requiresApprovedBoundedHttpTests": True, "expectedHTTPRequests": 3,
            "requests": ["anonymous GET /healthz", "operator-authenticated GET /healthz",
                         "operator-authenticated POST /v1/warmup {}"], "automaticRetry": False,
            "tokenPersistence": False, "iamChanges": False, "awsActivation": False})); return 0
    require(sys.platform == "linux" and os.environ.get("CLOUD_SHELL") == "true", "Existing Google CloudShell required")
    require(not RESULT.exists() and not RESULT.is_symlink(), "HTTP verification attempt exists; no retry")
    for key in ("GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_OAUTH_ACCESS_TOKEN", "GOOGLE_CREDENTIALS",
                "GOOGLE_IMPERSONATE_SERVICE_ACCOUNT", "GOOGLE_IMPERSONATE_SERVICE_ACCOUNT_DELEGATES",
                "GOOGLE_CLOUD_KEYFILE_JSON", "GCLOUD_KEYFILE_JSON", "CLOUDSDK_AUTH_ACCESS_TOKEN",
                "CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT", "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE"):
        require(not os.environ.get(key), "Unreviewed credential override: " + key)
    source_check()
    m = load_frozen("frozen_http_publisher", FROZEN_PUBLISH, FROZEN_PUBLISH_SHA); m.ENV = ENV
    a = load_frozen("frozen_http_apply", FROZEN_APPLY, FROZEN_APPLY_SHA)
    require(read(["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"]) == OPERATOR
            and read(["gcloud", "config", "get-value", "project"]) == PROJECT, "Existing operator/project differs")
    for setting in ("auth/impersonate_service_account", "auth/credential_file_override"):
        require(read(["gcloud", "config", "get-value", setting]) in ("", "(unset)"), "Configured credential override")
    project = m.cloud("projects", "describe", PROJECT)
    require(project.get("projectId") == PROJECT and str(project.get("projectNumber")) == NUMBER
            and project.get("lifecycleState") == "ACTIVE", "Canonical project differs")
    gate_spec = importlib.util.spec_from_file_location("frozen_http_gate", ROOT / "check_runtime_plan.py")
    gate = importlib.util.module_from_spec(gate_spec); gate_spec.loader.exec_module(gate); a.GATE = gate
    detail, url, feature, plan_sha, publication_sha, files = local_inputs(a, m)
    os.umask(0o077); RESULT.mkdir(mode=0o700)
    summary = {"status": "blocked", "project": PROJECT, "sourceRevision": HEAD, "imageUri": IMAGE,
        "savedPlanSHA256": plan_sha, "publicationEvidenceSHA256": publication_sha,
        "httpRequests": [], "automaticRetry": False, "tokenPersisted": False, "iamModified": False,
        "apisModified": False, "awsActivated": False, "cloudInferenceVerified": False,
        "crossCloudVerified": False, "warmupAttempted": False}
    token = None
    try:
        save("attempt-started.json", {"startedAtUtc": datetime.now(timezone.utc).isoformat(),
            "maximumHTTPRequests": 3, "retryPermitted": False})
        live_metadata(a, m, detail, url, RESULT / "before-read-only")
        stable_files(files)
        host = urlsplit(url).hostname
        status, _ = request_once(host, "GET", "/healthz", 60, summary["httpRequests"])
        require(status in (401, 403), "Anonymous access was not denied; stop before authenticated checks")
        result = subprocess.run(["gcloud", "auth", "print-identity-token", "--account=" + OPERATOR, "--quiet"],
            env=ENV, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30, shell=False)
        require(result.returncode == 0, "Existing user ID-token acquisition failed; no impersonation or new grants")
        token = result.stdout.strip()
        require(32 < len(token) < 20000 and re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", token),
                "User ID-token response schema differs")
        del result
        _, health = request_once(host, "GET", "/healthz", 60, summary["httpRequests"], token)
        models = health.get("models", {})
        require(health.get("status") == "alive" and health.get("schemaVersion") == "1"
                and models.get("configured") is True and models.get("manifestVersion") == MANIFEST_VERSION,
                "Authenticated health is not the configured locked-model service")
        summary["httpRequests"][-1]["models"] = {"configured": True, "manifestVersion": MANIFEST_VERSION}
        a.approval_record(m, plan_sha, IMAGE, publication_sha); stable_files(files)
        summary["warmupAttempted"] = True
        _, warmup = request_once(host, "POST", "/v1/warmup", 270, summary["httpRequests"], token)
        require(warmup.get("ready") is True and warmup.get("loadedModels") == ["detector", "embedding"]
                and warmup.get("manifestVersion") == MANIFEST_VERSION and warmup.get("featureVersion") == feature,
                "Warmup did not confirm both exact locked models ready")
        summary["httpRequests"][-1]["models"] = {"ready": True, "loadedModels": ["detector", "embedding"],
            "manifestVersion": MANIFEST_VERSION, "featureVersion": feature}
        token = None
        require(len(summary["httpRequests"]) == 3, "Bounded HTTP request count differs")
        summary.update(status="private-http-access-and-model-warmup-verified", modelWarmupVerified=True,
            anonymousDenied=True, userAuthenticatedHealthVerified=True)
    except Exception as error:
        summary["errorType"] = type(error).__name__
        summary["error"] = str(error) if isinstance(error, RuntimeError) else "Bounded check failed; inspect safe metadata without retries"
    finally:
        token = None
        try:
            stable_files(files)
            live_metadata(a, m, detail, url, RESULT / "after-read-only")
            stable_files(files)
            summary["stateSourceIAMUnchanged"] = True
        except Exception as error:
            summary.update(status="blocked", stateSourceIAMUnchanged=False,
                postVerificationErrorType=type(error).__name__,
                postVerificationError="Read-only postcheck failed; inspect private metadata without retries")
        summary["observedAtUtc"] = datetime.now(timezone.utc).isoformat()
        save("summary.json", summary); print(json.dumps(summary, separators=(",", ":")), flush=True)
    return 0 if summary["status"] == "private-http-access-and-model-warmup-verified" else 1


if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"status": "blocked", "errorType": type(error).__name__,
            "error": str(error) if isinstance(error, RuntimeError) else "Invalid/incomplete approved deployment evidence"}), flush=True)
        raise SystemExit(1)
