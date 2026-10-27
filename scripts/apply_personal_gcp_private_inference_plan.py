"""Frozen next-stage apply preparation; DEFAULT ONLY PRINTS SCOPE, never authorizes.

--apply requires PLAN/apply-approval.json written after a NEW actual user approval:
approved=true, approvedScope="private-inference-four-create-with-google-run-service-agent",
project/projectNumber/sourceRevision, savedPlanSHA256, imageUri,
publicationEvidenceSHA256, approvalReference, approvedAtUtc,
additionalPersonalSpendLimitAUD=0, remainingCreditVerifiedPositive=true,
creditExpiryDate="2026-10-28", cleanupByDateAustraliaMelbourne="2026-10-27",
creditsVerifiedAtUtc (within one hour), billingAccountName (existing verified account).
There is no default authorization and this helper never writes approval.
Only the exact passed 4-create/9-no-op saved plan is applied once. That scope
includes Run API, dedicated runtime SA, private service, sole invoker grant, and
Google's automatic Run service-agent/project-role setup. No invocation, token/key
export, AWS activation, API-enablement workaround, patch, retry or warmup exists.
Deployment itself starts a revision; verification is configuration/readiness,
not proof of inference or federation. Unknown live serialization blocks review.
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
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

sys.dont_write_bytecode = True
BASE = Path.home() / "ecoguard-c-personal-20261023"
FROZEN = BASE / "frozen-publish-inference-20261024-1.py"
FROZEN_SHA = "f180a9ac01473e468bca17c6a4a1a8f5154422bfafb6b986f9a469b48444b462"
ROOT = BASE / "source/infra/gcp/environments/personal"
PLAN = ROOT / "private/private-inference-plan-20261024-2"
BINARY = PLAN / "private-inference.tfplan"
STATE = ROOT / "state/terraform.tfstate"
RESULT = PLAN / "apply-20261024-1"
MARKER = PLAN / "apply-started.json"
PUBLICATION = BASE / "image-publication-20261024-3/summary.json"
TF = "/tmp/ecoguard-c-personal-20261023/tools/terraform"
DATA = Path("/tmp/ecoguard-c-personal-20261023/terraform-data-gcp")
PROJECT, NUMBER, REGION = "ecoguard-fit3184-a2-2026", "995070689587", "us-central1"
HEAD = "3dd63c805b625fb3b378ac977d51c6959d599f0c"
HISTORICAL_HEAD = "00d58e0e8c65321cc759d575eafaba801c1e8253"
REFRESH = ROOT / "private/registry-publication-refresh-20261024-1"
SERVICE = "ecoguard-inference"
RUNTIME = f"ecoguard-inference@{PROJECT}.iam.gserviceaccount.com"
RUN_AGENT = f"service-{NUMBER}@serverless-robot-prod.iam.gserviceaccount.com"
AR_AGENT = f"service-{NUMBER}@gcp-sa-artifactregistry.iam.gserviceaccount.com"
EXECUTION_STARTED = False
ENV = {**os.environ, "TF_DATA_DIR": str(DATA), "TF_IN_AUTOMATION": "1",
       "CHECKPOINT_DISABLE": "1", "CLOUDSDK_CORE_DISABLE_PROMPTS": "1", "PYTHONDONTWRITEBYTECODE": "1"}


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(name, value):
    with (RESULT / name).open("x") as output:
        json.dump(value, output, indent=2); output.write("\n")


def read(argv):
    result = subprocess.run([str(x) for x in argv], env=ENV, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=90, shell=False)
    require(result.returncode == 0, "Read failed: " + " ".join(str(x) for x in argv[:3]))
    return result.stdout.strip()


def edges(policy):
    return {(b["role"], v, json.dumps(b.get("condition"), sort_keys=True))
            for b in policy.get("bindings", []) for v in b.get("members", [])}


def meta(policy):
    return {k: v for k, v in policy.items() if k not in ("bindings", "etag", "version")}


def state_values(path):
    document = json.loads(read([TF, "-chdir=" + str(ROOT), "show", "-json", path]))
    items = GATE.managed(document["values"]["root_module"])
    require(len(items) == len({r["address"] for r in items}), "Duplicate managed state address")
    return {r["address"]: r["values"] for r in items}


def raw_state(data, count):
    value = json.loads(data)
    items = [i for r in value["resources"] if r.get("mode") == "managed" for i in r.get("instances", [])]
    require(len(items) == count and all(i.get("status") in (None, "ready") and not i.get("deposed") for i in items), "Raw state count/taint/deposed mismatch")
    require(isinstance(value.get("lineage"), str) and value["lineage"] and type(value.get("serial")) is int, "State lineage/serial missing")
    return value


def clean_source(m):
    require(read(["git", "-C", m.SOURCE, "rev-parse", "HEAD"]) == HEAD and not
            read(["git", "-C", m.SOURCE, "status", "--porcelain", "--untracked-files=no"]), "Wrong/modified state-owning runtime source")


def refresh_checkpoint(m):
    """Verify retained state A -> narrowly reviewed refresh -> current state B."""
    historical = m.local_json(m.APPLY / "summary.json")
    historical_proof = m.local_json(m.APPLY / "post-verification-private.json")
    require(historical.get("status") == "registry-only-apply-and-verification-passed" and historical.get("applyExitCode") == 0
            and historical.get("sourceRevision") == HISTORICAL_HEAD and historical.get("savedPlanSHA256") == m.SAVED_PLAN_SHA
            and m.sha_file(m.SAVED_PLAN) == m.SAVED_PLAN_SHA, "Historical registry apply/plan checkpoint differs")
    old_path = m.APPLY / "post-state-final.tfstate"
    old = old_path.read_bytes(); old_raw = raw_state(old, 9)
    require(digest(old) == historical_proof.get("stateSHA256") and old_raw["lineage"] == historical_proof.get("lineage")
            and old_raw["serial"] == historical_proof.get("serial") and old == (REFRESH / "state-before-private-backup.json").read_bytes(), "Historical state A/checkpoint differs")
    review = m.local_json(REFRESH / "review-summary.json")
    refreshed = m.local_json(REFRESH / "apply-20261024-1/summary.json")
    expected = {"status": "exact-publication-metadata-state-refresh-passed", "applyExitCode": 0,
        "configurationVerified": True, "managedResources": 9, "cloudResourcesMutated": False, "runtimeCreated": False,
        "sourceRevision": HISTORICAL_HEAD, "changedFields": ["labels", "update_time"],
        "oldUpdateTime": "2026-10-23T22:17:27.541917Z", "newUpdateTime": "2026-10-23T22:42:43.012721Z", "retryAttempted": False}
    require(all(type(refreshed.get(k)) is type(v) and refreshed[k] == v for k, v in expected.items()), "Exact state-only refresh attestation missing")
    refresh_sha = digest((REFRESH / "refresh-only.tfplan").read_bytes())
    require(review.get("status") == "exact-publication-metadata-refresh-plan-passed" and review.get("savedPlanSHA256") == refresh_sha
            and refreshed.get("savedPlanSHA256") == refresh_sha and review.get("stateSHA256") == digest(old)
            and refreshed.get("oldStateSHA256") == digest(old), "Refresh plan/A hash bridge differs")
    publication_sha = m.local_json(REFRESH / "preflight-private.json").get("publicationEvidenceSHA256")
    require(publication_sha == digest(PUBLICATION.read_bytes()), "Publication proof changed across refresh")
    current = STATE.read_bytes(); current_raw = raw_state(current, 9)
    require(current == (REFRESH / "apply-20261024-1/post-state-final.tfstate").read_bytes()
            and digest(current) == refreshed.get("newStateSHA256") and current_raw["lineage"] == old_raw["lineage"] == refreshed.get("lineage")
            and current_raw["serial"] == refreshed.get("newSerial") > refreshed.get("oldSerial") == old_raw["serial"], "Current state B/hash/lineage/serial bridge differs")
    before, after = state_values(old_path), state_values(STATE)
    repo = GATE.MODULE + GATE.REPOSITORY
    require(before.get(repo, {}).get("labels") is None and before[repo].get("update_time") == expected["oldUpdateTime"], "Historical repository fields differ")
    expected_values = {a: dict(v) for a, v in before.items()}
    expected_values[repo] = {**before[repo], "labels": {}, "update_time": expected["newUpdateTime"]}
    require(after == expected_values and set(after) == GATE.IDENTITY.expected_addresses() | GATE.REGISTRY_ADDITIONS
            and GATE.identity_is_exact(after) and GATE.registry_is_exact(after), "State A-to-B changed outside exact metadata")
    return current, current_raw


def identity_and_keys(m, after=False):
    pool = m.cloud("iam", "workload-identity-pools", "describe", "ecoguard-aws", "--location=global", "--project=" + PROJECT)
    provider = m.cloud("iam", "workload-identity-pools", "providers", "describe", "aws-role", "--workload-identity-pool=ecoguard-aws", "--location=global", "--project=" + PROJECT)
    grant = m.cloud("iam", "service-accounts", "get-iam-policy", GATE.INVOKER_EMAIL, "--project=" + PROJECT)
    require(pool.get("name") == GATE.IDENTITY.POOL_NAME and pool.get("state") == "ACTIVE" and pool.get("disabled", False) is False, "Live WIF pool differs")
    require(provider.get("name") == GATE.IDENTITY.POOL_NAME + "/providers/aws-role" and provider.get("state") == "ACTIVE"
            and provider.get("disabled", False) is False and provider.get("aws", {}).get("accountId") == GATE.IDENTITY.AWS_ACCOUNT
            and provider.get("attributeMapping") == GATE.IDENTITY.MAPPING and provider.get("attributeCondition") == GATE.IDENTITY.CONDITION
            and not provider.get("oidc") and not provider.get("saml"), "Live WIF trust differs")
    require(edges(grant) == {("roles/iam.workloadIdentityUser", GATE.IDENTITY.PRINCIPAL, "null")}, "Invoker WIF grant differs")
    accounts = m.cloud("iam", "service-accounts", "list", "--project=" + PROJECT)
    emails = {a["email"] for a in accounts}
    allowed = {GATE.INVOKER_EMAIL, AR_AGENT, RUN_AGENT} | ({RUNTIME} if after else set())
    require(GATE.INVOKER_EMAIL in emails and emails <= allowed and (not after or RUNTIME in emails)
            and all(a.get("disabled", False) is False for a in accounts), "Unexpected/missing/disabled project service account")
    for email in sorted(emails):
        require(m.cloud("iam", "service-accounts", "keys", "list", "--iam-account=" + email, "--managed-by=user", "--project=" + PROJECT) == [], "User-managed service-account key exists")
    return {"pool": pool, "provider": provider, "grant": grant, "serviceAccountEmails": sorted(emails), "userManagedKeyCount": 0}


def approval_record(m, plan_sha, image, publication_sha):
    record = m.local_json(PLAN / "apply-approval.json")
    expected = {"approved": True, "approvedScope": "private-inference-four-create-with-google-run-service-agent",
        "project": PROJECT, "projectNumber": NUMBER, "sourceRevision": HEAD, "savedPlanSHA256": plan_sha,
        "imageUri": image, "publicationEvidenceSHA256": publication_sha, "additionalPersonalSpendLimitAUD": 0,
        "remainingCreditVerifiedPositive": True, "creditExpiryDate": "2026-10-28", "cleanupByDateAustraliaMelbourne": "2026-10-27"}
    require(all(type(record.get(k)) is type(v) and record[k] == v for k, v in expected.items()), "NEW user approval does not match actual plan/image/scope/funding")
    require(isinstance(record.get("approvalReference"), str) and record["approvalReference"].strip(), "Actual new user approval reference missing")
    require(isinstance(record.get("billingAccountName"), str) and re.fullmatch(r"billingAccounts/[0-9A-Fa-f]{6}-[0-9A-Fa-f]{6}-[0-9A-Fa-f]{6}", record["billingAccountName"]), "Verified existing-credit billing account missing")
    current = datetime.now(timezone.utc)
    for key in ("approvedAtUtc", "creditsVerifiedAtUtc"):
        stamp = datetime.fromisoformat(record[key].replace("Z", "+00:00"))
        require(stamp.tzinfo is not None and stamp <= current, "Approval/funding timestamp invalid")
        if key == "creditsVerifiedAtUtc":
            require((current - stamp).total_seconds() <= 3600, "Fresh funding observation older than one hour")
    require(datetime.now(ZoneInfo("Australia/Melbourne")).date().isoformat() < "2026-10-28", "Recorded credits expired")
    billing = m.cloud("billing", "projects", "describe", PROJECT)
    require(billing.get("billingEnabled") is True and billing.get("billingAccountName") == record["billingAccountName"], "Live billing account differs")
    return record


def preflight():
    global GATE
    require(sys.platform == "linux" and os.environ.get("CLOUD_SHELL") == "true", "Existing Google CloudShell required")
    require(not RESULT.exists() and not RESULT.is_symlink() and not MARKER.exists() and not MARKER.is_symlink(), "Run apply attempt exists; no retry")
    for key, value in os.environ.items():
        require(not (value and (key.startswith(("TF_CLI_ARGS", "TF_VAR_")) or key in ("TF_WORKSPACE", "TF_LOG", "TF_LOG_PATH", "TF_CLI_CONFIG_FILE", "TF_REATTACH_PROVIDERS"))), "Terraform environment override")
    for key in ("GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_OAUTH_ACCESS_TOKEN", "GOOGLE_CREDENTIALS", "GOOGLE_IMPERSONATE_SERVICE_ACCOUNT", "GOOGLE_IMPERSONATE_SERVICE_ACCOUNT_DELEGATES", "GOOGLE_CLOUD_KEYFILE_JSON", "GCLOUD_KEYFILE_JSON", "CLOUDSDK_AUTH_ACCESS_TOKEN", "CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT", "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE"):
        require(not os.environ.get(key), "Unreviewed credential override")
    require(not (Path.home() / ".terraformrc").exists(), "Unreviewed Terraform CLI configuration")
    require(FROZEN.is_file() and not FROZEN.is_symlink() and digest(FROZEN.read_bytes()) == FROZEN_SHA, "Frozen publisher missing/changed")
    spec = importlib.util.spec_from_file_location("frozen_publisher", FROZEN); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    require(m.SOURCE_REVISION == HISTORICAL_HEAD and m.PROJECT == PROJECT and m.NUMBER == NUMBER, "Frozen helper scope differs")
    clean_source(m)
    require(read(["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"]) == m.OPERATOR
            and read(["gcloud", "config", "get-value", "project"]) == PROJECT, "Operator/project differs")
    for setting in ("auth/impersonate_service_account", "auth/credential_file_override"):
        require(read(["gcloud", "config", "get-value", setting]) in ("", "(unset)"), "Configured credential override")
    project = m.cloud("projects", "describe", PROJECT)
    require(project.get("projectId") == PROJECT and str(project.get("projectNumber")) == NUMBER and project.get("lifecycleState") == "ACTIVE", "Canonical live project differs")
    require(not any(list(ROOT.glob(p)) for p in ("*.auto.tfvars", "*.auto.tfvars.json", "terraform.tfvars", "terraform.tfvars.json")), "Unexpected root input")
    require(read(["git", "-C", m.SOURCE, "hash-object", ROOT / ".terraform.lock.hcl"]) == read(["git", "-C", m.SOURCE, "rev-parse", HEAD + ":infra/gcp/environments/personal/.terraform.lock.hcl"]), "Provider lock changed")
    version = json.loads(read([TF, "-chdir=" + str(ROOT), "version", "-json"]))
    require(version.get("terraform_version") == "1.17.0" and version.get("provider_selections") == {"registry.terraform.io/hashicorp/google": "7.46.1"}, "Tool/provider differs")
    backend = json.loads((DATA / "terraform.tfstate").read_text())["backend"]
    require(backend.get("type") == "local" and backend["config"]["path"] == "state/terraform.tfstate" and read([TF, "-chdir=" + str(ROOT), "workspace", "show"]) == "default", "Backend/workspace differs")
    spec = importlib.util.spec_from_file_location("frozen_increment_gate", ROOT / "check_runtime_plan.py"); GATE = importlib.util.module_from_spec(spec); spec.loader.exec_module(GATE)
    publication = m.local_json(PUBLICATION)
    proof = {"status": "private-inference-image-published-and-verified", "target": m.TARGET, "archiveSHA256": m.ARCHIVE_SHA,
        "pushReturnedSuccess": True, "registryDigest": m.OCI_DIGEST, "configDigest": m.CONFIG_DIGEST,
        "imageUri": m.IMAGE + "@" + m.OCI_DIGEST, "remoteManifestAndConfigBytesMatch": True,
        "remoteCompressedLayersMatchArchive": True, "stateFileUnchanged": True, "runtimeActivated": False, "iamModified": False, "apisModified": False}
    require(all(type(publication.get(k)) is type(v) and publication[k] == v for k, v in proof.items()), "Actual successful publication3 evidence is missing or differs")
    image, publication_sha = publication["imageUri"], digest(PUBLICATION.read_bytes())
    summary = m.local_json(PLAN / "review-summary.json")
    fixed = {"status": "private-inference-saved-plan-review-passed", "sourceRevision": HEAD, "image": image,
        "creates": 4, "noops": 9, "gateChecksPassed": 13, "gateChecksTotal": 13, "otherChanges": [], "failedChecks": [],
        "warnings": False, "stateFileUnchanged": True, "sourceUnchanged": True, "resourceDriftEntries": 0, "applyExecuted": False}
    require(all(type(summary.get(k)) is type(v) and summary[k] == v for k, v in fixed.items()), "Actual private Run saved plan is not fully passing")
    plan_sha = summary.get("savedPlanSHA256")
    require(isinstance(plan_sha, str) and re.fullmatch(r"[0-9a-f]{64}", plan_sha) and digest(BINARY.read_bytes()) == plan_sha, "Actual saved binary SHA differs")
    original, raw = refresh_checkpoint(m)
    checkpoint = m.local_json(PLAN / "preflight.json")
    require(original == (PLAN / "state-before-private-backup.json").read_bytes() and checkpoint.get("stateSHA256") == digest(original)
            and checkpoint.get("lineage") == raw["lineage"] and checkpoint.get("serial") == raw["serial"], "Nine-state checkpoint differs")
    document = json.loads(read([TF, "-chdir=" + str(ROOT), "show", "-json", BINARY]))
    gate = GATE.inspect_plan(document, "private-inference", image)
    require(gate["status"] == "offline-increment-plan-passed" and len(gate["checks"]) == 13 and all(c["passed"] for c in gate["checks"]), "Fresh saved-binary gate failed")
    values = state_values(STATE)
    require(set(values) == GATE.IDENTITY.expected_addresses() | GATE.REGISTRY_ADDITIONS, "Existing state is not exact nine")
    approval = approval_record(m, plan_sha, image, publication_sha)
    described = m.cloud("artifacts", "docker", "images", "describe", image, "--project=" + PROJECT)
    require(described.get("image_summary", {}).get("digest") == m.OCI_DIGEST and described["image_summary"].get("fully_qualified_digest") == image, "Live immutable image differs")
    repo = m.cloud("artifacts", "repositories", "describe", "ecoguard", "--location=" + REGION, "--project=" + PROJECT)
    require(repo.get("name") == m.REPOSITORY and repo.get("format") == "DOCKER" and repo.get("mode") == "STANDARD_REPOSITORY"
            and not repo.get("remoteRepositoryConfig") and not repo.get("virtualRepositoryConfig"), "Fresh repository settings differ")
    services = m.cloud("services", "list", "--enabled", "--project=" + PROJECT)
    enabled = {s.get("config", {}).get("name") for s in services}
    require("artifactregistry.googleapis.com" in enabled and not enabled.intersection({"containerscanning.googleapis.com", "ondemandscanning.googleapis.com"}), "Registry/scanning API state differs")
    policies, identities = m.private_policies(), identity_and_keys(m)
    require(STATE.read_bytes() == original, "State changed during preflight")
    return m, original, raw, values, policies, identities, approval, plan_sha, image, publication_sha


def live_run(m, image):
    service = m.cloud("run", "services", "describe", SERVICE, "--region=" + REGION, "--project=" + PROJECT)
    save("live-service-private.json", service)
    require(service.get("apiVersion") == "serving.knative.dev/v1" and service.get("kind") == "Service", "Unrecognized service JSON version; inspect privately")
    metadata, status = service["metadata"], service["status"]
    require(metadata.get("name") == SERVICE and str(metadata.get("namespace")) == NUMBER and metadata.get("labels", {}).get("cloud.googleapis.com/location") == REGION, "Live service identity differs")
    ann = metadata.get("annotations", {}); template = service["spec"]["template"]; revann = template.get("metadata", {}).get("annotations", {})
    require(ann.get("run.googleapis.com/ingress") == "all" and ann.get("run.googleapis.com/invoker-iam-disabled", "false") == "false", "Ingress/authentication differs")
    require(ann.get("run.googleapis.com/scalingMode", "automatic") == "automatic" and ann.get("run.googleapis.com/manualInstanceCount", "0") == "0"
            and ann.get("run.googleapis.com/minScale", "0") == "0" and ann.get("run.googleapis.com/maxScale") == "1"
            and revann.get("autoscaling.knative.dev/minScale", "0") == "0" and revann.get("autoscaling.knative.dev/maxScale") == "1", "Live service/revision scaling differs")
    require(revann.get("run.googleapis.com/cpu-throttling", "true") == "true" and revann.get("run.googleapis.com/startup-cpu-boost") == "true", "Live CPU behavior differs")
    forbidden = ("run.googleapis.com/vpc-access-", "run.googleapis.com/network-interfaces", "run.googleapis.com/encryption-key", "run.googleapis.com/base-images", "run.googleapis.com/build-")
    require(not any(k.startswith(forbidden) for k in set(ann) | set(revann)), "Unexpected live networking/encryption/base-image/build configuration")
    require(ann.get("run.googleapis.com/iap-enabled", "false") == "false" and ann.get("run.googleapis.com/default-url-disabled", "false") == "false" and not ann.get("run.googleapis.com/custom-audiences"), "Unexpected live access configuration")
    def configuration(spec):
        containers = spec.get("containers", [])
        require(spec.get("serviceAccountName") == RUNTIME and spec.get("containerConcurrency") == 1 and spec.get("timeoutSeconds") == 360
                and not spec.get("volumes") and len(containers) == 1, "Live identity/concurrency/timeout/volume configuration differs")
        c = containers[0]; env = c.get("env", [])
        require(c.get("image") == image and not c.get("command") and not c.get("args") and not c.get("volumeMounts")
                and len(c.get("ports", [])) == 1 and c["ports"][0].get("containerPort") == 8080 and c["ports"][0].get("name") == "http1"
                and c.get("resources", {}).get("limits", {}).get("cpu") in ("4", "4000m")
                and c.get("resources", {}).get("limits", {}).get("memory") in ("8Gi", "8192Mi")
                and len(env) == len(GATE.RUNTIME_ENV) and {x.get("name"): x.get("value") for x in env} == GATE.RUNTIME_ENV
                and not any(x.get("valueFrom") for x in env), "Live image/resources/environment/command differs")
    configuration(template["spec"])
    require(any(c.get("type") == "Ready" and c.get("status") == "True" for c in status.get("conditions", []))
            and str(status.get("observedGeneration")) == str(metadata.get("generation"))
            and status.get("latestReadyRevisionName") == status.get("latestCreatedRevisionName")
            and isinstance(status.get("latestReadyRevisionName"), str), "Latest service revision is not ready/current")
    revision_name = status["latestReadyRevisionName"]
    revision = m.cloud("run", "revisions", "describe", revision_name, "--region=" + REGION, "--project=" + PROJECT)
    save("live-revision-private.json", revision)
    require(revision.get("apiVersion") == "serving.knative.dev/v1" and revision.get("kind") == "Revision"
            and revision.get("metadata", {}).get("name") == revision_name
            and any(c.get("type") == "Ready" and c.get("status") == "True" for c in revision.get("status", {}).get("conditions", []))
            and revision.get("status", {}).get("imageDigest") in (image, m.OCI_DIGEST), "Ready revision/digest differs")
    configuration(revision["spec"])
    traffic = status.get("traffic", [])
    require(len(traffic) == 1 and traffic[0].get("percent") == 100 and traffic[0].get("revisionName") == revision_name and not traffic[0].get("tag"), "Traffic is not solely latest ready revision")
    url = status.get("url", ""); parsed = urlsplit(url)
    require(parsed.scheme == "https" and parsed.hostname and parsed.hostname.endswith(".run.app") and not parsed.username
            and parsed.port is None and parsed.path in ("", "/") and not parsed.query and not parsed.fragment, "Unexpected service URL")
    policy = m.cloud("run", "services", "get-iam-policy", SERVICE, "--region=" + REGION, "--project=" + PROJECT)
    save("live-service-iam-private.json", policy)
    require(edges(policy) == {("roles/run.invoker", "serviceAccount:" + GATE.INVOKER_EMAIL, "null")}, "Service IAM is not sole exact invoker")
    return {"service": service, "revision": revision, "servicePolicy": policy, "url": url, "readyRevision": revision_name}


def verify_after(m, original_raw, prior_values, policies, identities, image):
    post = STATE.read_bytes(); raw = raw_state(post, 13); values = state_values(STATE)
    require(raw["lineage"] == original_raw["lineage"] and raw["serial"] > original_raw["serial"], "Post-state lineage/serial differs")
    require(set(values) == set(prior_values) | GATE.RUNTIME_ADDITIONS and all(values[a] == v for a, v in prior_values.items())
            and GATE.runtime_is_exact(values, image), "Exact thirteen state resources or unchanged prior nine differ")
    after = m.private_policies(); save("post-iam-private.json", after)
    expected = ("roles/run.serviceAgent", "serviceAccount:" + RUN_AGENT, "null")
    require(set(after) == set(policies), "Project ancestry/policy scope changed")
    for key, old in policies.items():
        new = after[key]
        require(meta(old) == meta(new), "IAM metadata changed")
        if key == "project":
            require(not (edges(old) - edges(new)) and edges(new) - edges(old) <= {expected} and expected in edges(new), "Unexpected project IAM delta")
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
    global EXECUTION_STARTED
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        print(json.dumps({"status": "dry-run", "cloudInvoked": False, "applyExecuted": False,
            "planDirectory": str(PLAN), "expectedCreates": 4, "expectedNoops": 9, "expectedGateChecks": 13,
            "requiresNewActualUserApproval": True, "requiresActualPassedPublication3AndPlan": True,
            "automaticRunAgent": RUN_AGENT, "automaticProjectRole": "roles/run.serviceAgent",
            "invocationsIncluded": False, "awsActivationIncluded": False})); return 0
    m, original, raw, values, policies, identities, approval, plan_sha, image, publication_sha = preflight()
    RESULT.mkdir(mode=0o700)
    save("preflight-private.json", {"sourceRevision": HEAD, "stateSHA256": digest(original), "savedPlanSHA256": plan_sha,
        "imageUri": image, "publicationEvidenceSHA256": publication_sha, "approval": approval, "iamBefore": policies, "identityBefore": identities})
    (RESULT / "state-before-private-backup.json").write_bytes(original)
    clean_source(m); approval_record(m, plan_sha, image, publication_sha)
    require(STATE.read_bytes() == original and digest(BINARY.read_bytes()) == plan_sha and digest(PUBLICATION.read_bytes()) == publication_sha, "State/plan/publication changed before execution")
    with MARKER.open("x") as output:
        json.dump({"startedAtUtc": now(), "savedPlanSHA256": plan_sha, "imageUri": image}, output)
    EXECUTION_STARTED = True
    summary = {"status": "blocked", "project": PROJECT, "projectNumber": NUMBER, "sourceRevision": HEAD,
        "savedPlanSHA256": plan_sha, "imageUri": image, "applyExecuted": True, "applyExitCode": None,
        "retryAttempted": False, "authenticatedInvocationAttempted": False, "awsActivated": False}
    print("PRIVATE_RUN_EXACT_SAVED_PLAN_APPLY_STARTED; no invocation/AWS activation/retry.", flush=True)
    try:
        with (RESULT / "apply-private.log").open("x") as log:
            result = subprocess.run([TF, "-chdir=" + str(ROOT), "apply", "-input=false", "-no-color", "-lock-timeout=60s", str(BINARY)],
                env=ENV, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, timeout=1500, shell=False)
        summary["applyExitCode"] = result.returncode
    except Exception as error:
        summary["executionErrorType"] = type(error).__name__
        if isinstance(error, subprocess.TimeoutExpired): summary["processOutcomeUncertain"] = True
    finally:
        try: (RESULT / "post-state-immediate.tfstate").write_bytes(STATE.read_bytes())
        except Exception as error: summary["postStateCaptureErrorType"] = type(error).__name__
    try:
        detail = verify_after(m, raw, values, policies, identities, image); save("post-verification-private.json", detail)
        summary.update(configurationVerified=True, managedResources=13, runtimeCreated=True, userManagedKeyCount=0,
            url=detail["run"]["url"], readyRevision=detail["run"]["readyRevision"], cloudInferenceVerified=False, crossCloudVerified=False)
        if summary["applyExitCode"] == 0 and not summary.get("processOutcomeUncertain"):
            summary["status"] = "private-run-apply-and-configuration-verification-passed"
    except Exception as error:
        summary["configurationVerified"] = False; summary["verificationErrorType"] = type(error).__name__
        summary["verificationError"] = str(error) if isinstance(error, RuntimeError) else "Inspect private metadata/state; no retry"
    finally:
        try: (RESULT / "post-state-final.tfstate").write_bytes(STATE.read_bytes())
        except Exception as error: summary["status"] = "blocked"; summary["finalStateCaptureErrorType"] = type(error).__name__
        summary["observedAtUtc"] = now(); save("summary.json", summary)
        print(json.dumps(summary, separators=(",", ":")), flush=True)
    return 0 if summary["status"] == "private-run-apply-and-configuration-verification-passed" else 1


if __name__ == "__main__":
    os.umask(0o077)
    try: raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"status": "blocked", "applyExecuted": EXECUTION_STARTED, "errorType": type(error).__name__,
            "error": str(error) if isinstance(error, RuntimeError) else "Invalid/incomplete actual evidence or preflight input"})); raise SystemExit(1)
