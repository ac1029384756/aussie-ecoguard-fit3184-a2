"""Synthetic first-plan guard regressions; no cloud/real saved plan evidence."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "gcp_personal_plan", Path(__file__).parents[1] / "environments/personal/check_plan.py")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


def fixture_plan():
    values = {
        "google_service_account.invoker": {"project": CHECKER.PROJECT, "account_id": CHECKER.SA_ID},
        "google_iam_workload_identity_pool.aws": {
            "project": CHECKER.PROJECT, "workload_identity_pool_id": CHECKER.POOL_ID},
        "google_iam_workload_identity_pool_provider.aws": {
            "project": CHECKER.PROJECT, "workload_identity_pool_id": CHECKER.POOL_ID,
            "workload_identity_pool_provider_id": "aws-role", "aws": [{"account_id": CHECKER.AWS_ACCOUNT}],
            "attribute_mapping": copy.deepcopy(CHECKER.MAPPING), "attribute_condition": CHECKER.CONDITION,
        },
        "google_service_account_iam_member.aws_invoker": {
            "service_account_id": CHECKER.SA_NAME, "member": CHECKER.PRINCIPAL,
            "role": "roles/iam.workloadIdentityUser",
        },
    }
    for service in CHECKER.APIS:
        values[f'google_project_service.required["{service}"]'] = {
            "project": CHECKER.PROJECT, "service": service, "disable_on_destroy": False}
    managed = [{"address": CHECKER.MODULE + address, "mode": "managed", "values": value}
               for address, value in values.items()]
    return {
        "format_version": "1.2", "complete": True, "errored": False,
        "configuration": {"root_module": {"module_calls": {"ecoguard": {
            "source": "../..", "expressions": {
                key: {"constant_value": value} for key, value in CHECKER.ROOT_INPUTS.items()}}}}},
        "planned_values": {"root_module": {"child_modules": [{"address": "module.ecoguard", "resources": [
            *managed, {"address": CHECKER.MODULE + "data.google_project.current", "mode": "data",
                       "type": "google_project", "values": {
                           "project_id": CHECKER.PROJECT, "number": CHECKER.PROJECT_NUMBER}},
        ]}]}},
        "resource_changes": [{"address": r["address"], "mode": "managed",
                              "change": {"actions": ["create"], "before": None}} for r in managed],
    }


class PersonalIdentityPlanTests(unittest.TestCase):
    def setUp(self):
        self.plan = fixture_plan()

    def inspect(self):
        return CHECKER.inspect_plan(self.plan)

    def value(self, suffix):
        return next(r["values"] for r in self.plan["planned_values"]["root_module"]["child_modules"][0]["resources"]
                    if r["address"] == CHECKER.MODULE + suffix)

    def assert_blocked(self):
        self.assertEqual(self.inspect()["status"], "blocked")

    def test_exact_first_identity_plan_passes_without_cloud_claim(self):
        report = self.inspect()
        self.assertEqual(report["status"], "offline-first-identity-plan-passed")
        self.assertEqual(report["managedResources"], 7)
        self.assertTrue(all(check["passed"] for check in report["checks"]))
        self.assertFalse(report["cloudVerified"])
        self.assertFalse(report["awsRoleVerified"])
        self.assertFalse(report["applyAuthorized"])

    def test_fixed_scope_cannot_be_overridden_or_left_to_child_defaults(self):
        expressions = self.plan["configuration"]["root_module"]["module_calls"]["ecoguard"]["expressions"]
        for key in CHECKER.ROOT_INPUTS:
            original = expressions.pop(key)
            with self.subTest(key=key):
                self.assert_blocked()
            expressions[key] = original
        for key, value in (("identity_only", False), ("project_id", "ecoguard-fit3184-jlii0474"),
                           ("aws_role_name", "LabRole"), ("image", "image:latest"),
                           ("inference_environment", {"SERVICE_AUTH_MODE": "none"})):
            original = expressions[key]
            expressions[key] = {"constant_value": value}
            with self.subTest(key=key):
                self.assert_blocked()
            expressions[key] = original

    def test_project_id_and_number_must_both_match(self):
        project = self.value("data.google_project.current")
        for key, value in (("project_id", "ecoguard-fit3184-jlii0474"), ("number", "1086936100292")):
            original = project[key]
            project[key] = value
            with self.subTest(key=key):
                self.assert_blocked()
            project[key] = original

    def test_api_and_identity_resources_cannot_target_another_project(self):
        for resource in self.plan["planned_values"]["root_module"]["child_modules"][0]["resources"]:
            values = resource["values"]
            if resource["mode"] == "managed" and "project" in values:
                values["project"] = "other-project"
                with self.subTest(address=resource["address"]):
                    self.assert_blocked()
                values["project"] = CHECKER.PROJECT

    def test_trust_cannot_broaden_account_role_or_mapping(self):
        provider = self.value("google_iam_workload_identity_pool_provider.aws")
        for key, value in (("aws", [{"account_id": "360493183467"}]), ("attribute_condition", "true"),
                           ("attribute_condition", f"assertion.account == '{CHECKER.AWS_ACCOUNT}'"),
                           ("attribute_mapping", {"google.subject": "assertion.arn", "attribute.aws_role": "'anything'"})):
            original = provider[key]
            provider[key] = value
            with self.subTest(key=key, value=value):
                self.assert_blocked()
            provider[key] = original

    def test_iam_role_principal_and_target_require_exact_known_values(self):
        grant = self.value("google_service_account_iam_member.aws_invoker")
        for key, value in (("member", "allUsers"), ("member", None), ("role", "roles/owner"),
                           ("member", f"principalSet://iam.googleapis.com/{CHECKER.POOL_NAME}/*"),
                           ("service_account_id", None), ("service_account_id", "projects/other/serviceAccounts/other@example.com")):
            original = grant[key]
            grant[key] = value
            with self.subTest(key=key, value=value):
                self.assert_blocked()
            grant[key] = original

    def test_prior_state_import_update_delete_and_replacement_are_rejected(self):
        change = self.plan["resource_changes"][0]["change"]
        for actions in (["no-op"], ["update"], ["delete"], ["delete", "create"]):
            change["actions"] = actions
            with self.subTest(actions=actions):
                self.assert_blocked()
        change["actions"] = ["create"]
        change["importing"] = {"id": "existing"}
        self.assert_blocked()
        del change["importing"]
        self.plan["prior_state"] = {"values": {"root_module": {"resources": [
            {"address": "google_service_account.old", "mode": "managed"}]}}}
        self.assert_blocked()

    def test_extra_compute_or_iam_and_incomplete_plan_are_rejected(self):
        resources = self.plan["planned_values"]["root_module"]["child_modules"][0]["resources"]
        for kind in ("google_cloud_run_v2_service", "google_project_iam_member"):
            resources.append({"address": CHECKER.MODULE + kind + ".extra", "mode": "managed", "values": {}})
            with self.subTest(kind=kind):
                self.assert_blocked()
            resources.pop()
        self.plan["complete"] = False
        self.assert_blocked()

    def test_manifest_drift_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.locked.json"
            path.write_bytes(CHECKER.MANIFEST.read_bytes() + b"\n")
            self.assertEqual(CHECKER.inspect_plan(self.plan, manifest_path=path)["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
