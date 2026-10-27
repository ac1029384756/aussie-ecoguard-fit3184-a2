"""Synthetic incremental-plan regressions; no cloud or real saved-plan claims."""
import contextlib
import copy
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

TESTS = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GATE = load("gcp_personal_runtime_gate", TESTS.parent / "environments/personal/check_runtime_plan.py")
FIRST = load("gcp_personal_identity_fixture", TESTS / "test_personal_plan.py")
IMAGE = GATE.REGISTRY + "/inference@sha256:" + "a" * 64  # Synthetic digest only.


def managed_resource(suffix, values):
    return {"address": GATE.MODULE + suffix, "mode": "managed",
            "type": suffix.split(".", 1)[0], "values": copy.deepcopy(values)}


def fixture_plan(stage):
    first = FIRST.fixture_plan()
    base = copy.deepcopy(first["planned_values"]["root_module"]["child_modules"][0]["resources"])
    for resource in base:
        if resource["mode"] == "managed":
            resource["type"] = resource["address"][len(GATE.MODULE):].split(".", 1)[0]
        if resource["address"] in {
            GATE.MODULE + "google_service_account.invoker",
            GATE.MODULE + "google_iam_workload_identity_pool.aws",
            GATE.MODULE + "google_iam_workload_identity_pool_provider.aws",
        }:
            resource["values"]["disabled"] = False
    registry = [
        managed_resource(GATE.REGISTRY_API, {"project": GATE.PROJECT,
            "service": "artifactregistry.googleapis.com", "disable_on_destroy": False}),
        managed_resource(GATE.REPOSITORY, {"project": GATE.PROJECT, "location": GATE.IDENTITY.REGION,
            "repository_id": "ecoguard", "format": "DOCKER", "mode": "STANDARD_REPOSITORY"}),
    ]
    runtime = [
        managed_resource(GATE.RUN_API, {"project": GATE.PROJECT,
            "service": "run.googleapis.com", "disable_on_destroy": False}),
        managed_resource(GATE.RUNTIME, {"project": GATE.PROJECT,
            "account_id": "ecoguard-inference", "disabled": False}),
        managed_resource(GATE.SERVICE, {
            "project": GATE.PROJECT, "location": GATE.IDENTITY.REGION,
            "name": "ecoguard-inference", "ingress": "INGRESS_TRAFFIC_ALL",
            "deletion_protection": False, "invoker_iam_disabled": False,
            "scaling": [{"scaling_mode": "AUTOMATIC", "min_instance_count": 0,
                         "max_instance_count": 1, "manual_instance_count": 0}],
            "template": [{"service_account": GATE.RUNTIME_EMAIL, "timeout": "360s",
                "max_instance_request_concurrency": 1,
                "scaling": [{"min_instance_count": 0, "max_instance_count": 1}],
                "containers": [{"image": IMAGE, "ports": [{"name": "http1", "container_port": 8080}],
                    "resources": [{"limits": {"cpu": "4", "memory": "8Gi"},
                        "cpu_idle": True, "startup_cpu_boost": True}],
                    "env": [{"name": name, "value": value}
                            for name, value in sorted(GATE.RUNTIME_ENV.items())]}]}],
        }),
        managed_resource(GATE.INVOKER, {"project": GATE.PROJECT, "location": GATE.IDENTITY.REGION,
            "name": "ecoguard-inference", "role": "roles/run.invoker",
            "member": "serviceAccount:" + GATE.INVOKER_EMAIL}),
    ]
    prior = base if stage == "registry" else base + registry
    additions = registry if stage == "registry" else runtime
    planned = prior + additions
    prior_addresses = {r["address"] for r in prior if r["mode"] == "managed"}

    def root(resources):
        return {"child_modules": [{"address": "module.ecoguard", "resources": copy.deepcopy(resources)}]}

    constants = {**GATE.IDENTITY.ROOT_INPUTS, "model_storage_enabled": False,
                 "inference_deletion_protection": False,
                 "cognito_issuer": GATE.RUNTIME_ENV["COGNITO_ISSUER"],
                 "cognito_client_id": GATE.RUNTIME_ENV["COGNITO_CLIENT_ID"],
                 "media_bucket": "ecoguard3184-personal-011154879765-media"}
    expressions = {key: {"constant_value": value} for key, value in constants.items()}
    expressions.update(identity_only={"references": ["var.deployment_stage"]},
                       prepare_registry={"references": ["var.deployment_stage"]},
                       image={"references": ["var.deployment_stage", "var.inference_image"]})
    return {
        "format_version": "1.2", "complete": True, "errored": False,
        "variables": {"deployment_stage": {"value": stage},
                      "inference_image": {"value": "" if stage == "registry" else IMAGE}},
        "configuration": {"root_module": {"module_calls": {"ecoguard": {
            "source": "../..", "expressions": expressions}}}},
        "prior_state": {"values": {"root_module": root(prior)}},
        "planned_values": {"root_module": root(planned)},
        "resource_changes": [
            {"address": r["address"], "mode": "managed", "type": r["type"],
             "change": {"actions": ["no-op"] if r["address"] in prior_addresses else ["create"],
                        "before": copy.deepcopy(r["values"]) if r["address"] in prior_addresses else None,
                        "after": copy.deepcopy(r["values"]), "after_unknown": {}}}
            for r in planned if r["mode"] == "managed"
        ],
    }


def resources(plan, prior=False):
    root = (plan["prior_state"]["values"] if prior else plan["planned_values"])["root_module"]
    return root["child_modules"][0]["resources"]


def change(plan, suffix):
    return next(r for r in plan["resource_changes"] if r["address"] == GATE.MODULE + suffix)


def values(plan, suffix, prior=False):
    return next(r["values"] for r in resources(plan, prior) if r["address"] == GATE.MODULE + suffix)


def mutate(plan, suffix, operation, *, existing_everywhere=False):
    operation(values(plan, suffix))
    operation(change(plan, suffix)["change"]["after"])
    if existing_everywhere:
        operation(values(plan, suffix, prior=True))
        operation(change(plan, suffix)["change"]["before"])


class PersonalRuntimePlanTests(unittest.TestCase):
    def assert_rejected(self, plan, stage="private-inference"):
        report = GATE.inspect_plan(plan, stage, "" if stage == "registry" else IMAGE)
        self.assertEqual(report["status"], "blocked", report)

    def test_exact_registry_then_private_inference_increments_pass_without_cloud_claims(self):
        for stage, prior_count, creates, final_count in (("registry", 7, 2, 9),
                                                       ("private-inference", 9, 4, 13)):
            with self.subTest(stage=stage):
                report = GATE.inspect_plan(fixture_plan(stage), stage, "" if stage == "registry" else IMAGE)
                self.assertEqual(report["status"], "offline-increment-plan-passed")
                self.assertEqual((report["priorManagedResources"], report["creates"], report["managedResources"]),
                                 (prior_count, creates, final_count))
                self.assertTrue(all(item["passed"] for item in report["checks"]))
                for claim in ("applyAuthorized", "cloudVerified", "fundingVerified",
                              "imageProvenanceVerified", "crossCloudVerified"):
                    self.assertFalse(report[claim])

    def test_extra_iam_and_public_invokers_are_rejected(self):
        for stage in ("registry", "private-inference"):
            for role, member in (("roles/owner", "allUsers"),
                                 ("roles/run.invoker", "allAuthenticatedUsers")):
                plan = fixture_plan(stage)
                extra = managed_resource("google_project_iam_member.unapproved", {
                    "project": GATE.PROJECT, "role": role, "member": member})
                resources(plan).append(extra)
                plan["resource_changes"].append({"address": extra["address"], "mode": "managed",
                    "change": {"actions": ["create"], "before": None, "after": extra["values"]}})
                with self.subTest(stage=stage, member=member):
                    self.assert_rejected(plan, stage)
        for member in ("allUsers", "allAuthenticatedUsers", "serviceAccount:other@example.com"):
            plan = fixture_plan("private-inference")
            mutate(plan, GATE.INVOKER, lambda v: v.update(member=member))
            with self.subTest(member=member):
                self.assert_rejected(plan)

    def test_existing_wif_must_remain_exact_even_if_all_changes_claim_noop(self):
        suffix = "google_iam_workload_identity_pool_provider.aws"
        changes = ({"attribute_condition": "true"},
                   {"attribute_condition": f"assertion.account == '{GATE.IDENTITY.AWS_ACCOUNT}'"},
                   {"aws": [{"account_id": "360493183467"}]},
                   {"attribute_mapping": {"google.subject": "assertion.arn", "attribute.aws_role": "assertion.arn"}},
                   {"disabled": True}, {"project": "ecoguard-fit3184-jlii0474"})
        for update in changes:
            plan = fixture_plan("private-inference")
            mutate(plan, suffix, lambda v: v.update(copy.deepcopy(update)), existing_everywhere=True)
            with self.subTest(update=update):
                self.assert_rejected(plan)
        plan = fixture_plan("private-inference")
        mutate(plan, "google_service_account_iam_member.aws_invoker",
               lambda v: v.update(member="allUsers"), existing_everywhere=True)
        self.assert_rejected(plan)

    def test_update_delete_replace_move_depose_and_import_are_rejected(self):
        for stage in ("registry", "private-inference"):
            for actions in (["update"], ["delete"], ["delete", "create"], ["create", "delete"]):
                plan = fixture_plan(stage)
                plan["resource_changes"][0]["change"]["actions"] = actions
                with self.subTest(stage=stage, actions=actions):
                    self.assert_rejected(plan, stage)
            for nested, key, value in ((False, "previous_address", "module.old.google_service_account.invoker"),
                                       (False, "deposed", "abcdef01"),
                                       (False, "importing", {"id": "existing"}),
                                       (True, "importing", {"id": "existing"})):
                plan = fixture_plan(stage)
                target = plan["resource_changes"][-1]
                (target["change"] if nested else target)[key] = value
                with self.subTest(stage=stage, key=key, nested=nested):
                    self.assert_rejected(plan, stage)

    def test_unchanged_actions_cannot_hide_changes_to_existing_values(self):
        plan = fixture_plan("private-inference")
        mutate(plan, GATE.REPOSITORY, lambda v: v.update(description="unreviewed mutation"))
        self.assert_rejected(plan)
        plan = fixture_plan("registry")
        suffix = 'google_project_service.required["iam.googleapis.com"]'
        mutate(plan, suffix, lambda v: v.update(disable_on_destroy=True), existing_everywhere=True)
        self.assert_rejected(plan, "registry")

    def test_missing_or_duplicate_prior_planned_and_change_resources_are_rejected(self):
        for stage in ("registry", "private-inference"):
            for location in ("prior", "planned", "changes"):
                for duplicate in (False, True):
                    plan = fixture_plan(stage)
                    sequence = (plan["resource_changes"] if location == "changes" else
                                resources(plan, prior=location == "prior"))
                    if duplicate:
                        sequence.append(copy.deepcopy(sequence[0]))
                    else:
                        sequence.pop(0)
                    with self.subTest(stage=stage, location=location, duplicate=duplicate):
                        self.assert_rejected(plan, stage)

    def test_drift_deferred_error_and_incomplete_plan_are_rejected(self):
        for update in ({"resource_drift": [{"address": "old"}]},
                       {"deferred_changes": [{"reason": "unknown"}]},
                       {"complete": False}, {"errored": True}):
            plan = fixture_plan("private-inference")
            plan.update(update)
            with self.subTest(update=update):
                self.assert_rejected(plan)
        plan = fixture_plan("private-inference")
        del plan["complete"]
        self.assert_rejected(plan)

    def test_stage_image_and_unconditional_module_scope_are_required(self):
        for key, replacement in (("deployment_stage", "identity"), ("inference_image", "")):
            plan = fixture_plan("private-inference")
            plan["variables"][key]["value"] = replacement
            with self.subTest(key=key):
                self.assert_rejected(plan)
        for update in ({"source": "../unreviewed"}, {"count_expression": {}},
                       {"for_each_expression": {}}, {"depends_on": []}):
            plan = fixture_plan("private-inference")
            plan["configuration"]["root_module"]["module_calls"]["ecoguard"].update(update)
            with self.subTest(update=update):
                self.assert_rejected(plan)

    def test_mutable_digest_wrong_registry_and_wrong_image_path_are_rejected(self):
        for image in (GATE.REGISTRY + "/inference:latest", GATE.REGISTRY + "/inference:release",
                      IMAGE.replace(GATE.PROJECT, "old-project"), IMAGE.replace("us-central1-", "us-east1-"),
                      IMAGE.replace("/inference@", "/unreviewed@"), IMAGE[:-1], IMAGE[:-64] + "A" * 64):
            with self.subTest(image=image), self.assertRaises(ValueError):
                GATE.inspect_plan(fixture_plan("private-inference"), "private-inference", image)
        with self.assertRaises(ValueError):
            GATE.inspect_plan(fixture_plan("registry"), "registry", IMAGE)
        plan = fixture_plan("private-inference")
        mutate(plan, GATE.SERVICE, lambda v: v["template"][0]["containers"][0].update(image=IMAGE[:-1] + "b"))
        self.assert_rejected(plan)

    def test_private_auth_identity_and_capacity_cannot_change(self):
        operations = (
            lambda v: v.update(invoker_iam_disabled=True),
            lambda v: v.update(deletion_protection=True),
            lambda v: v.update(ingress="INGRESS_TRAFFIC_INTERNAL_ONLY"),
            lambda v: v.update(project="ecoguard-fit3184-jlii0474"),
            lambda v: v.update(location="australia-southeast1"),
            lambda v: v["template"][0].update(service_account=GATE.INVOKER_EMAIL),
            lambda v: v["template"][0].update(timeout="900s"),
            lambda v: v["template"][0].update(max_instance_request_concurrency=80),
            lambda v: v["template"][0]["scaling"][0].update(min_instance_count=1),
            lambda v: v["template"][0]["scaling"][0].update(max_instance_count=2),
            lambda v: v["template"][0]["containers"][0]["ports"][0].update(name="h2c"),
            lambda v: v["template"][0]["containers"][0]["resources"][0]["limits"].update(cpu="8"),
            lambda v: v["template"][0]["containers"][0]["resources"][0]["limits"].update(memory="16Gi"),
            lambda v: v["template"][0]["containers"][0]["resources"][0].update(cpu_idle=False),
            lambda v: v["template"][0]["containers"][0]["resources"][0].update(startup_cpu_boost=False),
        )
        for index, operation in enumerate(operations):
            plan = fixture_plan("private-inference")
            mutate(plan, GATE.SERVICE, operation)
            with self.subTest(operation=index):
                self.assert_rejected(plan)

    def test_runtime_env_does_not_allow_auth_bypasses_or_old_application_settings(self):
        updates = {"SERVICE_AUTH_MODE": "local", "COGNITO_ISSUER": "https://old.example.com",
                   "COGNITO_CLIENT_ID": "old-client", "SOURCE_S3_HOSTS": "unapproved.example.com",
                   "SOURCE_KEY_PREFIXES": "", "MODEL_MANIFEST_PATH": "/config/model.example.json",
                   "MODEL_MANIFEST_SHA256": "0" * 64, "INFERENCE_TIMEOUT_SECONDS": "900"}
        for name, replacement in updates.items():
            plan = fixture_plan("private-inference")
            def update_env(value):
                env = value["template"][0]["containers"][0]["env"]
                next(item for item in env if item["name"] == name)["value"] = replacement
            mutate(plan, GATE.SERVICE, update_env)
            with self.subTest(name=name):
                self.assert_rejected(plan)
        for extra in ({"name": "K_SERVICE", "value": "forged-service"},
                      {"name": "LOCAL_SERVICE_TOKEN", "value": "unapproved-local-token"}):
            plan = fixture_plan("private-inference")
            mutate(plan, GATE.SERVICE,
                   lambda v: v["template"][0]["containers"][0]["env"].append(copy.deepcopy(extra)))
            with self.subTest(extra=extra["name"]):
                self.assert_rejected(plan)
        plan = fixture_plan("private-inference")
        mutate(plan, GATE.SERVICE, lambda v: v["template"][0]["containers"][0]["env"][0].update(
            value_source=[{"secret_key_ref": [{"secret": "unreviewed", "version": "latest"}]}]))
        self.assert_rejected(plan)

    def test_missing_and_unknown_security_fields_fail_closed(self):
        for suffix, key in ((GATE.SERVICE, "invoker_iam_disabled"),
                            (GATE.SERVICE, "deletion_protection"), (GATE.RUNTIME, "disabled"),
                            (GATE.INVOKER, "member"), (GATE.REGISTRY_API, "project")):
            plan = fixture_plan("private-inference")
            mutate(plan, suffix, lambda v: v.pop(key))
            change(plan, suffix)["change"]["after_unknown"] = {key: True}
            with self.subTest(suffix=suffix, key=key):
                self.assert_rejected(plan)

    def test_unknown_markers_cannot_contradict_literal_security_values(self):
        for suffix, unknown in ((GATE.SERVICE, {"invoker_iam_disabled": True}),
                               (GATE.SERVICE, {"iap_enabled": True}),
                               (GATE.SERVICE, {"default_uri_disabled": True}),
                               (GATE.SERVICE, {"custom_audiences": True}),
                               (GATE.SERVICE, {"scaling": [{"min_instance_count": True}]}),
                               (GATE.SERVICE, {"build_config": True}),
                               (GATE.SERVICE, {"template": [{"service_account": True}]}),
                               (GATE.SERVICE, {"template": [{"encryption_key": True}]}),
                               (GATE.SERVICE, {"template": [{"sandboxes": True}]}),
                               (GATE.SERVICE, {"template": [{"vpc_access": True}]}),
                               (GATE.SERVICE, {"template": [{"containers": [{"base_image_uri": True}]}]}),
                               (GATE.SERVICE, {"template": [{"containers": [{"ports": True}]}]}),
                               (GATE.SERVICE, {"template": [{"containers": [{"ports": [{"name": True}]}]}]}),
                               (GATE.SERVICE, {"template": [{"containers": [{"sandbox_launcher": True}]}]}),
                               (GATE.INVOKER, {"member": True}),
                               (GATE.REPOSITORY, {"project": True})):
            plan = fixture_plan("private-inference")
            change(plan, suffix)["change"]["after_unknown"] = unknown
            with self.subTest(suffix=suffix, unknown=unknown):
                self.assert_rejected(plan)

    def test_create_after_must_match_the_reviewed_planned_values(self):
        for suffix, update in ((GATE.SERVICE, {"invoker_iam_disabled": True}),
                               (GATE.INVOKER, {"member": "allUsers"}),
                               (GATE.RUNTIME, {"project": "other-project"}),
                               (GATE.REPOSITORY, {"mode": "REMOTE_REPOSITORY"})):
            stage = "registry" if suffix == GATE.REPOSITORY else "private-inference"
            plan = fixture_plan(stage)
            change(plan, suffix)["change"]["after"].update(update)
            with self.subTest(suffix=suffix, update=update):
                self.assert_rejected(plan, stage)

    def test_fixed_image_cannot_be_repurposed_by_entrypoint_or_volume_overrides(self):
        for update in ({"command": ["sh", "-c"], "args": ["sleep infinity"]},
                       {"volume_mounts": [{"name": "unapproved", "mount_path": "/config"}]}):
            plan = fixture_plan("private-inference")
            mutate(plan, GATE.SERVICE, lambda v: v["template"][0]["containers"][0].update(copy.deepcopy(update)))
            with self.subTest(update=update):
                self.assert_rejected(plan)
        plan = fixture_plan("private-inference")
        mutate(plan, GATE.SERVICE, lambda v: v["template"][0].update(
            volumes=[{"name": "unapproved", "secret": [{"secret": "unapproved-secret"}]}]))
        self.assert_rejected(plan)

    def test_extra_containers_templates_ports_and_resource_blocks_are_rejected(self):
        for operation in (
            lambda v: v["template"].append(copy.deepcopy(v["template"][0])),
            lambda v: v["template"][0]["containers"].append(copy.deepcopy(v["template"][0]["containers"][0])),
            lambda v: v["template"][0]["containers"][0]["ports"].append({"container_port": 9000}),
            lambda v: v["template"][0]["containers"][0]["resources"].append({"limits": {"cpu": "8", "memory": "16Gi"}}),
        ):
            plan = fixture_plan("private-inference")
            mutate(plan, GATE.SERVICE, operation)
            self.assert_rejected(plan)

    def test_service_level_scaling_cannot_keep_instances_running_or_expand_capacity(self):
        for update in ({"min_instance_count": 1}, {"max_instance_count": 2},
                       {"manual_instance_count": 1},
                       {"scaling_mode": "MANUAL", "manual_instance_count": 1}):
            plan = fixture_plan("private-inference")
            mutate(plan, GATE.SERVICE, lambda v: v["scaling"][0].update(update))
            with self.subTest(update=update):
                self.assert_rejected(plan)
        for key in ("scaling_mode", "min_instance_count", "max_instance_count", "manual_instance_count"):
            plan = fixture_plan("private-inference")
            mutate(plan, GATE.SERVICE, lambda v: v["scaling"][0].pop(key))
            with self.subTest(missing=key):
                self.assert_rejected(plan)
        plan = fixture_plan("private-inference")
        mutate(plan, GATE.SERVICE, lambda v: v.pop("scaling"))
        self.assert_rejected(plan)

    def test_unreviewed_connector_or_direct_vpc_access_is_rejected(self):
        # Pure plan fixtures: no connector, network or subnetwork is contacted.
        for access in (
            {"connector": f"projects/{GATE.PROJECT}/locations/us-central1/connectors/unapproved",
             "egress": "ALL_TRAFFIC"},
            {"network_interfaces": [{"network": "unapproved", "subnetwork": "unapproved"}],
             "egress": "PRIVATE_RANGES_ONLY"},
        ):
            plan = fixture_plan("private-inference")
            mutate(plan, GATE.SERVICE,
                   lambda v: v["template"][0].update(vpc_access=[copy.deepcopy(access)]))
            with self.subTest(access=access):
                self.assert_rejected(plan)

    def test_fixed_digest_cannot_opt_into_automatic_base_image_updates(self):
        plan = fixture_plan("private-inference")
        mutate(plan, GATE.SERVICE, lambda v: v["template"][0]["containers"][0].update(
            base_image_uri="us-central1-docker.pkg.dev/serverless-runtimes/google-22/python312"))
        self.assert_rejected(plan)

    def test_image_deployment_cannot_add_service_source_build_configuration(self):
        plan = fixture_plan("private-inference")
        mutate(plan, GATE.SERVICE, lambda v: v.update(build_config=[{
            "source_location": "gs://unapproved-source/source.zip",
            "image_uri": IMAGE, "enable_automatic_updates": True}]))
        self.assert_rejected(plan)

    def test_unreviewed_ingress_auth_encryption_and_sandbox_options_are_rejected(self):
        operations = (
            lambda v: v.update(iap_enabled=True),
            lambda v: v.update(default_uri_disabled=True),
            lambda v: v.update(custom_audiences=["https://unapproved.example.com"]),
            lambda v: v["template"][0].update(encryption_key=
                f"projects/{GATE.PROJECT}/locations/us-central1/keyRings/unapproved/cryptoKeys/unapproved"),
            lambda v: v["template"][0].update(sandboxes=[{}]),
            lambda v: v["template"][0]["containers"][0].update(sandbox_launcher=True),
        )
        for index, operation in enumerate(operations):
            plan = fixture_plan("private-inference")
            mutate(plan, GATE.SERVICE, operation)
            with self.subTest(operation=index):
                self.assert_rejected(plan)

    def test_existing_registry_and_locked_manifest_cannot_drift(self):
        plan = fixture_plan("private-inference")
        mutate(plan, GATE.REPOSITORY, lambda v: v.update(mode="REMOTE_REPOSITORY"), existing_everywhere=True)
        self.assert_rejected(plan)
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "model.locked.json"
            manifest.write_bytes(GATE.IDENTITY.MANIFEST.read_bytes() + b"\n")
            report = GATE.inspect_plan(fixture_plan("private-inference"), "private-inference", IMAGE,
                                       manifest_path=manifest)
            self.assertEqual(report["status"], "blocked")

    def test_cli_rejects_malformed_private_plan_without_cloud_claims(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = Path(directory) / "plan.json"
            plan.write_text("[]")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(GATE.main(["--plan-json", str(plan), "--stage", "registry"]), 2)


if __name__ == "__main__":
    unittest.main()
