"""Default inert. One separately approved bucket-policy replacement, no retries.

Only STS identity and S3 bucket metadata reads accompany one forward write and,
only on failed postchecks with the proposed policy still present, one rollback.
No Terraform, Lambda, object/listing operation or credential persistence.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

BASE = Path("/home/cloudshell-user/ecoguard-c-personal-20261023")
KIT = BASE / "aws-paused-root-inventory-recovery-20261024-1"
RESULT = KIT / "attempt-20261024-1"
SOURCE = BASE / "source"
STATE = SOURCE / "infra/aws/environments/personal/state/terraform.tfstate"
DIAG = BASE / "aws-paused-s3-diagnostic-20261024-1"
AWS = Path("/usr/local/aws-cli/v2/2.38.1/dist/aws")
AWS_SHA = "b95378674f18a78594c62334b2cca9363f4d5c71bd160f578a88b35d28335e09"
PLAN_SHA = "8fc7bba2a41b9c17997853a38e838edc6fb39c0c1f99edfe6b0b73ec955bbbd1"
# Filled only after the user explicitly approves this exact concrete plan.
APPROVAL_SHA256 = None
ACCOUNT, REGION = "011154879765", "us-east-1"
BUCKET = "ecoguard3184-personal-011154879765-media"
ROOT_ARN = "arn:aws:iam::011154879765:root"
HEAD = "ac7757717486b3db2da8c955ebffcc01f6807724"
STATE_SHA = "644e48c482187a7f782f65750059c8e84f084c68e5c400567c67c79fe4d4a26d"
BEFORE_SHA = "04ba66fbc1bfc6fe3e9c18a2113f3f067fd20ada5065001af388dc0331d33c06"
AFTER_SHA = "80f724f068e7a03c369a9e3aa54fd3a89a4dde55551b70b1b164c5787ec8918b"
READS = {"get-bucket-location", "head-bucket", "get-bucket-policy", "get-public-access-block",
         "get-bucket-ownership-controls", "get-bucket-encryption", "get-bucket-policy-status",
         "get-bucket-cors", "get-bucket-notification-configuration"}
PRIVACY = ("get-public-access-block", "get-bucket-ownership-controls", "get-bucket-encryption",
           "get-bucket-policy-status", "get-bucket-cors", "get-bucket-notification-configuration")


def require(value, reason):
    if not value:
        raise RuntimeError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def regular(path, digest=None):
    path = Path(path)
    require(path.is_absolute(), "Absolute reviewed path required")
    for parent in (path, *path.parents):
        require(not parent.is_symlink(), "Symlink in reviewed path rejected")
    require(path.is_file(), "Reviewed regular file missing")
    require(path.stat().st_size < 2 * 1024**2 or path == AWS, "Evidence exceeds size limit")
    with path.open("rb") as stream:
        data = stream.read()
    require(digest is None or sha(data) == digest, "Reviewed evidence/tool hash differs")
    return data


def read_json(path, digest=None):
    return json.loads(regular(path, digest))


def private_json(name, value):
    path = RESULT / name
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def local_env():
    return {"PATH": os.defpath, "LANG": "C", "NO_COLOR": "1", "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_OPTIONAL_LOCKS": "0", "AWS_PAGER": "",
            "AWS_CLI_AUTO_PROMPT": "off"}


def cloud_env():
    blocked = ("AWS_PROFILE", "AWS_DEFAULT_PROFILE", "AWS_CONFIG_FILE", "AWS_SHARED_CREDENTIALS_FILE",
               "AWS_ROLE_ARN", "AWS_WEB_IDENTITY_TOKEN_FILE", "AWS_ROLE_SESSION_NAME", "AWS_ENDPOINT_URL",
               "AWS_CA_BUNDLE", "SSL_CERT_FILE", "SSL_CERT_DIR", "CURL_CA_BUNDLE", "HTTP_PROXY",
               "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
    require(not any(os.environ.get(k) for k in blocked)
            and not any(k.startswith("AWS_ENDPOINT_URL_") for k in os.environ),
            "Unreviewed identity/endpoint/TLS/proxy override")
    # Existing official CloudShell credential-provider chain only. Values are
    # never inspected, printed, exported to files or included in evidence.
    env = dict(os.environ)
    env.update(AWS_REGION=REGION, AWS_DEFAULT_REGION=REGION, AWS_PAGER="", AWS_CLI_AUTO_PROMPT="off",
               AWS_IGNORE_CONFIGURED_ENDPOINT_URLS="true", AWS_MAX_ATTEMPTS="1", NO_COLOR="1")
    return env


def command(argv, env, payload=None):
    try:
        result = subprocess.run([str(v) for v in argv], env=env, input=payload,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=45, shell=False)
    except subprocess.TimeoutExpired:
        raise RuntimeError("Command timed out; outcome is not assumed") from None
    require(len(result.stdout) <= 1024**2, "Metadata output exceeds limit")
    return result


def local_text(argv):
    result = command(argv, local_env(), b"")
    require(result.returncode == 0, "Local source/version read failed")
    return result.stdout.decode().strip()


def source_state():
    require(local_text(["git", "--no-optional-locks", "-C", SOURCE, "rev-parse", "HEAD"]) == HEAD
            and not local_text(["git", "--no-optional-locks", "-C", SOURCE, "status", "--porcelain", "--untracked-files=no"]),
            "Exact clean source differs")
    value = read_json(STATE, STATE_SHA)
    rows = [(r, i) for r in value.get("resources", []) if r.get("mode") == "managed"
            for i in r.get("instances", [])]
    require(value.get("serial") == 60 and value.get("lineage") == "58808681-d69a-1fe0-b562-796a24a58fdc"
            and len(rows) == 55 and all(r.get("module") == "module.ecoguard"
                and i.get("status") in (None, "ready") and not i.get("deposed") for r, i in rows),
            "Exact current untainted physical55 state differs")


def aws_args(service, operation):
    return [AWS, service, operation, "--region", REGION, "--output", "json", "--no-cli-pager",
            "--no-cli-auto-prompt", "--cli-connect-timeout", "5", "--cli-read-timeout", "20"]


def read_aws(env, operation, expect_head=None):
    require(operation in READS, "Operation outside bucket metadata allowlist")
    argv = aws_args("s3api", operation) + ["--bucket", BUCKET, "--expected-bucket-owner", ACCOUNT]
    result = command(argv, env, b"")
    if expect_head == 403:
        require(operation == "head-bucket" and result.returncode == 254 and not result.stdout.strip()
                and b"(403) when calling the HeadBucket operation" in result.stderr,
                "Expected-owner HeadBucket must still be403 before recovery")
        return {"httpStatus": 403, "exitCode": result.returncode}
    require(result.returncode == 0, "Bucket metadata read failed")
    if operation == "head-bucket":
        return {"httpStatus": 200, "exitCode": 0}
    return json.loads(result.stdout.strip() or b"{}")


def identity(env):
    result = command(aws_args("sts", "get-caller-identity"), env, b"")
    require(result.returncode == 0, "Caller identity read failed")
    value = json.loads(result.stdout)
    require(value.get("Account") == ACCOUNT and value.get("Arn") == ROOT_ARN,
            "Exact account-root caller required")
    return value


def expected_before():
    resources = ["arn:aws:s3:::" + BUCKET, "arn:aws:s3:::" + BUCKET + "/*"]
    return {"Version": "2012-10-17", "Statement": [
        {"Sid": "DenyInsecureTransport", "Effect": "Deny", "Principal": "*", "Action": "s3:*",
         "Resource": resources, "Condition": {"Bool": {"aws:SecureTransport": "false"}}},
        {"Sid": "DenyDataAccessWhileRuntimePaused", "Effect": "Deny", "Principal": "*",
         "Action": ["s3:GetObject*", "s3:PutObject*", "s3:DeleteObject*", "s3:RestoreObject",
                    "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts", "s3:ListBucket",
                    "s3:ListBucketVersions", "s3:ListBucketMultipartUploads"], "Resource": resources}]}


def validate_policies(before, after):
    require(before == expected_before(), "Pinned original policy semantics differ")
    expected = json.loads(json.dumps(before))
    expected["Statement"][1]["Action"].remove("s3:ListBucket")
    expected["Statement"].append({"Sid": "DenyBucketListingWhileRuntimePaused", "Effect": "Deny",
        "Principal": "*", "Action": ["s3:ListBucket"], "Resource": ["arn:aws:s3:::" + BUCKET],
        "Condition": {"ArnNotEquals": {"aws:PrincipalArn": ROOT_ARN}}})
    require(after == expected, "Proposed policy exceeds exact root ListBucket exception")


def approval():
    require(isinstance(APPROVAL_SHA256, str) and re.fullmatch(r"[0-9a-f]{64}", APPROVAL_SHA256),
            "Separate actual per-action approval SHA remains pending")
    value = read_json(KIT / "action-approval-private.json", APPROVAL_SHA256)
    expected = {"status": "authorized", "basis": "explicit user approval for this concrete S3 bucket-policy recovery",
        "userConfirmationReceived": True, "planSHA256": PLAN_SHA, "account": ACCOUNT, "region": REGION,
        "bucket": BUCKET, "beforePolicySHA256": BEFORE_SHA, "afterPolicySHA256": AFTER_SHA,
        "maximumForwardPutBucketPolicyCalls": 1, "maximumRollbackPutBucketPolicyCalls": 1,
        "rollbackOnlyAfterPostcheckFailure": True, "rootObjectNameInventoryAuthorized": True,
        "runtimeActivationAuthorized": False, "objectOperationsAuthorized": False,
        "terraformOrStateWriteAuthorized": False, "otherResourceOrIAMChangeAuthorized": False}
    require(set(value) == set(expected) | {"userConfirmationRecord", "approvedAtUtc", "expiresAtUtc"}
            and all(type(value.get(k)) is type(v) and value[k] == v for k, v in expected.items()),
            "Explicit per-action approval scope differs")
    require(isinstance(value["userConfirmationRecord"], str) and value["userConfirmationRecord"].strip(),
            "Actual user confirmation record missing")
    start = datetime.fromisoformat(value["approvedAtUtc"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(value["expiresAtUtc"].replace("Z", "+00:00"))
    require(start.tzinfo is not None and end.tzinfo is not None
            and 0 < (end - start).total_seconds() <= 3600
            and start <= datetime.now(timezone.utc) <= end, "Approval is future, expired or too broad")


def privacy(env):
    v = {name: read_aws(env, name) for name in PRIVACY}
    require(v[PRIVACY[0]].get("PublicAccessBlockConfiguration") == {
        "BlockPublicAcls": True, "BlockPublicPolicy": True, "IgnorePublicAcls": True, "RestrictPublicBuckets": True},
        "Four public-access blocks required")
    require(v[PRIVACY[1]].get("OwnershipControls", {}).get("Rules") == [{"ObjectOwnership": "BucketOwnerEnforced"}],
            "BucketOwnerEnforced required")
    rules = v[PRIVACY[2]].get("ServerSideEncryptionConfiguration", {}).get("Rules", [])
    require(len(rules) == 1 and rules[0].get("ApplyServerSideEncryptionByDefault", {}).get("SSEAlgorithm") == "AES256",
            "Default AES256 encryption required")
    require(v[PRIVACY[3]].get("PolicyStatus", {}).get("IsPublic") is False, "Bucket must remain nonpublic")
    cors = v[PRIVACY[4]].get("CORSRules", [])
    require(len(cors) == 1 and set(cors[0].get("AllowedOrigins", [])) == {"http://localhost:5173", "http://127.0.0.1:5173"}
            and set(cors[0].get("AllowedMethods", [])) == {"PUT", "GET", "HEAD"}, "Exact reviewed CORS required")
    require(v[PRIVACY[5]] == {}, "Bucket notifications must remain absent")
    return v


def live_policy(env):
    value = read_aws(env, "get-bucket-policy")
    require(set(value) == {"Policy"} and isinstance(value["Policy"], str), "Policy response schema differs")
    return json.loads(value["Policy"])


def put_once(env, policy_text, phase, summary):
    # Durable marker precedes the only command. Timeouts/nonzero codes never
    # trigger a retry; they are ambiguous until subsequent metadata reads.
    require(phase in ("forward", "rollback"), "Unknown policy-write phase")
    private_json(phase + "-started-private.json", {"operation": "PutBucketPolicy", "bucket": BUCKET})
    summary[phase + "WriteInvoked" if phase == "forward" else "rollbackInvoked"] = True
    body = {"Bucket": BUCKET, "ExpectedBucketOwner": ACCOUNT, "Policy": policy_text,
            "ConfirmRemoveSelfBucketAccess": False}
    try:
        result = command(aws_args("s3api", "put-bucket-policy") + ["--cli-input-json", "file:///dev/stdin"],
                         env, json.dumps(body).encode())
        outcome = {"invoked": True, "exitCode": result.returncode, "timedOut": False}
    except RuntimeError:
        outcome = {"invoked": True, "exitCode": None, "timedOutOrOutputLimit": True}
    except OSError:
        outcome = {"invoked": False, "exitCode": None, "commandLaunchFailed": True}
        summary[phase + "WriteInvoked" if phase == "forward" else "rollbackInvoked"] = False
    private_json(phase + "-outcome-private.json", outcome)
    return outcome


def postcheck(env, wanted, baseline, location, head_status):
    require(live_policy(env) == wanted, "Full live policy differs from required document")
    current = privacy(env)
    require(current == baseline, "Bucket privacy/CORS/notification metadata changed")
    require(read_aws(env, "get-bucket-location") == location, "Bucket location changed")
    head = read_aws(env, "head-bucket", expect_head=head_status)
    identity(env)
    source_state()
    return {"privacy": current, "head": head, "fullPolicyMatch": True,
            "sourceAndStateUnchanged": True, "exactRootCaller": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        print(json.dumps({"status": "prepared-inert", "cloudInvoked": False, "planSHA256": PLAN_SHA,
                          "explicitPerActionApprovalPending": APPROVAL_SHA256 is None,
                          "maximumForwardWrites": 1, "maximumConditionalRollbackWrites": 1}))
        return 0
    # Missing approval blocks before subprocesses, result creation or cloud reads.
    approval()
    require(sys.platform == "linux", "Reviewed Linux CloudShell required")
    regular(KIT / "recovery-plan.json", PLAN_SHA)
    regular(AWS, AWS_SHA)
    regular(BASE / "aws-source-transition-private-20261024-4.json",
            "6b13e2723a6a8b2241596cbc0a70068ebbdb7e98c5d111255ab5314535358f76")
    read_json(DIAG / "diagnostic-private.json", "02ef277f79c9d6801f9a1c13e5dadedaf17522bdc2b8c99208c86fc54e4a9860")
    before = read_json(DIAG / "parsed-policy-before-private.json", BEFORE_SHA)
    old_raw = read_json(DIAG / "bucket-policy-before-private.json",
                        "bc351b75149ca45c21c219c0e7feb9ec27c4b05b4ce05d3fdecc3d5b74f7200e")
    require(isinstance(old_raw.get("Policy"), str) and json.loads(old_raw["Policy"]) == before,
            "Original rollback policy and parsed observation differ")
    after_text = regular(KIT / "proposed-policy-after.json", AFTER_SHA).decode()
    after = json.loads(after_text)
    validate_policies(before, after)
    require(local_text([AWS, "--version"]).startswith("aws-cli/2.38.1 "), "Pinned AWS CLI version differs")
    source_state()
    env = cloud_env()
    require(KIT.is_dir() and not KIT.is_symlink() and not RESULT.exists() and not RESULT.is_symlink(),
            "Recovery attempt exists or reviewed directory differs; no retry")
    RESULT.mkdir(mode=0o700)
    summary = {"status": "blocked-before-forward-write", "planSHA256": PLAN_SHA,
        "approvalSHA256": APPROVAL_SHA256, "forwardWriteInvoked": False, "rollbackInvoked": False,
        "runtimeActivated": False, "objectOperationsInvoked": False, "terraformOrStateWriteInvoked": False}
    phase = "preflight"
    try:
        caller = identity(env)
        location = read_aws(env, "get-bucket-location")
        require(location.get("LocationConstraint") is None, "Expected us-east-1 bucket location differs")
        require(live_policy(env) == before, "Current policy is not exact reviewed original")
        baseline = privacy(env)
        read_aws(env, "head-bucket", expect_head=403)
        private_json("preflight-private.json", {"identity": caller, "location": location, "privacy": baseline,
                     "policySHA256OfPinnedParsedFile": BEFORE_SHA, "expectedOwnerHeadStatus": 403})
        # Recheck local state, identity, policy and action-time approval adjacent
        # to the write. No apply/import/refresh or other cloud write can occur.
        source_state()
        identity(env)
        require(live_policy(env) == before, "Policy changed immediately before write")
        approval()
        phase = "forward-write"
        summary["forwardOutcome"] = put_once(env, after_text, "forward", summary)
        phase = "postcheck"
        try:
            verified = postcheck(env, after, baseline, location, 200)
            private_json("postcheck-private.json", verified)
            summary.update(status="s3-root-inventory-policy-recovery-verified", policyRecovered=True,
                           sourceAndStateUnchanged=True, headBucketHTTPStatus=200, bucketPublic=False)
        except Exception as failure:
            summary.update(status="postcheck-failed", postcheckFailureType=type(failure).__name__)
            phase = "rollback-eligibility"
            # Never overwrite an unknown/concurrently changed policy. No second
            # forward attempt, credential changes or generic cleanup is allowed.
            source_state()
            identity(env)
            current = live_policy(env)
            if current == after:
                phase = "rollback-write"
                approval()
                summary["rollbackOutcome"] = put_once(env, old_raw["Policy"], "rollback", summary)
                phase = "rollback-postcheck"
                check = postcheck(env, before, baseline, location, 403)
                private_json("rollback-postcheck-private.json", check)
                summary.update(status="postcheck-failed-original-policy-restored", rollbackVerified=True,
                               policyRecovered=False, sourceAndStateUnchanged=True)
            elif current == before:
                summary.update(status="postcheck-failed-original-policy-already-present", rollbackRequired=False,
                               policyRecovered=False)
            else:
                summary.update(status="postcheck-failed-policy-drift-manual-review", policyRecovered=False)
    except Exception as failure:
        summary.update(failureType=type(failure).__name__, failedPhase=phase)
    finally:
        try:
            source_state()
            summary["finalSourceAndStateUnchanged"] = True
        except Exception:
            summary["finalSourceAndStateUnchanged"] = False
            summary["status"] = "blocked-source-or-state-changed"
        private_json("summary-private.json", summary)
    # No raw AWS stderr, caller ARN, policy body or approval quote on stdout.
    print(json.dumps({k: summary[k] for k in ("status", "forwardWriteInvoked", "rollbackInvoked")}))
    return 0 if summary["status"] == "s3-root-inventory-policy-recovery-verified" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as failure:
        print(json.dumps({"status": "blocked", "errorType": type(failure).__name__}))
        raise SystemExit(1)
