"""Offline mutations of the approved root-only paused inventory exception."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIXTURE = load("root_inventory_increment_fixture", HERE / "test_staged_increment_plan.py")
FULL = FIXTURE.G
FOCUS = FULL.FOCUS
BASE = FULL.BASE
POLICY = FULL.MODULE + "aws_s3_bucket_policy.media_tls"
ROOT_ARN = f"arn:aws:iam::{FULL.ACCOUNT}:root"
INPUT = "allow_root_bucket_inventory_while_paused"


def module_input(document):
    return document["configuration"]["root_module"]["module_calls"]["ecoguard"]["expressions"]


def policy_value():
    legacy = FIXTURE.F.plan_fixture()
    value = json.loads(FIXTURE.F.value(legacy, "aws_s3_bucket_policy.media_tls")["policy"])
    value["Statement"][1]["Action"].remove("s3:ListBucket")
    value["Statement"].append({
        "Sid": "DenyBucketListingWhileRuntimePaused", "Effect": "Deny", "Principal": "*",
        "Action": ["s3:ListBucket"], "Resource": [f"arn:aws:s3:::{BASE.BUCKET}"],
        "Condition": {"ArnNotEquals": {"aws:PrincipalArn": ROOT_ARN}}})
    return value


def fixture(policy=None):
    document, physical = FIXTURE.fixture()
    encoded = json.dumps(policy if policy is not None else policy_value())
    for root in (document["planned_values"]["root_module"], document["prior_state"]["values"]["root_module"],
                 physical["values"]["root_module"]):
        for row in BASE.resources(root):
            if row["address"] == POLICY:
                row["values"]["policy"] = encoded
            if row.get("type") == "aws_caller_identity":
                row["values"]["arn"] = ROOT_ARN
    FIXTURE.change(document, POLICY).update(before=copy.deepcopy(FIXTURE.table(document["prior_state"]["values"])[POLICY]),
        after=copy.deepcopy(FIXTURE.table(document["planned_values"])[POLICY]))
    module_input(document)[INPUT] = {"constant_value": True}
    return document, physical


def review(document, physical, **kwargs):
    return FULL.inspect_plan(document, physical, image=FIXTURE.IMAGE, zip_sha=FULL.ZIP_SHA,
        zip_filename=FIXTURE.ZIP, run_url=FULL.RUN_URL, wif=copy.deepcopy(FIXTURE.WIF), **kwargs)


class RootInventoryGateTests(unittest.TestCase):
    def rejected(self, document, physical, **kwargs):
        with self.assertRaises((ValueError, KeyError, TypeError)):
            review(document, physical, root_inventory_while_paused=True, **kwargs)

    def test_legacy_default_and_historical_first_gate_remain_unchanged(self):
        self.assertEqual(review(*FIXTURE.fixture())["status"], "offline-paused-wiring-increment-passed")
        self.assertEqual(BASE.inspect_plan(FIXTURE.F.plan_fixture())["status"], "offline-first-plan-passed")
        document, physical = fixture()
        with self.assertRaises(ValueError):
            review(document, physical)
        # The historical first-plan entry point has no implicit new-policy mode.
        first = FIXTURE.F.plan_fixture()
        FIXTURE.F.value(first, "aws_s3_bucket_policy.media_tls")["policy"] = json.dumps(policy_value())
        self.assertEqual(BASE.inspect_plan(first)["status"], "blocked")

    def test_only_the_two_singleton_fields_accept_each_aws_form(self):
        for scalar_action in (False, True):
            for scalar_resource in (False, True):
                with self.subTest(action=scalar_action, resource=scalar_resource):
                    policy = policy_value()
                    listing = policy["Statement"][2]
                    if scalar_action:
                        listing["Action"] = listing["Action"][0]
                    if scalar_resource:
                        listing["Resource"] = listing["Resource"][0]
                    document, physical = fixture(policy)
                    report = review(document, physical, root_inventory_while_paused=True)
                    self.assertTrue(report["rootInventoryWhilePausedReviewed"])
                    self.assertEqual((report["creates"], report["updates"], report["noops"]), (4, 8, 47))
                    self.assertTrue(report["physicalPriorFullyEqual"])
                    self.assertFalse(report["applyAuthorized"])
                    self.assertFalse(report["cloudVerified"])

    def test_opt_in_requires_exact_constant_true_without_references(self):
        cases = [None, {}, {"constant_value": False}, {"constant_value": 1}, {"constant_value": None},
                 {"constant_value": "true"}, {"references": ["var.allow_inventory"]},
                 {"constant_value": True, "references": ["var.allow_inventory"]},
                 {"constant_value": True, "unknown": True}]
        for expression in cases:
            with self.subTest(expression=expression):
                document, physical = fixture()
                if expression is None:
                    module_input(document).pop(INPUT)
                else:
                    module_input(document)[INPUT] = expression
                self.rejected(document, physical)

    def test_truthy_or_unknown_api_flags_cannot_enable_review(self):
        for flag in (None, 1, "true", {"unknown": True}, [True]):
            with self.subTest(flag=flag):
                document, physical = fixture()
                with self.assertRaises(ValueError):
                    review(document, physical, root_inventory_while_paused=flag)
                with self.assertRaises(ValueError):
                    FOCUS.inspect_plan(document, FIXTURE.IMAGE, root_inventory_while_paused=flag)
                with self.assertRaises(ValueError):
                    BASE.inspect_bucket_security(lambda _: {}, lambda *_: None, root_inventory_while_paused=flag)

    def test_caller_must_be_exact_root_in_every_known_observation(self):
        for arn in (None, "*", f"arn:aws:iam::{FULL.ACCOUNT}:role/operator",
                    f"arn:aws:iam::{FULL.ACCOUNT}:user/operator", "arn:aws:iam::360493183467:root"):
            for location in ("prior", "planned"):
                with self.subTest(arn=arn, location=location):
                    document, physical = fixture()
                    root = document["planned_values"]["root_module"] if location == "planned" else document["prior_state"]["values"]["root_module"]
                    next(r["values"] for r in BASE.resources(root) if r.get("type") == "aws_caller_identity")["arn"] = arn
                    self.rejected(document, physical)

    def test_unknown_or_inconsistent_caller_change_fails(self):
        for kind in ("unknown", "inconsistent"):
            with self.subTest(kind=kind):
                document, physical = fixture()
                change = {"actions": ["read"], "after": {"account_id": FULL.ACCOUNT, "arn": ROOT_ARN}, "after_unknown": {}}
                if kind == "unknown":
                    change["after_unknown"] = {"arn": True}
                else:
                    change["after"]["arn"] = f"arn:aws:iam::{FULL.ACCOUNT}:role/operator"
                document["resource_changes"].append({"address": FULL.MODULE + "data.aws_caller_identity.current",
                    "type": "aws_caller_identity", "mode": "data", "change": change})
                self.rejected(document, physical)

    def test_broader_principals_actions_resources_or_conditions_fail(self):
        mutations = [
            lambda p: p["Statement"][2]["Condition"]["ArnNotEquals"].update({"aws:PrincipalArn": "*"}),
            lambda p: p["Statement"][2]["Condition"].update(ArnNotLike={"aws:PrincipalArn": f"arn:aws:iam::{FULL.ACCOUNT}:*"}),
            lambda p: p["Statement"][2]["Condition"]["ArnNotEquals"].update({"aws:PrincipalArn": f"arn:aws:iam::{FULL.ACCOUNT}:role/operator"}),
            lambda p: p["Statement"][2].update(Principal={"AWS": ROOT_ARN}),
            lambda p: p["Statement"][2].update(Action="s3:List*"),
            lambda p: p["Statement"][2]["Action"].append("s3:ListBucketVersions"),
            lambda p: p["Statement"][2]["Resource"].append(f"arn:aws:s3:::{BASE.BUCKET}/*"),
            lambda p: p["Statement"][2].update(Effect="Allow"),
            lambda p: p["Statement"][2].update(NotPrincipal={"AWS": ROOT_ARN}),
            lambda p: p["Statement"][2]["Condition"]["ArnNotEquals"].update({"aws:PrincipalAccount": FULL.ACCOUNT}),
            lambda p: p["Statement"][1].update(Condition={"ArnNotEquals": {"aws:PrincipalArn": ROOT_ARN}}),
        ]
        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=index):
                policy = policy_value()
                mutation(policy)
                self.rejected(*fixture(policy))

    def test_each_of_eight_unconditional_data_denies_and_tls_is_retained(self):
        for action in policy_value()["Statement"][1]["Action"]:
            with self.subTest(missing=action):
                policy = policy_value()
                policy["Statement"][1]["Action"].remove(action)
                self.rejected(*fixture(policy))
        for mutation in (lambda p: p["Statement"][0]["Resource"].pop(),
                         lambda p: p["Statement"][0]["Condition"]["Bool"].update({"aws:SecureTransport": "true"}),
                         lambda p: p["Statement"][0].update(Action=["s3:*"])):
            policy = policy_value()
            mutation(policy)
            self.rejected(*fixture(policy))

    def test_extra_statement_unknown_keys_and_other_representation_changes_fail(self):
        mutations = [lambda p: p.update(Id="unreviewed"),
            lambda p: p["Statement"].append({"Effect": "Allow", "Principal": "*", "Action": "s3:*", "Resource": "*"}),
            lambda p: p["Statement"].pop(1),
            lambda p: p["Statement"][0].update(NotAction="s3:DeleteBucket"),
            lambda p: p["Statement"][1].update(Condition={}),
            lambda p: p["Statement"][2].update(extra="unknown"),
            lambda p: p["Statement"][2]["Action"].append("s3:ListBucket"),
            lambda p: p["Statement"][1]["Action"].reverse(),
            lambda p: p["Statement"].reverse()]
        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=index):
                policy = policy_value()
                mutation(policy)
                self.rejected(*fixture(policy))

    def test_opt_in_does_not_skip_full_physical_or_unknown_value_checks(self):
        for kind in ("physical", "unknown", "activation"):
            with self.subTest(kind=kind):
                document, physical = fixture()
                if kind == "physical":
                    FULL.values(physical)[POLICY]["policy"] = json.dumps(policy_value(), indent=2)
                elif kind == "unknown":
                    FIXTURE.change(document, POLICY)["after_unknown"] = {"policy": True}
                else:
                    FIXTURE.mutate(document, FULL.MODULE + 'aws_lambda_function.zip["api"]',
                        lambda v: v.update(reserved_concurrent_executions=1))
                self.rejected(document, physical)

    def test_both_increment_clis_require_the_explicit_flag(self):
        document, physical = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan, state, wif = (root / name for name in ("plan.json", "physical.json", "wif.json"))
            plan.write_text(json.dumps(document))
            state.write_text(json.dumps(physical))
            wif.write_text(json.dumps(FIXTURE.WIF))
            cases = [(FOCUS, ["gate", "--plan-json", str(plan), "--image", FIXTURE.IMAGE]),
                (FULL, ["gate", "--plan-json", str(plan), "--physical-json", str(state), "--wif", str(wif),
                    "--image", FIXTURE.IMAGE, "--zip-sha256", FULL.ZIP_SHA, "--zip-filename", FIXTURE.ZIP,
                    "--run-url", FULL.RUN_URL])]
            for gate, argv in cases:
                for opted_in in (False, True):
                    with self.subTest(gate=gate.__name__, opted_in=opted_in):
                        output = io.StringIO()
                        with mock.patch.object(sys, "argv", argv + (["--root-inventory-while-paused"] if opted_in else [])), contextlib.redirect_stdout(output):
                            self.assertEqual(gate.main(), 0 if opted_in else 1)
                        self.assertEqual(json.loads(output.getvalue())["status"],
                            ("offline-paused-wiring-increment-passed" if gate is FULL else "focused-ecr-policy-paused-profile-passed") if opted_in else "blocked")


if __name__ == "__main__":
    unittest.main()
