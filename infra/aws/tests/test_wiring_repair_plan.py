"""Focused policy/change-boundary tests; no native-plan success is simulated."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

PATH = Path(__file__).resolve().parents[1] / "environments/personal/check_wiring_repair_plan.py"
SPEC = importlib.util.spec_from_file_location("repair_gate_test", PATH)
G = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(G)


class RepairBoundaryTests(unittest.TestCase):
    def policies(self):
        original = G.F.expected_policy()
        target = copy.deepcopy(original)
        del target["Statement"][0]["Resource"]
        return original, target

    def test_only_resource_omission_preserves_function_account_principal_actions(self):
        original, target = self.policies()
        self.assertEqual(G.omitted_policy(original, target), target)
        mutations = [lambda p: p["Statement"][0].update(Resource="*"),
            lambda p: p["Statement"][0]["Action"].append("ecr:PutImage"),
            lambda p: p["Statement"][0].update(Principal="*"),
            lambda p: p["Statement"][0]["Condition"]["ArnEquals"].update({"aws:SourceArn": "arn:aws:lambda:us-east-1:011154879765:function:*"}),
            lambda p: p["Statement"][0]["Condition"].pop("StringEquals"),
            lambda p: p["Statement"].append(copy.deepcopy(p["Statement"][0]))]
        for mutation in mutations:
            value = copy.deepcopy(target); mutation(value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                G.omitted_policy(original, value)

    def test_existing_values_must_be_typed_known_noops(self):
        value = {"enabled": False, "timeout": 120, "policy": "unchanged"}
        row = {"change": {"actions": ["no-op"], "before": copy.deepcopy(value), "after": copy.deepcopy(value), "after_unknown": {}}}
        G.unchanged(row, value, copy.deepcopy(value))
        for mutate in (lambda r: r["change"]["after"].update(enabled=0),
                       lambda r: r["change"].update(after_unknown={"policy": True}),
                       lambda r: r["change"].update(actions=["update"]),
                       lambda r: r["change"].update(importing={"id": "unreviewed"})):
            candidate = copy.deepcopy(row); mutate(candidate)
            with self.assertRaises(ValueError):
                G.unchanged(candidate, value, candidate["change"]["after"])

    def test_new_policy_profile_and_unknown_mask_stay_original(self):
        original, target = self.policies()
        old_values = {"policy": json.dumps(original), "repository": G.F.REPOSITORY, "region": G.B.REGION, "id": None, "registry_id": None}
        values = {**old_values, "policy": json.dumps(target)}
        original_row = {"change": {"actions": ["create"], "before": None, "after": copy.deepcopy(old_values), "after_unknown": {"id": True, "registry_id": True}, "after_sensitive": {}}}
        row = copy.deepcopy(original_row); row["change"]["after"] = copy.deepcopy(values)
        image = "011154879765.dkr.ecr.us-east-1.amazonaws.com/ecoguard3184-personal-worker@sha256:" + "0" * 64
        G.created(G.F.POLICY, row, values, original_row, old_values, image)
        for kind in ("repository", "region", "unknown"):
            candidate = copy.deepcopy(row)
            if kind == "unknown": candidate["change"]["after_unknown"]["policy"] = True
            else: candidate["change"]["after"][kind] = "other"
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                G.created(G.F.POLICY, candidate, candidate["change"]["after"], original_row, old_values, image)

    def test_default_is_inert_and_duplicate_policy_keys_are_rejected(self):
        with mock.patch.object(sys, "argv", ["check"]), mock.patch.object(Path, "read_bytes", side_effect=AssertionError("no input read")), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(G.main(), 0)
        self.assertFalse(json.loads(output.getvalue())["filesRead"])
        with self.assertRaises(ValueError): G.parsed('{"Version":"a","Version":"b"}')

    def test_each_unknown_representation_must_match_its_original_counterpart(self):
        original, target = self.policies()
        old_after = {"policy": json.dumps(original), "repository": G.F.REPOSITORY, "id": None, "registry_id": None}
        old_future = {k: v for k, v in old_after.items() if k not in ("id", "registry_id")}
        after = {**old_after, "policy": json.dumps(target)}
        future = {**old_future, "policy": json.dumps(target)}
        original_row = {"change": {"actions": ["create"], "before": None, "after": old_after, "after_unknown": {"id": True, "registry_id": True}, "after_sensitive": {}}}
        row = copy.deepcopy(original_row); row["change"]["after"] = after
        image = "011154879765.dkr.ecr.us-east-1.amazonaws.com/ecoguard3184-personal-worker@sha256:" + "0" * 64
        G.created(G.F.POLICY, row, future, original_row, old_future, image)
        wrong_future = {**future, "id": None}
        with self.assertRaises(ValueError): G.created(G.F.POLICY, row, wrong_future, original_row, old_future, image)
        wrong_after = copy.deepcopy(row); del wrong_after["change"]["after"]["id"]
        with self.assertRaises(ValueError): G.created(G.F.POLICY, wrong_after, future, original_row, old_future, image)


if __name__ == "__main__":
    unittest.main()
