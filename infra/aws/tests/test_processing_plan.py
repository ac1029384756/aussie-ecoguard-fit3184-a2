"""Independent existing-fixture deltas; no Terraform, ZIP, SDK or cloud calls."""
import contextlib
import copy
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

G = load("bounded_processing_gate", HERE.parent / "environments/personal/check_processing_plan.py")
F = load("approved_root_inventory_fixture", HERE / "test_paused_root_inventory_gate.py")
IMAGE, ZIP = F.FIXTURE.IMAGE, F.FIXTURE.ZIP


def runtime(active, adopted):
    return {"explicit": True, "function_concurrency": {n: (({"ingest": -1, "infer": -1, "outbox": -1}).get(n, 0) if active else 0) for n in
            ("api", "ingest", "infer", "delete", "notify", "outbox", "cleanup", "lex_fulfillment")},
            "media_data_enabled": active, "api_endpoint_enabled": False, "public_signup_enabled": False,
            "queue_consumers": ["infer", "ingest"] if active else [], "schedules": ["outbox"] if active else [],
            "manages_upload_notifications": adopted, "upload_notifications_enabled": active}


def outputs(active, adopted):
    vals = {"deployment_identity": {"account_id": "011154879765", "region": "us-east-1"},
            "execution_role_arn": "arn:aws:iam::011154879765:role/ecoguard3184-personal-lambda",
            "media_bucket": G.BUCKET, "api_url": "https://offline-fixture.invalid/api/v1",
            "cognito_user_pool_id": "fixture-pool", "cognito_client_id": "fixture-client",
            "worker_repository_url": IMAGE.split("@")[0], "runtime_enabled": False, "processing_enabled": active,
            "deployment_stage": "processing-bounded" if active else "wiring-paused", "runtime_controls": runtime(active, adopted)}
    return {k: {"sensitive": False, "type": "fixture-type-preserved", "value": v} for k, v in vals.items()}


def fixture(mode="activate-first"):
    wired, _ = F.fixture()
    physical = {"values": copy.deepcopy(wired["planned_values"])}
    physical["values"]["outputs"] = outputs(False, False)
    # The existing fixture models historical plan4. Current source45 repairs only
    # this Resource element; keep the historical fixture/checker untouched.
    policy_value = G.managed(physical["values"]["root_module"])[G.FOCUS.POLICY]
    repaired = json.loads(policy_value["policy"])
    del repaired["Statement"][0]["Resource"]
    policy_value["policy"] = json.dumps(repaired)
    if mode == "pause-adopted":
        active_doc, _ = fixture()
        physical = {"values": copy.deepcopy(active_doc["planned_values"])}
        G.managed(physical["values"]["root_module"])[G.NOTIFICATION]["id"] = G.BUCKET
    # State retains the caller read; native planned_values may omit it.
    caller = {"address": G.MODULE + "data.aws_caller_identity.current", "mode": "data", "type": "aws_caller_identity",
        "values": {"account_id": G.BASE.ACCOUNT, "id": G.BASE.ACCOUNT, "user_id": G.BASE.ACCOUNT,
                   "arn": f"arn:aws:iam::{G.BASE.ACCOUNT}:root"}}
    module_resources = physical["values"]["root_module"]["child_modules"][0]["resources"]
    module_resources[:] = [r for r in module_resources if r.get("mode") == "managed"] + [caller]
    active = mode == "activate-first"
    old = G.managed(physical["values"]["root_module"])
    planned = copy.deepcopy(physical["values"])
    planned["root_module"]["child_modules"][0]["resources"][:] = [r for r in planned["root_module"]["child_modules"][0]["resources"] if r.get("mode") == "managed"]
    future = G.managed(planned["root_module"])
    for name, count in {"ingest": -1, "infer": -1, "outbox": -1}.items():
        future[G.FUNCTIONS[name]]["reserved_concurrent_executions"] = count if active else 0
    for name in ("ingest", "infer"):
        future[G.MAPPINGS[name]].update(enabled=active, scaling_config=[{"maximum_concurrency": 2}] if active else [])
    future[G.RULES["outbox"]]["state"] = "ENABLED" if active else "DISABLED"
    paused_policy = F.policy_value()
    future[G.BUCKET_POLICY]["policy"] = json.dumps({"Version": "2012-10-17", "Statement": paused_policy["Statement"][:1]} if active else paused_policy)
    if active:
        value = {"bucket": G.BUCKET, "region": "us-east-1", "id": None, "eventbridge": False, "lambda_function": [], "topic": [],
            "queue": [{"id": "ecoguard3184-personal-incoming-ingest", "queue_arn": "arn:aws:sqs:us-east-1:011154879765:ecoguard3184-personal-ingest",
                       "events": ["s3:ObjectCreated:*"], "filter_prefix": "incoming/", "filter_suffix": ""}]}
        planned["root_module"]["child_modules"][0]["resources"].append({"address": G.NOTIFICATION, "mode": "managed", "type": "aws_s3_bucket_notification", "values": value})
        future = G.managed(planned["root_module"])
    else:
        future[G.NOTIFICATION]["queue"] = []
    planned["outputs"] = outputs(active, True)
    document = copy.deepcopy(wired)
    document.update(prior_state={"values": copy.deepcopy(physical["values"])}, planned_values=planned)
    document["variables"].update(deployment_stage={"value": "processing-bounded" if active else "wiring-paused"}, adopt_upload_notifications={"value": True})
    document["configuration"]["root_module"]["module_calls"]["ecoguard"]["expressions"]["manage_upload_notifications"] = {"references": ["var.adopt_upload_notifications"]}
    document["configuration"]["root_module"]["module_calls"]["ecoguard"]["expressions"]["allow_unreserved_processing_functions"] = {"references": ["var.deployment_stage"]}
    document["resource_changes"] = [{"address": a, "mode": "managed", "change": {
        "actions": ["create"] if a not in old else ["update"] if a in G.UPDATES or a == G.NOTIFICATION else ["no-op"],
        "before": copy.deepcopy(old.get(a)), "after": copy.deepcopy(v), "after_unknown": {"id": True} if a not in old else {}}} for a, v in future.items()]
    document["output_changes"] = {n: {"actions": ["update"] if n in ("deployment_stage", "processing_enabled", "runtime_controls") else ["no-op"],
        "before": copy.deepcopy(physical["values"]["outputs"][n]["value"]), "after": copy.deepcopy(v["value"]),
        "after_unknown": False, "before_sensitive": False, "after_sensitive": False} for n, v in planned["outputs"].items()}
    return document, physical


def quota_fixture():
    return {"recordType":"actual-read-only-lambda-quota-and-inventory", "accountId":G.BASE.ACCOUNT, "region":G.BASE.REGION,
        "observedAtUtc":"2026-10-24T05:00:00+00:00", "accountSettings":{"AccountLimit":{"ConcurrentExecutions":10,"UnreservedConcurrentExecutions":10},
        "AccountUsage":{"FunctionCount":8}}, "functionNames":sorted(G.PREFIX+"-"+name for name in G.FUNCTIONS), "listFunctionsComplete":True}


def review(d, p, mode="activate-first", window=300, quota=None):
    q=quota if quota is not None else quota_fixture()
    digest=hashlib.sha256(json.dumps(q,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    # Unit-only pin injection; no default synthetic record/pin enters the source gate.
    with mock.patch.object(G,"LIVE_QUOTA_EVIDENCE_SHA256",digest):
        return G.inspect_plan(d, p, mode=mode, image=IMAGE, zip_filename=ZIP, window_seconds=window,
            quota_evidence=q,quota_evidence_sha256=digest,review_time=datetime(2026,10,24,5,1,tzinfo=timezone.utc))


def change(d, a):
    return next(r["change"] for r in d["resource_changes"] if r["address"] == a)


def mutate(d, a, operation):
    operation(G.managed(d["planned_values"]["root_module"])[a])
    operation(change(d, a)["after"])


class ProcessingPlanTests(unittest.TestCase):
    def reject(self, d, p, mode="activate-first", window=300):
        with self.assertRaises((ValueError, TypeError, KeyError)):
            review(d, p, mode, window)

    def test_activation_and_adopted_pause_retain_sixty_and_have_no_apply_claim(self):
        for mode, expected in (("activate-first", (1, 7, 52)), ("pause-adopted", (0, 8, 52))):
            with self.subTest(mode=mode):
                d, p = fixture(mode); untouched = copy.deepcopy((d, p)); report = review(d, p, mode)
                self.assertEqual((report["creates"], report["updates"], report["noops"]), expected)
                self.assertEqual((d, p), untouched)
                self.assertEqual(len(G.managed(d["planned_values"]["root_module"])), 60)
                self.assertFalse(any(report[k] for k in ("applyAuthorized", "automaticFlowVerified", "timerCreated")))
        d, _ = fixture("pause-adopted")
        self.assertEqual(change(d, G.NOTIFICATION)["actions"], ["update"])
        self.assertEqual(change(d, G.NOTIFICATION)["after"]["queue"], [])

    def test_api_signup_notify_cleanup_and_wrong_concurrency_reject(self):
        cases = [(G.FUNCTIONS["api"], lambda v: v.update(reserved_concurrent_executions=1)),
            (G.FUNCTIONS["notify"], lambda v: v.update(reserved_concurrent_executions=1)),
            (G.FUNCTIONS["ingest"], lambda v: v.update(reserved_concurrent_executions=3)),
            (G.MAPPINGS["notify"], lambda v: v.update(enabled=True)),
            (G.MAPPINGS["infer"], lambda v: v.update(scaling_config=[{"maximum_concurrency": 3}])),
            (G.RULES["cleanup"], lambda v: v.update(state="ENABLED")),
            (G.MODULE + "aws_apigatewayv2_api.app[0]", lambda v: v.update(disable_execute_api_endpoint=False)),
            (G.MODULE + "aws_cognito_user_pool.users", lambda v: v.update(admin_create_user_config=[{"allow_admin_create_user_only": False}]))]
        for a, op in cases:
            with self.subTest(address=a):
                d, p = fixture(); mutate(d, a, op); self.reject(d, p)

    def test_notification_scope_adoption_and_pause_retention_are_exact(self):
        for key, value in (("filter_prefix", ""), ("filter_prefix", "uploads/"), ("filter_suffix", ".jpg"),
                           ("queue_arn", "arn:aws:sqs:us-east-1:011154879765:other"), ("events", ["s3:ObjectRemoved:*"])):
            with self.subTest(key=key, value=value):
                d, p = fixture(); mutate(d, G.NOTIFICATION, lambda v: v["queue"][0].update({key: value})); self.reject(d, p)
        d, p = fixture(); mutate(d, G.NOTIFICATION, lambda v: v.update(topic=[{"topic_arn": "other"}])); self.reject(d, p)
        d, p = fixture(); change(d, G.NOTIFICATION)["after_unknown"] = {"id": 1}; self.reject(d, p)
        d, p = fixture(); d["variables"]["adopt_upload_notifications"]["value"] = False; self.reject(d, p)
        d, p = fixture("pause-adopted"); change(d, G.NOTIFICATION)["actions"] = ["delete"]; self.reject(d, p, "pause-adopted")

    def test_nonruntime_values_and_complete_prior_stay_exact(self):
        for a, op in ((G.WIRING.ROLE_POLICY, lambda v: v.update(policy="{}")),
            (G.FUNCTIONS["infer"], lambda v: v.update(filename="/other.zip")),
            (G.FUNCTIONS["ingest"], lambda v: v.update(image_uri=IMAGE + "0")),
            (G.MAPPINGS["ingest"], lambda v: v.update(batch_size=2)),
            (G.RULES["outbox"], lambda v: v.update(schedule_expression="rate(5 minutes)")),
            (G.MODULE + "aws_s3_bucket_public_access_block.media", lambda v: v.update(block_public_policy=False))):
            with self.subTest(address=a):
                d, p = fixture(); mutate(d, a, op); self.reject(d, p)
        d, p = fixture(); G.managed(p["values"]["root_module"])[G.FUNCTIONS["api"]]["memory_size"] = 1024; self.reject(d, p)
        d, p = fixture(); d["resource_drift"] = [{"address": G.BUCKET_POLICY}]; self.reject(d, p)

    def test_unknown_security_rejects_only_named_readonly_projection_passes(self):
        for a, key in ((G.FUNCTIONS["ingest"], "environment"), (G.FUNCTIONS["infer"], "role"),
            (G.MAPPINGS["infer"], "enabled"), (G.NOTIFICATION, "queue"), (G.BUCKET_POLICY, "policy")):
            with self.subTest(key=key):
                d, p = fixture(); change(d, a)["after_unknown"] = {key: True}; mutate(d, a, lambda v: v.update({key: None})); self.reject(d, p)
        d, p = fixture(); a = G.FUNCTIONS["infer"]
        change(d, a)["after_unknown"] = {"last_modified": True}; mutate(d, a, lambda v: v.update(last_modified=None)); review(d, p)
        change(d, a)["after_unknown"] = {"last_modified": {"nested": True}}; self.reject(d, p)

    def test_policy_cannot_gain_allow_and_pause_restores_exact_root_form(self):
        for mode in ("activate-first", "pause-adopted"):
            d, p = fixture(mode); policy = json.loads(change(d, G.BUCKET_POLICY)["after"]["policy"])
            policy["Statement"].append({"Effect": "Allow", "Principal": "*", "Action": "s3:*", "Resource": "*"})
            mutate(d, G.BUCKET_POLICY, lambda v: v.update(policy=json.dumps(policy))); self.reject(d, p, mode)

    def test_actions_data_outputs_and_window_cannot_escape_exact_scope(self):
        d, p = fixture(); d["action_invocations"] = [{"address": "action.test"}]; self.reject(d, p)
        d, p = fixture(); d["resource_changes"].append({"address": "data.external.other", "mode": "data", "type": "external", "change": {"actions": ["read"], "after": {}}}); self.reject(d, p)
        d, p = fixture(); d["planned_values"]["outputs"]["runtime_enabled"]["value"] = True; self.reject(d, p)
        d, p = fixture(); d["output_changes"]["runtime_controls"]["after_unknown"] = True; self.reject(d, p)
        d, p = fixture(); d["configuration"]["root_module"]["module_calls"]["ecoguard"]["expressions"]["runtime_enabled"] = {"constant_value": True}; self.reject(d, p)
        for window in (0, 601, True, None):
            d, p = fixture(); self.reject(d, p, window=window)
        d, p = fixture(); self.reject(d, p, mode="media-manual")

    def test_exact_state_caller_and_absent_planned_data_are_not_optional(self):
        d, p = fixture()
        caller = next(r for r in G.BASE.resources(p["values"]["root_module"]) if r.get("mode") == "data")
        self.assertEqual(len(caller["values"]), 4)
        self.assertFalse(any(r.get("mode") != "managed" for r in G.BASE.resources(d["planned_values"]["root_module"])))
        for kind in ("planned-caller", "caller-change", "missing-user", "wrong-user", "extra-value", "missing-caller"):
            d, p = fixture()
            with self.subTest(kind=kind):
                if kind == "planned-caller":
                    d["planned_values"]["root_module"]["child_modules"][0]["resources"].append(copy.deepcopy(caller))
                elif kind == "caller-change":
                    d["resource_changes"].append({**copy.deepcopy(caller), "change": {"actions": ["no-op"], "after": copy.deepcopy(caller["values"]), "after_unknown": {}}})
                else:
                    for root in (p["values"]["root_module"], d["prior_state"]["values"]["root_module"]):
                        resources = root["child_modules"][0]["resources"]
                        row = next(r for r in resources if r.get("mode") == "data")
                        if kind == "missing-caller": resources.remove(row)
                        elif kind == "missing-user": del row["values"]["user_id"]
                        elif kind == "wrong-user": row["values"]["user_id"] = "role-session"
                        else: row["values"]["extra"] = True
                self.reject(d, p)

    def test_repaired_ecr_policy_exact_and_historical_checker_unchanged(self):
        d, p = fixture()
        value = G.managed(p["values"]["root_module"])[G.FOCUS.POLICY]
        policy = json.loads(value["policy"])
        self.assertNotIn("Resource", policy["Statement"][0])
        self.assertTrue(G.repaired_ecr_policy_is_scoped(value["policy"]))
        self.assertFalse(G.FOCUS.policy_exact(value["policy"]))
        review(d, p)
        for key, replacement in (("Resource", G.FOCUS.REPOSITORY_ARN), ("Resource", "*"),
                ("Principal", {"Service": "*"}), ("Action", ["ecr:*"]),
                ("Condition", {}), ("Condition", {"ArnLike": {"aws:SourceArn": G.FOCUS.INGEST_ARN + "*"},
                    "StringEquals": {"aws:SourceAccount": G.BASE.ACCOUNT}}),
                ("Condition", {"ArnEquals": {"aws:SourceArn": G.FOCUS.INGEST_ARN + "-other"},
                    "StringEquals": {"aws:SourceAccount": G.BASE.ACCOUNT}}),
                ("Condition", {"ArnEquals": {"aws:SourceArn": G.FOCUS.INGEST_ARN},
                    "StringEquals": {"aws:SourceAccount": "999999999999"}})):
            with self.subTest(key=key, replacement=replacement):
                d, p = fixture(); altered = copy.deepcopy(policy)
                altered["Statement"][0][key] = replacement
                mutate(d, G.FOCUS.POLICY, lambda v: v.update(policy=json.dumps(altered)))
                self.reject(d, p)
        d, p = fixture(); mutate(d, G.FOCUS.POLICY, lambda v: v.update(repository="other")); self.reject(d, p)

    def test_low_quota_unreserved_profile_pin_freshness_inventory_and_pause(self):
        d,p=fixture();report=review(d,p)
        self.assertFalse(report["outboxReservationCapOne"])
        self.assertEqual(report["lowQuotaEvidence"]["existingFunctionCount"],8)
        for kind in ("count7","quota","unreserved","incomplete","otherfunction","stale","future","boolquota"):
            q=quota_fixture()
            if kind=="count7":q["accountSettings"]["AccountUsage"]["FunctionCount"]=7
            elif kind=="quota":q["accountSettings"]["AccountLimit"]["ConcurrentExecutions"]=1000
            elif kind=="unreserved":q["accountSettings"]["AccountLimit"]["UnreservedConcurrentExecutions"]=9
            elif kind=="incomplete":q["listFunctionsComplete"]=False
            elif kind=="otherfunction":q["functionNames"][-1]="unrelated"
            elif kind=="stale":q["observedAtUtc"]="2026-10-24T04:00:00+00:00"
            elif kind=="future":q["observedAtUtc"]="2026-10-24T06:00:00+00:00"
            else:q["accountSettings"]["AccountLimit"]["ConcurrentExecutions"]=True
            with self.subTest(kind=kind),self.assertRaises(ValueError):review(d,p,quota=q)
        with self.assertRaisesRegex(ValueError,"unbound"):
            G.inspect_plan(d,p,mode="activate-first",image=IMAGE,zip_filename=ZIP,window_seconds=300,quota_evidence=quota_fixture())
        for a in (G.FUNCTIONS["ingest"],G.FUNCTIONS["infer"],G.FUNCTIONS["outbox"]):
            d,p=fixture();mutate(d,a,lambda v:v.update(reserved_concurrent_executions=2))
            self.reject(d,p)
        d,p=fixture("pause-adopted")
        report=G.inspect_plan(d,p,mode="pause-adopted",image=IMAGE,zip_filename=ZIP,window_seconds=300)
        self.assertTrue(report["pauseDoesNotRequireQuotaEvidence"]);self.assertIsNone(report["lowQuotaEvidence"])
        with mock.patch.object(sys,"argv",["gate","--review","--mode","activate-first"]), mock.patch.object(Path,"read_bytes",side_effect=AssertionError("no synthetic/default read")), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(G.main(),1)
        self.assertEqual(json.loads(out.getvalue())["status"],"blocked")

    def test_cli_default_reads_no_input(self):
        with mock.patch.object(sys, "argv", ["check"]), mock.patch.object(Path, "read_bytes", side_effect=AssertionError("No file read")), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(G.main(), 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "dry-run")


if __name__ == "__main__":
    unittest.main()
