"""Inert bounded-processing controller core, with explicit runtime capabilities.

Default/import/inspect never arm, start a process, call a CLI or contact a cloud.
Low-quota alternative: three active functions are unreserved (value None), not
individually capped. This separate copy is proposed only; all actual pins remain
pending. The original core1a704 is preserved byte-identical in its old directory.
"""
from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Protocol

ACCOUNT = "011154879765"
REGION = "us-east-1"
PREFIX = "ecoguard3184-personal"
TARGETS = ("outbox-rule", "bucket-notifications", "ingest-mapping", "infer-mapping",
           "ingest-concurrency", "infer-concurrency", "outbox-concurrency", "bucket-policy")
OPERATIONS = dict(zip(TARGETS, ("DisableRule", "PutBucketNotificationConfiguration",
    "UpdateEventSourceMapping", "UpdateEventSourceMapping", "PutFunctionConcurrency",
    "PutFunctionConcurrency", "PutFunctionConcurrency", "PutBucketPolicy")))
REASONS = {"success", "deadline", "heartbeat", "funding", "verification", "user-pause", "partial-apply"}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def same(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class ReadFailure(RuntimeError):
    """An adapter reports only a fixed category, never raw credential-bearing stderr."""


@dataclass(frozen=True)
class Intent:
    target: str
    operation: str
    identity: dict
    parameters: dict


class RuntimePort(Protocol):
    """Future adapter contract; methods below must never accept arbitrary CLI text.

    Reads retain raw private evidence and return exact reviewed identity, immutable
    profile SHA and control value. No general normalization: policy admits ONLY
    the two documented singleton spellings. Notification value is the WHOLE
    document, so any extra destination makes equality fail. Profile hashing must
    cover every reviewed unchanged configuration field, not caller assertions.

    mark_once persists an exclusive intent BEFORE an external call and survives
    restart. close_input is a sticky shared IPC latch. quiesce_writer checks
    exact PID/starttime/UID/process-group/nonce ownership; never signals itself or
    an unrelated process. A failed quiesce must not prevent other safe reductions.
    All external calls have bounded timeouts; AWS_MAX_ATTEMPTS=1; no blind retry.
    """
    def close_input(self, context_sha: str, nonce: str) -> bool: ...
    def quiesce_writer(self, expected: dict, timeout_seconds: int) -> dict: ...
    def observe(self, target: str, timeout_seconds: int) -> dict: ...
    def mark_once(self, action: str, context_sha: str, nonce: str, request_sha: str | None = None) -> bool: ...
    def mutate(self, intent: Intent, timeout_seconds: int) -> str: ...
    def unchanged_boundaries(self, timeout_seconds: int) -> dict: ...
    def append_receipt(self, receipt: dict): ...
    def input_is_open(self, context_sha: str, nonce: str) -> bool: ...
    def watchdog_ack(self, context_sha: str, nonce: str) -> dict: ...
    def apply_saved_plan_once(self, plan_sha: str) -> dict: ...
    def verify_exact_active_profile(self) -> bool: ...
    def request_stop(self, reason: str, context_sha: str, nonce: str): ...


def inspect_design(path=None):
    path = path or Path(__file__).with_name("INTERFACE-PENDING.json")
    record = json.loads(path.read_text())
    pins = record["actualPins"]
    return {"status": "implementation-draft-inert", "pendingPins": [k for k, v in pins.items() if v is None],
            "productionRuntimeAdapterImplemented": False, "armed": False,
            "processStarted": False, "subprocessInvoked": False, "cloudInvoked": False}


def arm_watchdog(binding, local_port, monotonic_now, utc_now):
    """Future explicit entry; default bindings fail BEFORE any adapter operation.

    This core does not launch/detach processes. A future separately reviewed local
    driver must verify all evidence and per-action human authority, create private
    IPC and a distinct watchdog process group, then obtain a fresh liveness ACK.
    It must not convert a filled-in dict into verified evidence by declaration.
    """
    pins = binding["actualPins"]
    require(pins and all(v is not None for v in pins.values()), "Actual pins pending; no arm")
    raise ValueError("Production process/evidence/IPC adapter not implemented; no real arm")


def writer_is_quiesced(result, expected):
    return (isinstance(result, dict) and same(result.get("identity"), expected)
            and result.get("quiesced") is True and result.get("inFlightCloudCallsRetracted") is False)


def policy_documents():
    bucket = "arn:aws:s3:::" + PREFIX + "-" + ACCOUNT + "-media"
    tls = {"Sid": "DenyInsecureTransport", "Effect": "Deny", "Principal": "*", "Action": "s3:*",
        "Resource": [bucket, bucket + "/*"], "Condition": {"Bool": {"aws:SecureTransport": "false"}}}
    data = {"Sid": "DenyDataAccessWhileRuntimePaused", "Effect": "Deny", "Principal": "*",
        "Action": ["s3:GetObject*", "s3:PutObject*", "s3:DeleteObject*", "s3:RestoreObject",
            "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts", "s3:ListBucketVersions", "s3:ListBucketMultipartUploads"],
        "Resource": [bucket, bucket + "/*"]}
    listing = {"Sid": "DenyBucketListingWhileRuntimePaused", "Effect": "Deny", "Principal": "*",
        "Action": ["s3:ListBucket"], "Resource": [bucket],
        "Condition": {"ArnNotEquals": {"aws:PrincipalArn": "arn:aws:iam::" + ACCOUNT + ":root"}}}
    return ({"Version": "2012-10-17", "Statement": [tls]},
            {"Version": "2012-10-17", "Statement": [tls, data, listing]})


def paused_policy_form(value):
    candidate = copy.deepcopy(value)
    if isinstance(candidate, dict) and isinstance(candidate.get("Statement"), list) and len(candidate["Statement"]) == 3:
        last = candidate["Statement"][2]
        if isinstance(last, dict):
            if same(last.get("Action"), "s3:ListBucket"):
                last["Action"] = ["s3:ListBucket"]
            bucket = "arn:aws:s3:::" + PREFIX + "-" + ACCOUNT + "-media"
            if same(last.get("Resource"), bucket):
                last["Resource"] = [bucket]
    return candidate


def observation_state(context, target, observation):
    spec = context["targets"][target]
    require(isinstance(observation, dict)
            and same(observation.get("identity"), spec["identity"])
            and observation.get("immutableProfileSHA256") == spec["immutableProfileSHA256"],
            "Unreviewed target identity or immutable configuration")
    value = observation.get("value")
    if target == "bucket-policy":
        value = paused_policy_form(value)
    if target in ("ingest-mapping", "infer-mapping"):
        require(isinstance(value, dict) and set(value) == {"state", "maximumConcurrency"}, "Mapping shape differs")
        require(value["maximumConcurrency"] is None or same(value["maximumConcurrency"], 2), "Unreviewed SQS cap")
        require(value["state"] in {"Enabled", "Disabled", "Enabling", "Disabling"}, "Unexpected mapping state")
        if value["state"] == "Disabled":
            return "safe"
        return "wait" if value["state"] in {"Enabling", "Disabling"} else "reduce"
    if same(value, spec["safeValue"]):
        return "safe"
    require(same(value, spec["activeValue"]), "Value is neither exact reviewed active nor paused")
    return "reduce"


def reduction_intent(context, target):
    """Only the eight monotone reductions; no generic request/argv escape hatch."""
    require(target in TARGETS, "Unknown reduction target")
    spec = context["targets"][target]
    if target == "outbox-rule":
        parameters = {"EventBusName": "default"}
    elif target == "bucket-notifications":
        parameters = {"ExpectedBucketOwner": ACCOUNT, "NotificationConfiguration": {}}
    elif target.endswith("-mapping"):
        parameters = {"Enabled": False}
    elif target.endswith("-concurrency"):
        parameters = {"ReservedConcurrentExecutions": 0}
    else:
        parameters = {"ExpectedBucketOwner": ACCOUNT, "Policy": copy.deepcopy(spec["safeValue"])}
    return Intent(target, OPERATIONS[target], copy.deepcopy(spec["identity"]), parameters)


def validate_context(context):
    require(context["account"] == ACCOUNT and context["region"] == REGION, "Scope differs")
    require(set(context["targets"]) == set(TARGETS), "Exactly eight reviewed controls required")
    require(type(context["windowSeconds"]) is int and 1 <= context["windowSeconds"] <= 600, "Window outside 1..600")
    require(type(context["callTimeoutSeconds"]) is int and 1 <= context["callTimeoutSeconds"] <= 10, "Call timeout differs")
    require(type(context["pollReadsMaximum"]) is int and 1 <= context["pollReadsMaximum"] <= 3, "Poll bound differs")
    require(type(context["stopReserveSeconds"]) is int and 1 <= context["stopReserveSeconds"] < context["windowSeconds"], "Stop reserve differs")
    require(type(context["heartbeatSeconds"]) is int and 1 <= context["heartbeatSeconds"] <= 30, "Heartbeat bound differs")
    # Quiesce + boundary read + each target's bounded initial/poll/mutation
    # calls, followed by one independent final read of every target.
    call_bound = (2 + len(TARGETS) * (2 * context["pollReadsMaximum"] + 2)) * context["callTimeoutSeconds"]
    require(context["stopReserveSeconds"] >= call_bound + context["callTimeoutSeconds"], "Stop reserve does not cover bounded worst-case reduction calls")
    # Reviewed identities/profiles and full active/paused policy documents must
    # be created from actual pinned evidence by the absent production adapter.
    require(all(type(spec["identity"]) is dict and type(spec["immutableProfileSHA256"]) is str
                for spec in context["targets"].values()), "Malformed reviewed targets")
    bucket = PREFIX + "-" + ACCOUNT + "-media"
    for target in TARGETS:
        spec = context["targets"][target]
        require(re.fullmatch(r"[0-9a-f]{64}", spec["immutableProfileSHA256"]), "Unpinned immutable profile")
        if target == "outbox-rule":
            identity = {"Name": PREFIX + "-outbox", "Arn": f"arn:aws:events:{REGION}:{ACCOUNT}:rule/{PREFIX}-outbox", "EventBusName": "default"}
            safe, active = "DISABLED", "ENABLED"
        elif target.startswith("bucket-"):
            identity = {"Bucket": bucket, "ExpectedBucketOwner": ACCOUNT}
            if target == "bucket-policy":
                active, safe = policy_documents()
            else:
                safe, active = {}, spec["activeValue"]
                queues = active.get("QueueConfigurations") if isinstance(active, dict) else None
                require(set(active) == {"QueueConfigurations"} and isinstance(queues, list) and len(queues) == 1, "Unknown notification destinations")
                q = queues[0]
                require(set(q) <= {"Id", "QueueArn", "Events", "Filter"}
                    and q.get("QueueArn") == f"arn:aws:sqs:{REGION}:{ACCOUNT}:{PREFIX}-ingest"
                    and same(q.get("Events"), ["s3:ObjectCreated:*"])
                    and same(q.get("Filter"), {"Key": {"FilterRules": [{"Name": "prefix", "Value": "incoming/"}]}})
                    and ("Id" not in q or type(q["Id"]) is str), "Notification scope differs")
        else:
            name = target.split("-", 1)[0]
            arn = f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:{PREFIX}-{name}"
            if target.endswith("-mapping"):
                uuid = context["mappingUUIDs"][name]
                require(isinstance(uuid, str) and re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", uuid), "Exact mapping UUID pending")
                identity = {"UUID": uuid, "FunctionArn": arn, "EventSourceArn": f"arn:aws:sqs:{REGION}:{ACCOUNT}:{PREFIX}-{name}"}
                safe, active = spec["safeValue"], spec["activeValue"]
                require(same(safe, {"state": "Disabled", "maximumConcurrency": None})
                    and same(active, {"state": "Enabled", "maximumConcurrency": 2}), "Mapping reviewed values differ")
            else:
                identity = {"FunctionArn": arn}
                safe, active = 0, None
        require(same(spec["identity"], identity) and same(spec["safeValue"], safe) and same(spec["activeValue"], active), "Target identity/value scope differs")
    require(same(context["accountConcurrencyProfile"], {"ConcurrentExecutions": 10, "UnreservedConcurrentExecutions": 10, "FunctionCount": 8}), "Low-quota account profile differs")
    require(type(context["quotaReadMaximumAgeSeconds"]) is int and 1 <= context["quotaReadMaximumAgeSeconds"] <= 10, "Quota read age differs")
    require(same(context["actualFunctionTimeouts"], {"ingest": 120, "infer": 480, "outbox": 60}), "Actual timeout profile differs")
    require(same(context["pausedBoundaries"], {"otherFiveConcurrency": {"api": 0, "delete": 0, "notify": 0, "cleanup": 0, "lex_fulfillment": 0},
        "apiEndpointDisabled": True, "publicSignupDisabled": True, "cleanupRuleDisabled": True,
        "bucketPrivacyUnchanged": True, "unrelatedIAMAndControlsUnchanged": True}), "Paused read-only boundaries differ")


def validate_arm(context, armed):
    validate_context(context)
    require(armed["contextSHA256"] == digest(context), "Arm context differs")
    require(armed["stopNewWorkBy"] == armed["t0"] + context["windowSeconds"], "Deadline was extended/reset")
    writer, watchdog = armed["writerIdentity"], armed["watchdogIdentity"]
    fields = {"pid", "pgid", "uid", "startTime", "nonce"}
    require(set(writer) == set(watchdog) == fields and type(armed["nonce"]) is str
        and re.fullmatch(r"[0-9a-f]{64}", armed["nonce"]) and armed["nonce"] == context["nonce"], "Process identity shape differs")
    require(all(type(actor[k]) is int and actor[k] > 1 for actor in (writer, watchdog) for k in ("pid", "pgid", "startTime")), "Process identity is not pinned")
    require(type(writer["uid"]) is int and writer["uid"] == watchdog["uid"] == context["operatorUID"]
        and writer["pid"] != watchdog["pid"] and writer["pgid"] != watchdog["pgid"]
        and writer["nonce"] == watchdog["nonce"] == armed["nonce"], "Writer/watchdog ownership or process groups differ")


def pause_and_observe(context, armed, port, monotonic_now, reason):
    """Watchdog-only reducer using an already verified simulated/future capability.

    Does not demand a whole active60 PASS. Each known owned target is validated
    independently, including mixed partial apply. Failed targets do not prevent
    the remaining seven attempts. A second pass can READ but cannot re-mutate a
    target with a prior durable intent, including uncertain/failed outcomes.
    """
    validate_arm(context, armed)
    require(reason in REASONS, "Arm reason differs")
    started = monotonic_now()
    require(type(started) in (int, float) and started >= armed["t0"], "Monotonic clock precedes original T0")
    try:
        input_closed = port.close_input(armed["contextSHA256"], armed["nonce"]) is True
    except Exception:
        input_closed = False
    try:
        quiesce = port.quiesce_writer(armed["writerIdentity"], context["callTimeoutSeconds"])
        writer_stopped = writer_is_quiesced(quiesce, armed["writerIdentity"])
    except Exception:
        writer_stopped = False
    rows = []
    for target in TARGETS:
        row = {"target": target, "mutationAttempted": False, "pausedVerified": False}
        try:
            observation = port.observe(target, context["callTimeoutSeconds"])
            state = observation_state(context, target, observation)
            reads = 1
            while state == "wait" and reads < context["pollReadsMaximum"]:
                observation = port.observe(target, context["callTimeoutSeconds"])
                reads += 1
                state = observation_state(context, target, observation)
            if state == "reduce":
                if port.mark_once("reduce:" + target, armed["contextSHA256"], armed["nonce"]):
                    row["mutationAttempted"] = True
                    try:
                        row["mutationOutcome"] = port.mutate(reduction_intent(context, target), context["callTimeoutSeconds"])
                    except Exception:
                        row["mutationOutcome"] = "uncertain-or-failed-no-retry"
                else:
                    row["mutationOutcome"] = "prior-intent-no-retry"
                for _ in range(context["pollReadsMaximum"]):
                    observation = port.observe(target, context["callTimeoutSeconds"])
                    state = observation_state(context, target, observation)
                    if state == "safe":
                        break
            row["pausedVerified"] = state == "safe"
            row["finalState"] = state
        except Exception:
            # NotFound/403/timeouts are NOT evidence that a target is paused.
            row["errorCategory"] = "unverified-read-or-unreviewed-control"
        rows.append(row)
    try:
        boundaries_ok = same(port.unchanged_boundaries(context["callTimeoutSeconds"]), context["pausedBoundaries"])
    except Exception:
        boundaries_ok = False
    final_rows = []
    for target in TARGETS:
        final = {"target": target, "readOnly": True, "pausedVerified": False}
        try:
            final["pausedVerified"] = observation_state(context, target,
                port.observe(target, context["callTimeoutSeconds"])) == "safe"
        except Exception:
            final["errorCategory"] = "unverified-final-read-or-unreviewed-control"
        final_rows.append(final)
    observed = monotonic_now()
    all_safe = input_closed and writer_stopped and boundaries_ok and all(row["pausedVerified"] for row in final_rows)
    report = {"status": "emergency-controls-paused" if all_safe else "blocked-recovery-required",
        "contextSHA256": armed["contextSHA256"], "nonce": armed["nonce"], "reason": reason,
        "inputClosed": input_closed, "writerQuiesced": writer_stopped, "inFlightCloudCallsRetracted": False,
        "requestedStopDeadline": armed["stopNewWorkBy"], "pauseRequestedAt": started,
        "controlReadbackAt": observed, "deadlineMissed": observed > armed["stopNewWorkBy"],
        "targets": rows, "finalControlReadbacks": final_rows,
        "allEightConcurrencyZeroAndOtherBoundariesVerified": boundaries_ok and all(
            row["pausedVerified"] for row in final_rows if row["target"].endswith("-concurrency")),
        "declarativeTerraformStateReconciled": False, "applicationDrained": False,
        "hardVMOrCredentialSurvivalGuarantee": False, "automaticRetryPermitted": False}
    port.append_receipt(copy.deepcopy(report))
    return report


def watchdog_reason(context, armed, monotonic_now, heartbeat, funding_valid, stop_requested=None):
    """Pure tick: original monotonic deadline is never reset for work latency."""
    validate_arm(context, armed)
    now = monotonic_now()
    require(type(now) in (int, float) and now >= armed["t0"], "Monotonic clock precedes original T0")
    if stop_requested is not None:
        require(stop_requested in REASONS, "Unexpected stop reason")
        return stop_requested
    if now >= armed["stopNewWorkBy"] - context["stopReserveSeconds"]:
        return "deadline"
    if funding_valid is not True:
        return "funding"
    if (heartbeat.get("nonce") != armed["nonce"] or heartbeat.get("contextSHA256") != armed["contextSHA256"]
            or type(heartbeat.get("at")) not in (int, float) or not 0 <= now - heartbeat["at"] <= context["heartbeatSeconds"]):
        return "heartbeat"
    return None


def assert_submission_open(context, armed, port, monotonic_now, active_verified, funding_valid, heartbeat):
    require(watchdog_reason(context, armed, monotonic_now, heartbeat, funding_valid) is None, "Stop margin/funding/heartbeat exhausted")
    ack = port.watchdog_ack(armed["contextSHA256"], armed["nonce"])
    require(same(ack.get("identity"), armed["watchdogIdentity"]) and ack.get("contextSHA256") == armed["contextSHA256"]
        and type(ack.get("at")) in (int, float) and 0 <= monotonic_now() - ack["at"] <= context["heartbeatSeconds"], "Fresh watchdog liveness ACK missing")
    require(active_verified is True and port.input_is_open(armed["contextSHA256"], armed["nonce"]), "Input latched closed or active profile unverified")


def activate_once(context, armed, port, monotonic_now, funding_valid, heartbeat):
    """Orchestrator capability: one pinned binary, no replan/retry or fixture here."""
    assert_submission_open(context, armed, port, monotonic_now, True, funding_valid, heartbeat)
    require(port.mark_once("activation", armed["contextSHA256"], armed["nonce"]), "Activation intent already exists")
    try:
        result = port.apply_saved_plan_once(context["activationSavedPlanSHA256"])
        active = type(result.get("exitCode")) is int and result["exitCode"] == 0 and port.verify_exact_active_profile() is True
    except Exception:
        active = False
    if not active:
        try:
            input_closed = port.close_input(armed["contextSHA256"], armed["nonce"]) is True
        except Exception:
            input_closed = False
        try:
            port.request_stop("partial-apply", armed["contextSHA256"], armed["nonce"])
            stop_requested = True
        except Exception:
            stop_requested = False
    else:
        input_closed, stop_requested = False, False
    return {"activationAttempted": True, "activeVerified": active, "retryPermitted": False,
            "fixtureSubmitted": False, "watchdogMustRemainArmed": True,
            "status": "active-profile-verified" if active else "blocked-stop-required",
            "inputClosureVerified": input_closed, "stopRequestRecorded": stop_requested}


def before_fixture_write(context, armed, port, monotonic_now, active_verified,
                         funding_valid, heartbeat, action, request_sha):
    """Callback for the separately reviewed fixture helper's two exact writes.

    The transport must check request_sha against its independently pinned seed or
    PUT spec. This core only closes the time/input window and consumes each intent
    durably before the possible request. A failed/uncertain attempt stays consumed.
    """
    require(action in {"seed", "source-put"} and isinstance(request_sha, str)
        and re.fullmatch(r"[0-9a-f]{64}", request_sha), "Unknown fixture write or request hash")
    require(request_sha == context["fixtureRequestSHA256"][action], "Fixture request differs from exact reviewed spec")
    assert_submission_open(context, armed, port, monotonic_now, active_verified, funding_valid, heartbeat)
    require(port.mark_once("fixture:" + action, armed["contextSHA256"], armed["nonce"], request_sha), "Fixture intent already consumed; no resubmission")
    return {"allowed": True, "action": action, "requestSHA256": request_sha,
        "contextSHA256": armed["contextSHA256"], "nonce": armed["nonce"]}


def observe_drain(context, pause_receipt, monotonic_now, evidence):
    """Separate scoped evidence; elapsed time or a delayed metric alone is insufficient."""
    validate_context(context)
    require(pause_receipt["status"] == "emergency-controls-paused"
        and pause_receipt.get("contextSHA256") == digest(context)
        and pause_receipt.get("nonce") == context["nonce"], "Paused receipt is not from this exact context/nonce")
    max_timeout = max(context["actualFunctionTimeouts"].values())
    require(type(max_timeout) is int and max_timeout > 0, "Actual timeout evidence missing")
    allowance = context["propagationReadAllowanceSeconds"]
    require(type(allowance) in (int, float) and math.isfinite(allowance) and allowance >= 0,
            "Propagation/read allowance must be typed finite and nonnegative")
    observed, paused_at = monotonic_now(), pause_receipt["controlReadbackAt"]
    require(all(type(value) in (int, float) and math.isfinite(value) and value >= 0
                for value in (observed, paused_at)) and observed >= paused_at, "Drain monotonic times are invalid")
    tail = max_timeout + allowance
    elapsed = observed - paused_at
    required = {"controlsStillPaused": True, "knownJobsTerminal": True,
        "producerLeasesExpired": True, "noUnresolvedInFlightEvidence": True,
        "boundedObservationWindowCovered": True}
    ok = elapsed >= tail and same(evidence, required)
    return {"status": "application-drained-with-reviewed-evidence" if ok else "drain-not-proven",
            "minimumObservationTailSeconds": tail, "observedElapsedSeconds": elapsed,
            "inFlightCancellationClaimed": False, "cleanupInvoked": False,
            "declarativeTerraformStateReconciled": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", action="store_true")
    parser.parse_args()
    print(json.dumps(inspect_design(), separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
