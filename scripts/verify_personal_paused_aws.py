"""Frozen CloudShell configuration audit for the 2026-10-24 personal AWS stack.

Expects the existing ~/ecoguard-c-personal-20261023 workspace and private report
folder. Its source checkout must remain at
29367645d62d47f16ac64659266dc3ba1540b89d. The original fdfaf23 create-plan binary
must have SHA-256
997517ccfd38b8257d07ec1073843611c90bec29c9b6f00ff2a4c4ca863154ba.

This audit covers that exact deployment and its three-mapping recovery. It reads
AWS configuration and local plan/state metadata, writes only its private summary,
and performs no invocation, user-data access, state write or runtime activation.
Its result is a frozen configuration observation, not a general shutdown check
or proof of application behavior, cross-cloud operation or future billing.
"""
import base64
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

BASE = Path.home() / "ecoguard-c-personal-20261023"
ROOT = BASE / "source/infra/aws/environments/personal"
TF = "/tmp/ecoguard-c-personal-20261023/tools/terraform"
ENV = {**os.environ, "TF_DATA_DIR": "/tmp/ecoguard-c-personal-20261023/terraform-data-aws",
       "AWS_PAGER": "", "AWS_CLI_AUTO_PROMPT": "off"}
ZIP = BASE / "artifacts/aws-personal-lambda-20261023-1.zip"
ZIP_SHA = "fafb94bf948312f1fef8998b5619567ad3c3471381a34e9e816cec87b034d9f6"
SOURCE_HEAD = "29367645d62d47f16ac64659266dc3ba1540b89d"
PLAN_SHA = "997517ccfd38b8257d07ec1073843611c90bec29c9b6f00ff2a4c4ca863154ba"
ACCOUNT, REGION, PREFIX = "011154879765", "us-east-1", "ecoguard3184-personal"
ROLE, BUCKET = PREFIX + "-lambda", PREFIX + "-" + ACCOUNT + "-media"
ROLE_ARN = f"arn:aws:iam::{ACCOUNT}:role/{ROLE}"
CHECKS = []


def check(name, passed):
    CHECKS.append({"name": name, "passed": bool(passed)})


def read_text(argv):
    result = subprocess.run(argv, env=ENV, stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, timeout=60, check=False, shell=False)
    if result.returncode:
        raise RuntimeError("Read operation failed: " + " ".join(argv[:3]))
    return result.stdout


def read_json(argv):
    output = read_text(argv)
    return json.loads(output) if output.strip() else {}


def aws(service, operation, *arguments):
    return read_json(["aws", service, operation, *arguments, "--region", REGION, "--output", "json"])


def norm(value, key=""):
    if isinstance(value, str) and key in ("Action", "Resource", "AWS", "Service"):
        value = [value]
    if key == "Principal" and value == "*":
        value = {"AWS": ["*"]}
    if key == "Statement" and isinstance(value, dict):
        value = [value]
    if isinstance(value, dict):
        return {name: norm(item, name) for name, item in value.items()}
    if isinstance(value, list):
        return sorted((norm(item) for item in value), key=lambda item: json.dumps(item, sort_keys=True))
    return value


def main():
    check("exact_recovery_source_head", read_text(["git", "-C", str(BASE / "source"), "rev-parse", "HEAD"]).strip() == SOURCE_HEAD)
    check("tracked_source_clean", not read_text(["git", "-C", str(BASE / "source"), "status", "--porcelain", "--untracked-files=no"]).strip())
    if not all(item["passed"] for item in CHECKS):
        return
    spec = importlib.util.spec_from_file_location("personal_gate", ROOT / "check_plan.py")
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    identity = aws("sts", "get-caller-identity")
    check("verified_personal_account", identity.get("Account") == ACCOUNT)
    if identity.get("Account") != ACCOUNT:
        return
    binary = ROOT / "private/first-paused.tfplan"
    check("original_approved_binary_sha256", hashlib.sha256(binary.read_bytes()).hexdigest() == PLAN_SHA)
    if not CHECKS[-1]["passed"]:
        return
    # Export the pinned original binary: the recovery gate intentionally rejects
    # its former ScalingConfig, so do not apply today's inspect_plan to it.
    plan = read_json([TF, "-chdir=" + str(ROOT), "show", "-json", str(binary)])
    planned = {r["address"]: r["values"] for r in gate.resources(plan["planned_values"]["root_module"]) if r.get("mode") == "managed"}
    changes = [r for r in plan["resource_changes"] if r.get("mode") == "managed"]
    check("original_55_create_scope", len(planned) == len(changes) == 55 and set(planned) == {r["address"] for r in changes} == gate.expected_addresses() and all(r.get("change", {}).get("actions") == ["create"] and not r.get("change", {}).get("importing") for r in changes))
    raw = json.loads((ROOT / "state/terraform.tfstate").read_text())
    instances = [item for resource in raw["resources"] if resource.get("mode") == "managed" for item in resource.get("instances", [])]
    check("all_raw_state_instances_current_untainted", len(instances) == 55 and all(item.get("status") in (None, "ready") and not item.get("deposed") for item in instances))
    state = read_json([TF, "-chdir=" + str(ROOT), "show", "-json", str(ROOT / "state/terraform.tfstate")])
    managed = [r for r in gate.resources(state["values"]["root_module"]) if r.get("mode") == "managed"]
    check("exact_55_managed_state_addresses", len(managed) == 55 and {r["address"] for r in managed} == set(planned) == gate.expected_addresses())
    values = {r["address"][len(gate.MODULE):]: r["values"] for r in managed}
    digest = hashlib.sha256(ZIP.read_bytes()).digest()
    code_hash = base64.b64encode(digest).decode("ascii")
    check("exact_reviewed_local_zip", digest.hex() == ZIP_SHA)
    role = aws("iam", "get-role", "--role-name", ROLE)["Role"]
    check("exact_lambda_role_and_trust", role.get("Arn") == ROLE_ARN and norm(role.get("AssumeRolePolicyDocument")) == norm(json.loads(planned[gate.MODULE + "aws_iam_role.runtime[0]"]["assume_role_policy"])))
    check("no_attached_role_policies", aws("iam", "list-attached-role-policies", "--role-name", ROLE).get("AttachedPolicies") == [])
    check("one_reviewed_inline_policy", aws("iam", "list-role-policies", "--role-name", ROLE).get("PolicyNames") == [PREFIX + "-runtime"])
    policy = aws("iam", "get-role-policy", "--role-name", ROLE, "--policy-name", PREFIX + "-runtime")["PolicyDocument"]
    check("live_runtime_policy_scoped", gate.policy_is_scoped(norm(policy)))
    for name in sorted(gate.FUNCTIONS):
        function = PREFIX + "-" + name
        cfg = aws("lambda", "get-function-configuration", "--function-name", function, "--query",
                  "{Name:FunctionName,State:State,Update:LastUpdateStatus,Role:Role,Runtime:Runtime,Architectures:Architectures,Hash:CodeSha256}")
        check(name + "_code_ready_exact_role_runtime_hash", cfg == {"Name": function, "State": "Active", "Update": "Successful", "Role": ROLE_ARN, "Runtime": "python3.12", "Architectures": ["x86_64"], "Hash": code_hash})
        check(name + "_concurrency_zero", aws("lambda", "get-function-concurrency", "--function-name", function).get("ReservedConcurrentExecutions") == 0)
    for name in ("infer", "delete", "notify"):
        mappings = aws("lambda", "list-event-source-mappings", "--function-name", PREFIX + "-" + name).get("EventSourceMappings", [])
        check(name + "_only_expected_disabled_mapping", len(mappings) == 1 and mappings[0].get("State") == "Disabled" and mappings[0].get("EventSourceArn") == f"arn:aws:sqs:{REGION}:{ACCOUNT}:{PREFIX}-{name}" and mappings[0].get("ScalingConfig") in (None, {}))
    for name in ("outbox", "cleanup"):
        check(name + "_schedule_disabled", aws("events", "describe-rule", "--name", PREFIX + "-" + name).get("State") == "DISABLED")
    api = aws("apigatewayv2", "get-api", "--api-id", values["aws_apigatewayv2_api.app[0]"]["id"])
    cors = api.get("CorsConfiguration", {})
    check("api_disabled_and_exact_cors", api.get("Name") == PREFIX + "-api" and api.get("DisableExecuteApiEndpoint") is True and set(cors.get("AllowOrigins", [])) == set(gate.ROOT_INPUTS["frontend_origins"]) and set(cors.get("AllowMethods", [])) == {"GET", "POST", "PATCH", "DELETE", "OPTIONS"})
    pool = aws("cognito-idp", "describe-user-pool", "--user-pool-id", values["aws_cognito_user_pool.users"]["id"])["UserPool"]
    check("public_signup_disabled", pool.get("Name") == PREFIX + "-users" and pool.get("AdminCreateUserConfig", {}).get("AllowAdminCreateUserOnly") is True)
    bucket_args = ("--bucket", BUCKET, "--expected-bucket-owner", ACCOUNT)
    pab = aws("s3api", "get-public-access-block", *bucket_args).get("PublicAccessBlockConfiguration", {})
    check("all_four_public_access_blocks", all(pab.get(key) is True for key in ("BlockPublicAcls", "BlockPublicPolicy", "IgnorePublicAcls", "RestrictPublicBuckets")))
    check("bucket_owner_enforced", aws("s3api", "get-bucket-ownership-controls", *bucket_args).get("OwnershipControls", {}).get("Rules") == [{"ObjectOwnership": "BucketOwnerEnforced"}])
    rules = aws("s3api", "get-bucket-encryption", *bucket_args).get("ServerSideEncryptionConfiguration", {}).get("Rules", [])
    check("default_aes256", len(rules) == 1 and rules[0].get("ApplyServerSideEncryptionByDefault", {}).get("SSEAlgorithm") == "AES256")
    check("bucket_not_public", aws("s3api", "get-bucket-policy-status", *bucket_args).get("PolicyStatus", {}).get("IsPublic") is False)
    live_policy = json.loads(aws("s3api", "get-bucket-policy", *bucket_args)["Policy"])
    planned_policy = json.loads(planned[gate.MODULE + "aws_s3_bucket_policy.media_tls"]["policy"])
    check("exact_reviewed_tls_and_paused_policy", norm(live_policy) == norm(planned_policy))
    cors_rules = aws("s3api", "get-bucket-cors", *bucket_args).get("CORSRules", [])
    check("bucket_cors_exact_origins_methods", len(cors_rules) == 1 and set(cors_rules[0].get("AllowedOrigins", [])) == set(gate.ROOT_INPUTS["frontend_origins"]) and set(cors_rules[0].get("AllowedMethods", [])) == {"PUT", "GET", "HEAD"})
    check("no_s3_notifications", not aws("s3api", "get-bucket-notification-configuration", *bucket_args))


if __name__ == "__main__":
    if not ROOT.is_dir() or not (ROOT / "private").is_dir():
        print(json.dumps({"status": "blocked", "reason": "frozen_cloudshell_root_or_private_directory_missing",
                          "account": ACCOUNT, "region": REGION, "sourceCommit": "2936764",
                          "runtimeActivated": False}, separators=(",", ":")))
        raise SystemExit(1)
    try:
        main()
    except Exception:
        check("all_read_operations_completed", False)
    report = {"status": "paused-config-verified" if CHECKS and all(c["passed"] for c in CHECKS) else "blocked", "account": ACCOUNT, "region": REGION, "sourceCommit": "2936764", "originalPlanSource": "fdfaf23", "observedAtUtc": datetime.now(timezone.utc).isoformat(), "checksPassed": sum(c["passed"] for c in CHECKS), "checksTotal": len(CHECKS), "failedChecks": [c["name"] for c in CHECKS if not c["passed"]], "runtimeActivated": False, "crossCloudVerified": False, "applicationVerified": False}
    report_path = ROOT / "private/post-apply-paused-verification.json"
    with os.fdopen(os.open(report_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(report, stream, indent=2)
    print(json.dumps(report, separators=(",", ":")))
    raise SystemExit(0 if report["status"] != "blocked" else 1)
