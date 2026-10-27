"""Offline review of a fresh, paused 56 -> 59 repair plan; never applies.

The original native plan4 JSON is an immutable reference, not a template to
rewrite or submit. The caller separately binds the real source, provider export,
normal refreshed-plan invocation and saved binary. No cloud acceptance follows.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re

SPEC = importlib.util.spec_from_file_location("repair_wiring_gate", Path(__file__).with_name("check_staged_increment_plan.py"))
W = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(W)
B, F = W.BASE, W.FOCUS
ORIGINAL_JSON_SHA = "b3c576af9355747d1ebb8d37c4170bcbb5cbdcda93fff24420ea958746158ce3"
RAW_STATE_SHA = "ad411dc4f52a7f510cc19518ff9e60f25948999dccb8b8d363a6ed19da401f95"
LINEAGE, SERIAL = "58808681-d69a-1fe0-b562-796a24a58fdc", 72
OLD = B.expected_addresses() | {F.LOG}
NEW = {F.POLICY, F.INGEST, F.MAPPING}
OUTPUTS = {"deployment_identity", "execution_role_arn", "media_bucket", "api_url", "cognito_user_pool_id", "cognito_client_id", "worker_repository_url", "runtime_enabled", "processing_enabled", "deployment_stage", "runtime_controls"}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def same(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def parsed(data):
    return json.loads(data, object_pairs_hook=pairs)


def managed(root):
    rows = [r for r in B.resources(root) if r.get("mode") == "managed"]
    result = {r["address"]: r["values"] for r in rows}
    require(len(result) == len(rows), "Duplicate managed address")
    return result


def raw_checkpoint(data):
    require(hashlib.sha256(data).hexdigest() == RAW_STATE_SHA, "Actual partial-state bytes/SHA differ")
    value = parsed(data)
    require(value.get("lineage") == LINEAGE and type(value.get("serial")) is int and value["serial"] == SERIAL, "Actual56 lineage/serial differ")
    found = set()
    for resource in value.get("resources", []):
        if resource.get("mode") != "managed":
            continue
        require(resource.get("module") == B.MODULE.rstrip("."), "Unexpected managed module")
        base = resource["module"] + "." + resource["type"] + "." + resource["name"]
        for instance in resource.get("instances", []):
            require(instance.get("status") in (None, "ready") and not instance.get("deposed"), "Tainted/deposed instance")
            key = instance.get("index_key")
            address = base + ("[" + json.dumps(key, separators=(",", ":")) + "]" if key is not None else "")
            require(address not in found, "Duplicate raw instance")
            found.add(address)
    require(found == OLD and len(found) == 56, "Actual partial state must contain the exact56")
    return value


def omitted_policy(original, candidate):
    require(F.policy_exact(original), "Original policy is not the already reviewed exact statement")
    expected = parsed(original) if isinstance(original, str) else copy.deepcopy(original)
    del expected["Statement"][0]["Resource"]
    actual = parsed(candidate) if isinstance(candidate, str) else candidate
    require(same(actual, expected), "Repair may only omit Resource; principal/actions/function/account must remain exact")
    return expected


def no_move(row):
    change = row.get("change", {})
    require(not any(row.get(k) or change.get(k) for k in ("previous_address", "deposed", "importing", "replace_paths")), "Move/import/replacement rejected")


def unchanged(row, actual, future):
    no_move(row)
    c = row["change"]
    require(c.get("actions") == ["no-op"] and same(c.get("after_unknown", {}), {}), "Every existing56 resource must be a known no-op")
    require(same(c.get("before"), actual) and same(c.get("after"), actual) and same(future, actual), "An existing56 resource changed")


def created(address, row, future, original_row, original_future, image):
    no_move(row)
    c, o = row["change"], original_row["change"]
    require(c.get("actions") == o.get("actions") == ["create"] and c.get("before") is None, "Only the three original missing creations may be repaired")
    require(same(c.get("after_unknown", {}), o.get("after_unknown", {})), "New unknown mask differs from the original actual plan4")
    require(same(c.get("after_sensitive", {}), o.get("after_sensitive", {})), "New sensitivity mask differs")
    W.new_known_values(address, c, future, image)
    W.new_known_values(address, o, original_future, image)
    expected_after, expected_future = copy.deepcopy(o["after"]), copy.deepcopy(original_future)
    if address == F.POLICY:
        omitted_policy(expected_after["policy"], c["after"]["policy"])
        omitted_policy(expected_future["policy"], future["policy"])
        require(future.get("repository") == F.REPOSITORY, "Policy attachment must be the sole exact repository")
        expected_after["policy"] = c["after"]["policy"]
        expected_future["policy"] = future["policy"]
    # Preserve each native representation independently: unknown attributes may
    # be null in change.after but absent from planned_values. No normalization.
    require(same(c["after"], expected_after) and same(future, expected_future), "New configured/known profile differs from original actual plan4")


def paused_profile(values, original_values, zip_path):
    for name in B.FUNCTIONS:
        address = B.MODULE + 'aws_lambda_function.zip["' + name + '"]'
        value = values[address]
        require(type(value.get("reserved_concurrent_executions")) is int and value["reserved_concurrent_executions"] == 0 and value.get("role") == B.EXECUTION_ROLE, "Existing ZIP must remain paused on the exact role")
        require(value.get("filename") == zip_path and value.get("source_code_hash") == original_values[address].get("source_code_hash") and same(value.get("environment"), original_values[address].get("environment")), "Existing reviewed ZIP/Run/WIF binding differs")
    for name in ("delete", "notify", "infer"):
        value = values[B.MODULE + 'aws_lambda_event_source_mapping.zip_queues["' + name + '"]']
        require(value.get("enabled") is False and same(value.get("scaling_config"), []), "Existing consumer must stay disabled without a concurrency cap")
    for name in ("cleanup", "outbox"):
        require(values[B.MODULE + 'aws_cloudwatch_event_rule.maintenance["' + name + '"]'].get("state") == "DISABLED", "Schedule must remain disabled")
    require(values[B.MODULE + "aws_apigatewayv2_api.app[0]"].get("disable_execute_api_endpoint") is True, "API must remain paused")
    signup = values[B.MODULE + "aws_cognito_user_pool.users"].get("admin_create_user_config", [])
    require(len(signup) == 1 and signup[0].get("allow_admin_create_user_only") is True, "Signup must remain restricted")
    checks = []
    B.inspect_bucket_security(lambda suffix: values.get(B.MODULE + suffix, {}), lambda name, ok: checks.append((name, ok)), root_inventory_while_paused=True)
    require(checks and all(ok for _, ok in checks), "Paused private bucket profile differs")
    require(same(parsed(values[W.ROLE_POLICY]["policy"]), parsed(original_values[W.ROLE_POLICY]["policy"])), "Already completed sole-log-ARN runtime policy differs")


def inspect_plan(document, physical, original_bytes, raw_state_bytes):
    raw_checkpoint(raw_state_bytes)
    require(hashlib.sha256(original_bytes).hexdigest() == ORIGINAL_JSON_SHA, "Use the unchanged original actual plan4 JSON")
    original = parsed(original_bytes)
    original_values = managed(original["planned_values"]["root_module"])
    original_rows = {r["address"]: r for r in original["resource_changes"] if r.get("mode") == "managed"}
    require(set(original_values) == set(original_rows) == OLD | NEW, "Original plan4 address profile differs")
    require(original.get("complete") is True and original.get("errored") is not True, "Original native plan is incomplete")
    require(document.get("complete") is True and document.get("errored") is not True and not document.get("resource_drift") and not document.get("deferred_changes") and not document.get("action_invocations"), "Incomplete/drift/deferred/action plan")
    old = managed(physical["values"]["root_module"])
    prior = managed(document["prior_state"]["values"]["root_module"])
    future = managed(document["planned_values"]["root_module"])
    require(set(old) == OLD and same(prior, old) and set(future) == OLD | NEW, "Full physical56/prior equality and exact future59 required")
    original_vars = original.get("variables", {})
    require(set(document.get("variables", {})) == set(original_vars) and same(document["variables"], original_vars), "All explicit inputs must remain the original wiring-paused values")
    require(original_vars.get("deployment_stage", {}).get("value") == "wiring-paused" and original_vars.get("inference_url", {}).get("value") == W.RUN_URL, "Original stage/Run differs")
    image = original_vars.get("worker_image", {}).get("value")
    zip_path = original_vars.get("lambda_zip", {}).get("value")
    require(isinstance(image, str) and F.IMAGE_PATTERN.fullmatch(image) and isinstance(zip_path, str) and zip_path.startswith("/") and zip_path.endswith(".zip"), "Original immutable image/ZIP input differs")
    paused_profile(old, original_values, zip_path)
    call = document.get("configuration", {}).get("root_module", {}).get("module_calls", {})
    require(set(call) == {"ecoguard"} and call["ecoguard"].get("source") == "../.." and not any(k in call["ecoguard"] for k in ("count_expression", "for_each_expression", "depends_on", "providers")), "Legacy module source/scope differs")
    require(same(call["ecoguard"].get("expressions"), original["configuration"]["root_module"]["module_calls"]["ecoguard"]["expressions"]), "Module input expressions changed")
    for root in (physical["values"]["root_module"], document["prior_state"]["values"]["root_module"], document["planned_values"]["root_module"]):
        data = [r for r in B.resources(root) if r.get("mode") != "managed"]
        require(len(data) == 1 and data[0].get("mode") == "data" and data[0].get("address") == B.MODULE + "data.aws_caller_identity.current" and data[0].get("type") == "aws_caller_identity", "Only the exact caller identity data resource is allowed")
        require(data[0].get("values", {}).get("account_id") == B.ACCOUNT and data[0]["values"].get("arn") == "arn:aws:iam::" + B.ACCOUNT + ":root", "Exact root account required")
    changes = document.get("resource_changes", [])
    rows = [r for r in changes if r.get("mode") == "managed"]
    require(len(rows) == 59 and {r.get("address") for r in rows} == OLD | NEW, "Exactly59 unique managed change rows required")
    for row in rows:
        address = row["address"]
        if address in OLD:
            unchanged(row, old[address], future[address])
        else:
            created(address, row, future[address], original_rows[address], original_values[address], image)
    data_changes = [r for r in changes if r.get("mode") != "managed"]
    require(len(data_changes) <= 1, "Unexpected nonmanaged change")
    for row in data_changes:
        no_move(row)
        c = row.get("change", {})
        require(row.get("mode") == "data" and row.get("address") == B.MODULE + "data.aws_caller_identity.current" and row.get("type") == "aws_caller_identity" and c.get("actions") in (["read"], ["no-op"]) and same(c.get("after_unknown", {}), {}), "Unknown/extra data action")
        target = [r["values"] for r in B.resources(document["planned_values"]["root_module"]) if r.get("mode") == "data"][0]
        require(same(c.get("after"), target), "Caller data change/planned values differ")
    outputs = physical["values"].get("outputs", {})
    require(set(outputs) == OUTPUTS and outputs.get("deployment_stage") == {"sensitive": False, "type": "string", "value": "wiring-paused"} and outputs.get("runtime_enabled", {}).get("value") is False and outputs.get("processing_enabled", {}).get("value") is False, "Physical wiring-paused11 outputs required")
    require(same(outputs.get("runtime_controls"), original["planned_values"].get("outputs", {}).get("runtime_controls")), "Original exact paused runtime-control descriptor required")
    require(same(document["prior_state"]["values"].get("outputs"), outputs) and same(document["planned_values"].get("outputs"), outputs), "No output descriptor may change")
    output_changes = document.get("output_changes", {})
    require(set(output_changes) == OUTPUTS, "All11 output change rows required")
    for name, descriptor in outputs.items():
        c = output_changes[name]
        require(c.get("actions") == ["no-op"] and same(c.get("before"), descriptor["value"]) and same(c.get("after"), descriptor["value"]) and c.get("after_unknown") is False and same(c.get("before_sensitive"), descriptor["sensitive"]) and same(c.get("after_sensitive"), descriptor["sensitive"]), "Output action/value/unknown/sensitivity differs")
    require(not W.unknown_paths(document.get("proposed_unknown", {}).get("outputs", {})), "Unknown output proposal")
    return {"status": "offline-paused-wiring56-to59-repair-passed", "priorManagedResources": 56, "managedResources": 59, "creates": 3, "noops": 56, "updates": 0, "deletes": 0, "fullPhysicalPriorEqual": True, "old56KnownNoops": True, "newProfilesAndUnknownMasksMatchOriginalActualPlan4": True, "policyChange": "omit-Resource-only-on-the-exact-repository", "rawStateSHA256": RAW_STATE_SHA, "serial": SERIAL, "lineage": LINEAGE, "applyAuthorized": False, "cloudPolicyCompatibilityVerified": False, "runtimeActivated": False, "normalRefreshInvocationAndBinaryProvenanceMustBeCheckedSeparately": True}


def read_pinned(path, expected):
    require(isinstance(path, Path) and path.is_absolute() and path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)) and isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected), "Actual regular input/hash required")
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == expected, "Input SHA differs")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", action="store_true")
    for key in ("plan-json", "physical-json", "original-plan-json", "raw-state"):
        parser.add_argument("--" + key, type=Path)
        parser.add_argument("--" + key + "-sha256")
    args = parser.parse_args()
    if not args.review:
        print(json.dumps({"status": "draft-inert", "filesRead": False, "cloudInvoked": False, "applyAuthorized": False}))
        return 0
    try:
        data = {key: read_pinned(getattr(args, key), getattr(args, key + "_sha256")) for key in ("plan_json", "physical_json", "original_plan_json", "raw_state")}
        report = inspect_plan(parsed(data["plan_json"]), parsed(data["physical_json"]), data["original_plan_json"], data["raw_state"])
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "blocked", "reason": str(error), "applyAuthorized": False}))
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
