"""Pure, fail-closed first automatic activation / adopted pause plan review.

No cloud clients, Terraform execution, write operations or approval inference.
The caller must bind the raw checkpoint, its provider export, source and saved
binary plan. This gate only reviews their JSON values; it cannot enforce time.
"""
import argparse
import base64
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re

SPEC = importlib.util.spec_from_file_location("processing_wiring_gate", Path(__file__).with_name("check_staged_increment_plan.py"))
WIRING = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WIRING)
BASE, FOCUS = WIRING.BASE, WIRING.FOCUS
MODULE, PREFIX, BUCKET = BASE.MODULE, BASE.PREFIX, BASE.BUCKET
NOTIFICATION = MODULE + "aws_s3_bucket_notification.uploads[0]"
BUCKET_POLICY = MODULE + "aws_s3_bucket_policy.media_tls"
FUNCTIONS = {name: MODULE + f'aws_lambda_function.zip["{name}"]' for name in BASE.FUNCTIONS}
FUNCTIONS["ingest"] = FOCUS.INGEST
MAPPINGS = {name: MODULE + f'aws_lambda_event_source_mapping.zip_queues["{name}"]' for name in ("infer", "delete", "notify")}
MAPPINGS["ingest"] = FOCUS.MAPPING
RULES = {name: MODULE + f'aws_cloudwatch_event_rule.maintenance["{name}"]' for name in ("outbox", "cleanup")}
UPDATES = {FUNCTIONS[n] for n in ("ingest", "infer", "outbox")} | {MAPPINGS[n] for n in ("ingest", "infer")} | {RULES["outbox"], BUCKET_POLICY}
WIRED = BASE.expected_addresses() | FOCUS.ADDITIONS
# A future live binder must set this to the actual fresh read-only receipt SHA.
# None blocks activation; unit fixtures are never a default execution receipt.
LIVE_QUOTA_EVIDENCE_SHA256 = None
OUTPUTS = {"deployment_identity", "execution_role_arn", "media_bucket", "api_url", "cognito_user_pool_id", "cognito_client_id", "worker_repository_url", "runtime_enabled", "processing_enabled", "deployment_stage", "runtime_controls"}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def same(a, b):
    """Keep bool distinct from int, recursively, without reordering arrays."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def repaired_ecr_policy_is_scoped(value):
    """Only the sole attached-repository policy accepted by the repair proposal.

    The historical FOCUS checker still describes the original failed plan4 with
    Resource. Do not change that checker or reintroduce its incompatible element.
    """
    if isinstance(value, str):
        value = json.loads(value)
    expected = {"Version": "2012-10-17", "Statement": [{
        "Sid": "LambdaECRImageRetrievalPolicy", "Effect": "Allow",
        "Principal": {"Service": "lambda.amazonaws.com"},
        "Action": ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
        "Condition": {"ArnEquals": {"aws:SourceArn": FOCUS.INGEST_ARN},
                      "StringEquals": {"aws:SourceAccount": BASE.ACCOUNT}}}]}
    return same(value, expected)


def managed(root):
    rows = [r for r in BASE.resources(root) if r.get("mode") == "managed"]
    result = {r["address"]: r["values"] for r in rows}
    require(len(result) == len(rows), "Duplicate managed addresses")
    return result


def controls(active, adopted):
    return {"explicit": True, "function_concurrency": {n: (-1 if n in ("ingest", "infer", "outbox") else 0) if active else 0 for n in FUNCTIONS},
            "media_data_enabled": active, "api_endpoint_enabled": False, "public_signup_enabled": False,
            "queue_consumers": ["infer", "ingest"] if active else [], "schedules": ["outbox"] if active else [],
            "manages_upload_notifications": adopted, "upload_notifications_enabled": active}


def tls_policy():
    arn = "arn:aws:s3:::" + BUCKET
    return {"Version": "2012-10-17", "Statement": [{"Sid": "DenyInsecureTransport", "Effect": "Deny", "Principal": "*", "Action": "s3:*",
            "Resource": [arn, arn + "/*"], "Condition": {"Bool": {"aws:SecureTransport": "false"}}}]}


def notification(active):
    return {"bucket": BUCKET, "region": BASE.REGION, "eventbridge": False, "lambda_function": [], "topic": [],
            "queue": [{"id": PREFIX + "-incoming-ingest", "queue_arn": f"arn:aws:sqs:{BASE.REGION}:{BASE.ACCOUNT}:{PREFIX}-ingest",
                       "events": ["s3:ObjectCreated:*"], "filter_prefix": "incoming/", "filter_suffix": ""}] if active else []}


def profile(values, *, active, adopted, image, zip_filename):
    expected = WIRED | ({NOTIFICATION} if adopted else set())
    require(set(values) == expected, "Exact wired59/adopted60 addresses required")
    for name, address in FUNCTIONS.items():
        v = values[address]
        reservation = (-1 if name in ("ingest", "infer", "outbox") else 0) if active else 0
        require(type(v.get("reserved_concurrent_executions")) is int and v["reserved_concurrent_executions"] == reservation,
                "Function reservation is outside this fixed stage: " + name)
        require(v.get("role") == BASE.EXECUTION_ROLE and v.get("function_name") == PREFIX + "-" + name and v.get("architectures") == ["x86_64"], "Function identity differs")
        env = v.get("environment", [])
        require(len(env) == 1 and all(env[0].get("variables", {}).get(k) == expected for k, expected in WIRING.ENV_BINDINGS.items())
                and env[0]["variables"].get("ECO_GOOGLE_CREDENTIALS_FILE") == "/var/task/config/google-wif.json", "Function Run/WIF binding differs")
        if name == "ingest":
            require(v.get("package_type") == "Image" and v.get("image_uri") == image and all(v.get(k) in (None, "") for k in ("filename", "runtime", "handler")), "Ingest immutable Image binding differs")
        else:
            require(v.get("package_type") == "Zip" and v.get("runtime") == "python3.12" and v.get("filename") == zip_filename
                    and v.get("source_code_hash") == base64.b64encode(bytes.fromhex(WIRING.ZIP_SHA)).decode(), "Reviewed unchanged ZIP differs")
    for name, address in MAPPINGS.items():
        v = values[address]
        enabled = active and name in ("ingest", "infer")
        require(v.get("enabled") is enabled and same(v.get("scaling_config"), [{"maximum_concurrency": 2}] if enabled else [])
                and v.get("event_source_arn") == f"arn:aws:sqs:{BASE.REGION}:{BASE.ACCOUNT}:{PREFIX}-{name}"
                and v.get("function_name") == f"arn:aws:lambda:{BASE.REGION}:{BASE.ACCOUNT}:function:{PREFIX}-{name}"
                and type(v.get("batch_size")) is int and v["batch_size"] == 1 and v.get("function_response_types") == ["ReportBatchItemFailures"], "Queue target/activation/cap differs")
    require(all(values[a].get("state") == ("ENABLED" if active and n == "outbox" else "DISABLED") for n, a in RULES.items()), "Schedule activation differs")
    require(values[MODULE + "aws_apigatewayv2_api.app[0]"].get("disable_execute_api_endpoint") is True, "API endpoint must stay off")
    signup = values[MODULE + "aws_cognito_user_pool.users"].get("admin_create_user_config", [])
    require(len(signup) == 1 and signup[0].get("allow_admin_create_user_only") is True, "Public signup must stay off")
    require(values[BUCKET_POLICY].get("bucket") == BUCKET, "Policy bucket differs")
    policy = json.loads(values[BUCKET_POLICY]["policy"])
    require(same(policy, tls_policy()) if active else BASE.root_inventory_policy_is_scoped(policy), "Only exact TLS-only/approved paused policy allowed")
    # Reuse all privacy checks against the approved pause policy in a copy, so
    # data activation never removes ownership/encryption/public-access/CORS checks.
    safe = copy.deepcopy(values)
    if active:
        # The actual paused policy is checked separately by the caller/profile.
        checks = []
        BASE.inspect_bucket_security(lambda suffix: safe.get(MODULE + suffix, {}), lambda n, ok: checks.append((n, bool(ok))), root_inventory_while_paused=True)
        require(all(ok for n, ok in checks if n not in {"only_reviewed_bucket_policy_statements", "bucket_data_paused", "only_exact_root_bucket_inventory_exception"}), "Bucket privacy/TLS controls differ")
    else:
        checks = []
        BASE.inspect_bucket_security(lambda suffix: safe.get(MODULE + suffix, {}), lambda n, ok: checks.append((n, bool(ok))), root_inventory_while_paused=True)
        require(all(ok for _, ok in checks), "Paused bucket privacy controls differ")
    require(repaired_ecr_policy_is_scoped(values[FOCUS.POLICY]["policy"]) and values[FOCUS.POLICY].get("repository") == FOCUS.REPOSITORY, "ECR retrieval policy differs")
    if adopted:
        value = values[NOTIFICATION]
        require(value.get("id") in (None, BUCKET) and same({k: v for k, v in value.items() if k != "id"}, notification(active)), "Notification destination/prefix/ownership differs")


def compared(old, after, planned, unknown, address, expected):
    allowed = {"last_modified"} if address in {FUNCTIONS[n] for n in ("ingest", "infer", "outbox")} else {
        "last_modified", "last_processing_result", "state", "state_transition_reason"} if address in {MAPPINGS[n] for n in ("ingest", "infer")} else set()
    paths = WIRING.unknown_paths(unknown)
    for path in paths:
        require(len(path) == 1 and path[0] in allowed and unknown.get(path[0]) is True
                and path[0] in after and path[0] in planned and after[path[0]] is None and planned[path[0]] is None,
                "Unreviewed/security/contradictory unknown: " + address)
    projected = {p[0] for p in paths}
    strip = lambda v: {k: x for k, x in v.items() if k not in projected}
    require(same(strip(after), strip(planned)) and same(strip(planned), strip(expected)), "Change outside exact runtime delta: " + address)
    return [list(p) for p in paths]


def reviewed_low_quota(evidence, evidence_sha256, review_time=None):
    require(type(LIVE_QUOTA_EVIDENCE_SHA256) is str and re.fullmatch(r"[0-9a-f]{64}", LIVE_QUOTA_EVIDENCE_SHA256)
            and evidence_sha256 == LIVE_QUOTA_EVIDENCE_SHA256,
            "Future actual quota/inventory receipt SHA is unbound; synthetic defaults cannot activate")
    require(type(evidence) is dict and set(evidence) == {"recordType", "accountId", "region", "observedAtUtc", "accountSettings", "functionNames", "listFunctionsComplete"}
            and evidence["recordType"] == "actual-read-only-lambda-quota-and-inventory"
            and evidence["accountId"] == BASE.ACCOUNT and evidence["region"] == BASE.REGION
            and evidence["listFunctionsComplete"] is True,
            "Actual complete own-account quota/inventory evidence required")
    settings = evidence["accountSettings"]
    require(type(settings) is dict and type(settings.get("AccountLimit")) is dict and type(settings.get("AccountUsage")) is dict,
            "Actual AccountLimit/AccountUsage missing")
    limit, usage = settings["AccountLimit"], settings["AccountUsage"]
    require(type(limit.get("ConcurrentExecutions")) is int and limit["ConcurrentExecutions"] == 10
            and type(limit.get("UnreservedConcurrentExecutions")) is int and limit["UnreservedConcurrentExecutions"] == 10
            and type(usage.get("FunctionCount")) is int and usage["FunctionCount"] == 8,
            "Reviewed future account capacity must be exactly10/10 with eight existing functions")
    require(same(evidence["functionNames"], sorted(PREFIX+"-"+name for name in FUNCTIONS)),
            "Whole account inventory must contain exactly the eight owned function names")
    require(type(evidence["observedAtUtc"]) is str, "Actual quota observation timestamp required")
    observed = datetime.fromisoformat(evidence["observedAtUtc"].replace("Z", "+00:00"))
    current = review_time if review_time is not None else datetime.now(timezone.utc)
    require(observed.tzinfo is not None and current.tzinfo is not None and observed.utcoffset().total_seconds() == 0
            and 0 <= (current-observed).total_seconds() <= 300,
            "Quota/inventory evidence is future-dated/stale; maximum freshness five minutes")
    return {"receiptSHA256": evidence_sha256, "accountConcurrentExecutions": 10, "unreservedConcurrentExecutions": 10,
            "existingFunctionCount": 8, "allEightOwnedFunctionsObserved": True, "maximumEvidenceAgeSeconds": 300,
            "perFunctionReservationsUsed": False, "outboxReservationCapOne": False}


def inspect_plan(document, physical, *, mode, image, zip_filename, window_seconds, quota_evidence=None, quota_evidence_sha256=None, review_time=None):
    require(mode in ("activate-first", "pause-adopted"), "Only first activation or adopted pause is reviewed")
    require(type(window_seconds) is int and 1 <= window_seconds <= 600, "Reviewed bounded window must be 1..600 seconds; no timer is created")
    require(isinstance(image, str) and FOCUS.IMAGE_PATTERN.fullmatch(image), "Exact personal ECR manifest URI required")
    require(isinstance(zip_filename, str) and zip_filename.startswith("/") and zip_filename.endswith(".zip"), "Absolute reviewed ZIP filename required")
    require(document.get("complete") is True and document.get("errored") is not True and not document.get("resource_drift") and not document.get("deferred_changes") and not document.get("action_invocations"), "Incomplete/drift/deferred plan")
    active = mode == "activate-first"
    quota = reviewed_low_quota(quota_evidence, quota_evidence_sha256, review_time) if active else None
    before_root, future_root = document["prior_state"]["values"]["root_module"], document["planned_values"]["root_module"]
    old = managed(physical["values"]["root_module"])
    require(same(managed(before_root), old), "Full refreshed prior differs from the physical checkpoint")
    future = managed(future_root)
    if not active:
        require(old.get(NOTIFICATION, {}).get("id") == BUCKET, "Physical adopted notification ID must be the exact bucket")
    profile(old, active=not active, adopted=not active, image=image, zip_filename=zip_filename)
    profile(future, active=active, adopted=True, image=image, zip_filename=zip_filename)
    # Strict candidate constraint observed in the separate real repair plan.
    # No processing-native plan has established its spelling yet: any deviation
    # must stop review rather than accepting optional/unknown caller resources.
    identity = {"account_id": BASE.ACCOUNT, "id": BASE.ACCOUNT, "user_id": BASE.ACCOUNT,
                "arn": f"arn:aws:iam::{BASE.ACCOUNT}:root"}
    for root in (physical["values"]["root_module"], before_root):
        data_rows = [r for r in BASE.resources(root) if r.get("mode") != "managed"]
        require(len(data_rows) == 1 and data_rows[0].get("mode") == "data"
                and data_rows[0].get("address") == MODULE + "data.aws_caller_identity.current"
                and data_rows[0].get("type") == "aws_caller_identity"
                and same(data_rows[0].get("values"), identity),
                "Physical/prior must contain exactly the literal root caller profile")
    require(not [r for r in BASE.resources(future_root) if r.get("mode") != "managed"],
            "Planned data resources must be exactly absent")
    require(not [r for r in document.get("resource_changes", []) if r.get("mode") != "managed"],
            "Nonmanaged change rows must be exactly absent")
    variables = document.get("variables", {})
    for key, expected in {"deployment_stage": "processing-bounded" if active else "wiring-paused", "adopt_upload_notifications": True,
                          "worker_image": image, "lambda_zip": zip_filename, "inference_url": WIRING.RUN_URL}.items():
        require(same(variables.get(key, {}).get("value"), expected), "Explicit input differs: " + key)
    call = document.get("configuration", {}).get("root_module", {}).get("module_calls", {}).get("ecoguard", {})
    require(call.get("source") == "../.." and not any(k in call for k in ("count_expression", "for_each_expression", "depends_on", "providers")), "Legacy module scope differs")
    expressions = call.get("expressions", {})
    for key, expected in BASE.ROOT_INPUTS.items():
        if key not in {"worker_image", "inference_url", "google_invoker_email"}:
            require(same(expressions.get(key), {"constant_value": expected}), "Static module input differs: " + key)
    require(same(expressions.get("allow_root_bucket_inventory_while_paused"), {"constant_value": True}), "Approved root inventory opt-in required")
    require(expressions.get("manage_upload_notifications") == {"references": ["var.adopt_upload_notifications"]}, "Notification ownership must use the explicit adoption input")
    require(same(expressions.get("allow_unreserved_processing_functions"), {"references": ["var.deployment_stage"]}),
            "Unreserved opt-in must be derived only from the fixed stage selector")
    rows = [r for r in document.get("resource_changes", []) if r.get("mode") == "managed"]
    require(len(rows) == 60 and {r.get("address") for r in rows} == set(future), "Exact sixty managed change rows required")
    paths = {}
    for row in rows:
        address, change = row["address"], row["change"]
        create = address == NOTIFICATION and active
        update = address in UPDATES or address == NOTIFICATION and not active
        actions = ["create"] if create else ["update"] if update else ["no-op"]
        require(change.get("actions") == actions and not any(row.get(k) or change.get(k) for k in ("previous_address", "deposed", "importing", "replace_paths")), "Action/move/import/replacement differs")
        require(same(change.get("before"), None if create else old[address]), "Before values differ from the complete physical export")
        if create:
            require((same(change.get("after_unknown", {}), {}) or same(change.get("after_unknown", {}), {"id": True})) and same(change["after"], future[address]), "Notification security/configuration is unknown/inconsistent")
            if change.get("after_unknown"):
                require("id" in future[address] and future[address]["id"] is None, "Unknown notification ID has a known value")
            continue
        expected = copy.deepcopy(old[address])
        if address in {FUNCTIONS[n] for n in ("ingest", "infer", "outbox")}:
            name = next(n for n, a in FUNCTIONS.items() if a == address)
            expected["reserved_concurrent_executions"] = -1 if active else 0
        elif address in {MAPPINGS[n] for n in ("ingest", "infer")}:
            expected.update(enabled=active, scaling_config=[{"maximum_concurrency": 2}] if active else [])
        elif address == RULES["outbox"]:
            expected["state"] = "ENABLED" if active else "DISABLED"
        elif address == BUCKET_POLICY:
            require(active or BASE.root_inventory_policy_is_scoped(json.loads(future[address]["policy"])), "Pause must restore only the approved root policy")
            expected["policy"] = future[address]["policy"]
        elif address == NOTIFICATION:
            expected["queue"] = []
        paths[address] = compared(old[address], change["after"], future[address], change.get("after_unknown", {}), address, expected)
    # Preserve all eleven outputs and their types/sensitivity. Only the exact
    # stage, effective controls and processing flag may change.
    before_outputs = physical["values"].get("outputs", {})
    prior_outputs = document["prior_state"]["values"].get("outputs", {})
    outputs = document["planned_values"].get("outputs", {})
    require(set(before_outputs) == OUTPUTS and same(prior_outputs, before_outputs) and set(outputs) == OUTPUTS, "All physical/prior/planned outputs must remain present")
    for name, value in before_outputs.items():
        expected = copy.deepcopy(value)
        if name == "deployment_stage": expected["value"] = "processing-bounded" if active else "wiring-paused"
        elif name == "processing_enabled": expected["value"] = active
        elif name == "runtime_controls": expected["value"] = controls(active, True)
        require(same(outputs[name], expected), "Root output drift: " + name)
    output_changes = document.get("output_changes", {})
    require(set(output_changes) == OUTPUTS, "All eleven output change records are required")
    for name in OUTPUTS:
        change = output_changes[name]
        changed = name in {"deployment_stage", "processing_enabled", "runtime_controls"}
        require(change.get("actions") == (["update"] if changed else ["no-op"])
                and same(change.get("before"), before_outputs[name]["value"])
                and same(change.get("after"), outputs[name]["value"])
                and not WIRING.unknown_paths(change.get("after_unknown", False))
                and change.get("before_sensitive") is False and change.get("after_sensitive") is False,
                "Root output action/value/sensitivity differs: " + name)
    require(before_outputs["runtime_enabled"].get("value") is False and same(before_outputs["runtime_controls"]["value"], controls(not active, not active))
            and before_outputs["processing_enabled"].get("value") is (not active)
            and before_outputs["deployment_stage"].get("value") == ("wiring-paused" if active else "processing-bounded"), "Physical stage outputs differ")
    return {"status": "offline-processing-stage-plan-passed", "mode": mode, "priorManagedResources": len(old), "managedResources": 60,
            "creates": 1 if active else 0, "updates": 7 if active else 8, "noops": 52, "physicalPriorFullyEqual": True,
            "reviewedUnknownPaths": {a: p for a, p in paths.items() if p}, "maximumReviewedWindowSeconds": window_seconds,
            "timerCreated": False, "applyAuthorized": False, "cloudVerified": False, "automaticFlowVerified": False,
            "lowQuotaEvidence": quota, "unreservedProcessingOptIn": active, "outboxReservationCapOne": False,
            "pauseDoesNotRequireQuotaEvidence": not active}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", action="store_true")
    for key in ("plan-json", "physical-json"):
        parser.add_argument("--" + key, type=Path)
        parser.add_argument("--" + key + "-sha256")
    parser.add_argument("--mode", choices=("activate-first", "pause-adopted"))
    parser.add_argument("--image")
    parser.add_argument("--zip-filename")
    parser.add_argument("--window-seconds", type=int)
    parser.add_argument("--quota-json", type=Path)
    parser.add_argument("--quota-json-sha256")
    args = parser.parse_args()
    if not args.review:
        print(json.dumps({"status": "dry-run", "filesRead": False, "applyAuthorized": False}))
        return 0
    try:
        quota = None
        if args.mode == "activate-first":
            require(type(LIVE_QUOTA_EVIDENCE_SHA256) is str and args.quota_json_sha256 == LIVE_QUOTA_EVIDENCE_SHA256,
                    "Future live quota receipt pin pending; no activation review")
            require(isinstance(args.quota_json, Path) and args.quota_json.is_absolute() and args.quota_json.is_file()
                    and not any(p.is_symlink() for p in (args.quota_json, *args.quota_json.parents)), "Pinned actual quota receipt path required")
            data = args.quota_json.read_bytes()
            require(len(data) <= 1024**2 and hashlib.sha256(data).hexdigest() == LIVE_QUOTA_EVIDENCE_SHA256, "Actual quota receipt bytes/hash differ")
            quota = json.loads(data)
        documents = []
        for key in ("plan_json", "physical_json"):
            path, expected = getattr(args, key), getattr(args, key + "_sha256")
            require(isinstance(path, Path) and isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected), "Actual plan and physical-export paths/hashes are required")
            data = path.read_bytes()
            require(hashlib.sha256(data).hexdigest() == expected, "Reviewed JSON hash differs")
            documents.append(json.loads(data))
        report = inspect_plan(*documents, mode=args.mode, image=args.image, zip_filename=args.zip_filename, window_seconds=args.window_seconds,
            quota_evidence=quota, quota_evidence_sha256=args.quota_json_sha256)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "blocked", "reason": str(error), "applyAuthorized": False}))
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
