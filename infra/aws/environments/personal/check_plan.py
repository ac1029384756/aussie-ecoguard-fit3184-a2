"""Offline gate for the first, paused personal-account plan. No cloud clients."""
import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import sys
import zipfile

WIF_SPEC = importlib.util.spec_from_file_location("lambda_wif", Path(__file__).resolve().parents[4] / "scripts/lambda_wif.py")
WIF = importlib.util.module_from_spec(WIF_SPEC)
WIF_SPEC.loader.exec_module(WIF)

ACCOUNT = "011154879765"
REGION = "us-east-1"
PREFIX = "ecoguard3184-personal"
BUCKET = f"{PREFIX}-{ACCOUNT}-media"
EXECUTION_ROLE = f"arn:aws:iam::{ACCOUNT}:role/{PREFIX}-lambda"
FUNCTIONS = {"api", "infer", "delete", "notify", "outbox", "cleanup", "lex_fulfillment"}
TABLES = {"media", "operations", "search", "subscriptions", "outbox"}
QUEUES = {"ingest", "infer", "delete", "notify"}
MODULE = "module.ecoguard."
ROOT_INPUTS = {
    "allowed_account_ids": [ACCOUNT], "region": REGION,
    "prefix": "ecoguard3184", "environment": "personal",
    "manage_execution_role": True, "execution_role_arn": "",
    "manage_media_bucket": True,
    "deploy_api": True, "runtime_enabled": False,
    "worker_image": "", "inference_url": "", "google_invoker_email": "",
    "lex_bot_id": "", "lex_alias_id": "",
    "model_manifest_version": "ecoguard-models-2026-10-08-v3",
    "frontend_origins": ["http://localhost:5173", "http://127.0.0.1:5173"],
    "web_url": "http://127.0.0.1:5173",
}


def expected_addresses():
    addresses = {
        "aws_s3_bucket.media[0]", "aws_s3_bucket_ownership_controls.media[0]",
        "aws_s3_bucket_public_access_block.media", "aws_s3_bucket_server_side_encryption_configuration.media",
        "aws_s3_bucket_cors_configuration.media", "aws_s3_bucket_policy.media_tls",
        "aws_sqs_queue_policy.s3_ingest", "aws_cognito_user_pool.users",
        "aws_cognito_user_pool_client.web", "aws_ecr_repository.worker",
        "aws_apigatewayv2_api.app[0]", "aws_apigatewayv2_authorizer.cognito[0]",
        "aws_apigatewayv2_integration.api[0]", "aws_apigatewayv2_route.api[0]",
        "aws_apigatewayv2_route.preflight[0]", "aws_apigatewayv2_stage.app[0]",
        "aws_lambda_permission.api[0]", "aws_iam_role.runtime[0]", "aws_iam_role_policy.runtime[0]",
    }
    addresses |= {f'aws_dynamodb_table.data["{name}"]' for name in TABLES}
    addresses |= {f'aws_sqs_queue.{kind}["{name}"]' for name in QUEUES for kind in ("work", "dead")}
    addresses |= {f'aws_lambda_function.zip["{name}"]' for name in FUNCTIONS}
    addresses |= {f'aws_cloudwatch_log_group.functions["{name}"]' for name in FUNCTIONS}
    addresses |= {f'aws_lambda_event_source_mapping.zip_queues["{name}"]' for name in ("infer", "delete", "notify")}
    addresses |= {f'{kind}.maintenance["{name}"]' for name in ("outbox", "cleanup") for kind in
                  ("aws_cloudwatch_event_rule", "aws_cloudwatch_event_target", "aws_lambda_permission")}
    return {MODULE + address for address in addresses}


def resources(module):
    yield from module.get("resources", [])
    for child in module.get("child_modules", []):
        yield from resources(child)


def policy_is_scoped(policy):
    if isinstance(policy, str):
        policy = json.loads(policy)
    arn = f"arn:aws:{{service}}:{REGION}:{ACCOUNT}:{{resource}}"
    expected = {
        "ProjectTableRecords": ({"dynamodb:GetItem", "dynamodb:Query", "dynamodb:Scan", "dynamodb:PutItem", "dynamodb:DeleteItem"},
                                {arn.format(service="dynamodb", resource=f"table/{PREFIX}-{name}") for name in TABLES}, None),
        "ProjectBucketListing": ({"s3:ListBucket", "s3:ListBucketVersions"}, {f"arn:aws:s3:::{BUCKET}"}, None),
        "ProjectMediaObjects": ({"s3:GetObject", "s3:GetObjectVersion", "s3:PutObject", "s3:DeleteObject", "s3:DeleteObjectVersion"},
                                {f"arn:aws:s3:::{BUCKET}/*"}, None),
        "ProjectWorkQueues": ({"sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"},
                              {arn.format(service="sqs", resource=f"{PREFIX}-{name}") for name in QUEUES}, None),
        "ProjectNotificationTopics": ({"sns:CreateTopic", "sns:ListSubscriptionsByTopic", "sns:Publish"},
                                      {arn.format(service="sns", resource=f"{PREFIX}-user-*")}, None),
        "ProjectEmailSubscriptions": ({"sns:Subscribe"}, {arn.format(service="sns", resource=f"{PREFIX}-user-*")},
                                     {"StringEquals": {"sns:Protocol": "email"}}),
        "RegionalAnimalLabelDetection": ({"rekognition:DetectLabels"}, {"*"}, {"StringEquals": {"aws:RequestedRegion": REGION}}),
        "ProjectFunctionLogs": ({"logs:CreateLogStream", "logs:PutLogEvents"},
                                {arn.format(service="logs", resource=f"log-group:/aws/lambda/{PREFIX}-{name}:log-stream:*") for name in FUNCTIONS}, None),
    }
    statements = policy.get("Statement", [])
    if (policy.get("Version") != "2012-10-17" or not isinstance(statements, list)
            or len(statements) != len(expected) or {s.get("Sid") for s in statements} != set(expected)):
        return False
    for statement in statements:
        actions, targets, condition = expected[statement["Sid"]]
        if (set(statement) != {"Sid", "Effect", "Action", "Resource"} | ({"Condition"} if condition else set())
                or statement.get("Effect") != "Allow"
                or not isinstance(statement.get("Action"), list) or set(statement["Action"]) != actions
                or not isinstance(statement.get("Resource"), list) or set(statement["Resource"]) != targets
                or statement.get("Condition") != condition):
            return False
    return True


def exact_strings(actual, expected):
    return (isinstance(actual, list) and all(isinstance(item, str) for item in actual)
            and len(actual) == len(expected) and set(actual) == set(expected))


def cors_is_scoped(blocks, origin_key, method_key, methods):
    return (isinstance(blocks, list) and len(blocks) == 1 and isinstance(blocks[0], dict)
            and exact_strings(blocks[0].get(origin_key), ROOT_INPUTS["frontend_origins"])
            and exact_strings(blocks[0].get(method_key), methods))


def root_inventory_policy_is_scoped(policy):
    """Accept only the approved root listing exception and its two AWS forms."""
    bucket = f"arn:aws:s3:::{BUCKET}"
    targets = [bucket, bucket + "/*"]
    expected = {"Version": "2012-10-17", "Statement": [
        {"Sid": "DenyInsecureTransport", "Effect": "Deny", "Principal": "*", "Action": "s3:*",
         "Resource": targets, "Condition": {"Bool": {"aws:SecureTransport": "false"}}},
        {"Sid": "DenyDataAccessWhileRuntimePaused", "Effect": "Deny", "Principal": "*",
         "Action": ["s3:GetObject*", "s3:PutObject*", "s3:DeleteObject*", "s3:RestoreObject",
                    "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts", "s3:ListBucketVersions",
                    "s3:ListBucketMultipartUploads"], "Resource": targets},
        {"Sid": "DenyBucketListingWhileRuntimePaused", "Effect": "Deny", "Principal": "*",
         "Action": ["s3:ListBucket"], "Resource": [bucket],
         "Condition": {"ArnNotEquals": {"aws:PrincipalArn": f"arn:aws:iam::{ACCOUNT}:root"}}}]}
    if not isinstance(policy, dict) or not isinstance(policy.get("Statement"), list) or len(policy["Statement"]) != 3:
        return False
    listing = policy["Statement"][2]
    if (not isinstance(listing, dict) or listing.get("Action") not in ("s3:ListBucket", ["s3:ListBucket"])
            or listing.get("Resource") not in (bucket, [bucket])):
        return False
    # No general policy normalization: retain every key, condition, target and
    # ordered value, changing only these two observed singleton representations.
    normalized = {**policy, "Statement": [*policy["Statement"][:2],
        {**listing, "Action": ["s3:ListBucket"], "Resource": [bucket]}]}
    return normalized == expected


def inspect_bucket_security(values, check, *, root_inventory_while_paused=False):
    if type(root_inventory_while_paused) is not bool:
        raise ValueError("Root inventory review opt-in must be an explicit boolean")
    bucket = values("aws_s3_bucket.media[0]")
    check("owned_personal_bucket_retained", bucket.get("bucket") == BUCKET and bucket.get("force_destroy") is False)
    ownership = values("aws_s3_bucket_ownership_controls.media[0]")
    check("personal_bucket_owner_enforced", ownership.get("bucket") == BUCKET
          and ownership.get("rule") == [{"object_ownership": "BucketOwnerEnforced"}])
    bucket_settings = ("aws_s3_bucket_public_access_block.media", "aws_s3_bucket_server_side_encryption_configuration.media",
                       "aws_s3_bucket_cors_configuration.media", "aws_s3_bucket_policy.media_tls")
    # Addresses alone do not prove that every setting targets this new bucket.
    check("only_personal_bucket_settings", all(values(address).get("bucket") == BUCKET for address in bucket_settings))
    public = values("aws_s3_bucket_public_access_block.media")
    check("all_bucket_public_access_blocked", all(public.get(key) is True for key in
          ("block_public_acls", "block_public_policy", "ignore_public_acls", "restrict_public_buckets")))
    encryption = values("aws_s3_bucket_server_side_encryption_configuration.media").get("rule", [])
    defaults = encryption[0].get("apply_server_side_encryption_by_default", []) if len(encryption) == 1 else []
    check("bucket_default_aes256", len(defaults) == 1 and defaults[0].get("sse_algorithm") == "AES256")
    check("bucket_cors_scoped", cors_is_scoped(values("aws_s3_bucket_cors_configuration.media").get("cors_rule"),
          "allowed_origins", "allowed_methods", ["PUT", "GET", "HEAD"]))

    policy = json.loads(values("aws_s3_bucket_policy.media_tls").get("policy", "{}"))
    statements = policy.get("Statement", [])
    expected_sids = {"DenyInsecureTransport", "DenyDataAccessWhileRuntimePaused"}
    if root_inventory_while_paused:
        expected_sids.add("DenyBucketListingWhileRuntimePaused")
    check("only_reviewed_bucket_policy_statements", policy.get("Version") == "2012-10-17"
          and len(statements) == len(expected_sids) and {s.get("Sid") for s in statements} == expected_sids)
    targets = {f"arn:aws:s3:::{BUCKET}", f"arn:aws:s3:::{BUCKET}/*"}
    tls = [s for s in statements if s.get("Sid") == "DenyInsecureTransport"]
    check("bucket_requires_tls", len(tls) == 1 and tls[0].get("Effect") == "Deny" and tls[0].get("Principal") == "*"
          and tls[0].get("Action") in ("s3:*", ["s3:*"]) and set(tls[0].get("Resource", [])) == targets
          and tls[0].get("Condition") == {"Bool": {"aws:SecureTransport": "false"}})
    pause = [s for s in statements if s.get("Sid") == "DenyDataAccessWhileRuntimePaused"]
    required_s3_actions = {"s3:GetObject*", "s3:PutObject*", "s3:DeleteObject*", "s3:RestoreObject", "s3:AbortMultipartUpload",
                           "s3:ListMultipartUploadParts", "s3:ListBucket", "s3:ListBucketVersions", "s3:ListBucketMultipartUploads"}
    if root_inventory_while_paused:
        required_s3_actions.remove("s3:ListBucket")
    check("bucket_data_paused", len(pause) == 1 and pause[0].get("Effect") == "Deny" and pause[0].get("Principal") == "*"
          and not pause[0].get("Condition") and set(pause[0].get("Action", [])) == required_s3_actions
          and set(pause[0].get("Resource", [])) == targets)
    if root_inventory_while_paused:
        check("only_exact_root_bucket_inventory_exception", root_inventory_policy_is_scoped(policy))


def inspect_plan(document):
    if not isinstance(document, dict):
        raise ValueError("Plan JSON must be an object")
    checks = []

    def check(name, value):
        checks.append({"name": name, "passed": bool(value)})

    planned = list(resources(document.get("planned_values", {}).get("root_module", {})))
    managed = {r["address"]: r for r in planned if r.get("mode") == "managed"}
    identities = [r.get("values", {}).get("account_id") for r in planned
                  if r.get("mode") == "data" and r.get("type") == "aws_caller_identity"]
    if not identities:
        # Terraform may keep an already-read data source only in refreshed state.
        identities = [r.get("values", {}).get("account_id") for r in resources(
            document.get("prior_state", {}).get("values", {}).get("root_module", {}))
            if r.get("mode") == "data" and r.get("type") == "aws_caller_identity"]
    check("verified_personal_account", identities == [ACCOUNT])
    call = document.get("configuration", {}).get("root_module", {}).get("module_calls", {}).get("ecoguard", {})
    expressions = call.get("expressions", {})
    check("fixed_personal_module_inputs", call.get("source") == "../.." and all(
        expressions.get(key, {}).get("constant_value") == value for key, value in ROOT_INPUTS.items()))
    check("unconditional_module_call", not any(key in call for key in ("count_expression", "for_each_expression", "depends_on")))
    check("only_expected_55_resources", set(managed) == expected_addresses())
    changes = [r for r in document.get("resource_changes", []) if r.get("mode") == "managed"]
    check("first_plan_only_creates_expected_resources", len(changes) == len(expected_addresses())
          and {r.get("address") for r in changes} == expected_addresses()
          and all(r.get("change", {}).get("actions") == ["create"] and not r.get("change", {}).get("importing") for r in changes))
    check("no_existing_managed_state", not any(r.get("mode") == "managed" for r in resources(
        document.get("prior_state", {}).get("values", {}).get("root_module", {}))))

    def values(address):
        return managed.get(MODULE + address, {}).get("values", {})

    functions = [values(f'aws_lambda_function.zip["{name}"]') for name in sorted(FUNCTIONS)]
    zip_path = document.get("variables", {}).get("lambda_zip", {}).get("value", "")
    hashes = {f.get("source_code_hash") for f in functions}
    check("real_zip_path_explicit_in_all_functions", isinstance(zip_path, str) and zip_path.startswith("/")
          and zip_path.endswith(".zip") and all(f.get("filename") == zip_path for f in functions))
    check("one_zip_hash_in_all_functions", len(hashes) == 1 and None not in hashes)
    check("all_functions_paused", all(f.get("reserved_concurrent_executions") == 0 for f in functions))
    check("only_x86_python_functions", all(f.get("runtime") == "python3.12" and f.get("architectures") == ["x86_64"]
          and f.get("function_name") == f"{PREFIX}-{name}" for name, f in zip(sorted(FUNCTIONS), functions)))
    check("all_functions_use_dedicated_execution_role", all(f.get("role") == EXECUTION_ROLE for f in functions))
    check("queue_pollers_paused", all(values(f'aws_lambda_event_source_mapping.zip_queues["{name}"]').get("enabled") is False
                                     for name in ("infer", "delete", "notify")))
    check("paused_queue_scaling_config_omitted", all(
        values(f'aws_lambda_event_source_mapping.zip_queues["{name}"]').get("scaling_config", []) == []
        for name in ("infer", "delete", "notify")))
    check("maintenance_paused", all(values(f'aws_cloudwatch_event_rule.maintenance["{name}"]').get("state") == "DISABLED"
                                   for name in ("outbox", "cleanup")))
    check("http_api_paused", values("aws_apigatewayv2_api.app[0]").get("disable_execute_api_endpoint") is True)
    check("http_api_cors_scoped", cors_is_scoped(values("aws_apigatewayv2_api.app[0]").get("cors_configuration"),
          "allow_origins", "allow_methods", ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]))
    pool = values("aws_cognito_user_pool.users")
    signup = pool.get("admin_create_user_config", [])
    check("public_signup_paused", len(signup) == 1 and signup[0].get("allow_admin_create_user_only") is True)
    check("on_demand_project_tables", all(values(f'aws_dynamodb_table.data["{name}"]').get("billing_mode") == "PAY_PER_REQUEST"
                                         and values(f'aws_dynamodb_table.data["{name}"]').get("name") == f"{PREFIX}-{name}" for name in TABLES))
    inspect_bucket_security(values, check)
    role = values("aws_iam_role.runtime[0]")
    expected_trust = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": "sts:AssumeRole",
                                                             "Principal": {"Service": "lambda.amazonaws.com"}}]}
    check("dedicated_lambda_role_only", role.get("name") == f"{PREFIX}-lambda" and role.get("path") == "/"
          and json.loads(role.get("assume_role_policy", "{}")) == expected_trust
          and not role.get("managed_policy_arns") and not role.get("inline_policy"))
    policy = values("aws_iam_role_policy.runtime[0]")
    check("runtime_policy_project_scope", policy.get("name") == f"{PREFIX}-runtime"
          and policy.get("role") == f"{PREFIX}-lambda" and policy_is_scoped(policy.get("policy", "{}")))
    return {"status": "offline-first-plan-passed" if all(c["passed"] for c in checks) else "blocked",
            "account": ACCOUNT, "region": REGION, "managedResources": len(managed), "checks": checks,
            "cloudVerified": False, "billingVerified": False, "crossCloudVerified": False, "applyAuthorized": False}


def verify_archive(document):
    """Read the real local package and compare it with the plan; never create one."""
    path = Path(document.get("variables", {}).get("lambda_zip", {}).get("value", ""))
    if not path.is_absolute() or not path.is_file() or path.suffix != ".zip" or path.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("A real reviewed absolute-path Lambda ZIP of at most 50 MiB is required")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    expected_hash = base64.b64encode(digest.digest()).decode("ascii")
    functions = [r for r in resources(document.get("planned_values", {}).get("root_module", {})) if r.get("type") == "aws_lambda_function"]
    if not functions or any(r.get("values", {}).get("source_code_hash") != expected_hash for r in functions):
        raise ValueError("Real ZIP SHA-256 differs from the plan")
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if sum(e.file_size for e in entries) > 250 * 1024 * 1024 or any(
                e.flag_bits & 1 or PurePosixPath(e.filename).is_absolute() or ".." in PurePosixPath(e.filename).parts
                or "\\" in e.filename or ((e.external_attr >> 16) & 0o170000) == 0o120000 for e in entries):
            raise ValueError("ZIP exceeds unpacked size or contains unsafe/encrypted entries")
        if len(archive.namelist()) != len(set(archive.namelist())):
            raise ValueError("ZIP contains duplicate paths")
        required = {"ecoguard_aws/handlers.py", "ecoguard_aws/runtime.py", "ecoguard_aws/config.py",
                    "ecoguard_aws/pet-calibration.json", "ecoguard_domain/__init__.py", "boto3/__init__.py",
                    "google/auth/__init__.py", "requests/__init__.py", "config/google-wif.json"}
        if not required <= set(archive.namelist()) or archive.testzip() is not None:
            raise ValueError("ZIP is corrupt or missing application/dependency files; no placeholder package is accepted")
        if archive.getinfo("config/google-wif.json").file_size > WIF.MAX_DOCUMENT_BYTES:
            raise ValueError("Packaged WIF document is too large")
        WIF.parse_personal_wif(archive.read("config/google-wif.json"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-json", required=True, type=Path, help="Private terraform show -json output; never commit or paste it")
    args = parser.parse_args(argv)
    try:
        document = json.loads(args.plan_json.read_text(encoding="utf-8"))
        report = inspect_plan(document)
        if report["status"] != "blocked":
            verify_archive(document)
            report["localArchiveVerified"] = True
        print(json.dumps(report, indent=2))
        return 0 if report["status"] != "blocked" else 1
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError, NotImplementedError, zipfile.BadZipFile):
        # Do not print private plan values, environment settings or file contents.
        print("Offline gate blocked: invalid/incomplete plan or real ZIP verification failed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
