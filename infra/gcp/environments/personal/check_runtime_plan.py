"""Offline review of two bounded increments after the seven-resource identity apply.

This gate never calls Terraform or a cloud API. It rejects drift, changes to the
existing identities, extra IAM and unknown security settings. Passing it does not
authorize apply or prove funding, image provenance, federation or inference.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

SPEC = importlib.util.spec_from_file_location("frozen_identity_gate", Path(__file__).with_name("check_plan.py"))
IDENTITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IDENTITY)
MODULE = IDENTITY.MODULE
PROJECT = IDENTITY.PROJECT
REGISTRY = f"{IDENTITY.REGION}-docker.pkg.dev/{PROJECT}/ecoguard"
IMAGE_PATTERN = re.compile(re.escape(REGISTRY) + r"/inference@sha256:[0-9a-f]{64}")
REGISTRY_API = 'google_project_service.required["artifactregistry.googleapis.com"]'
RUN_API = 'google_project_service.required["run.googleapis.com"]'
REPOSITORY = "google_artifact_registry_repository.images[0]"
RUNTIME = "google_service_account.runtime[0]"
SERVICE = "google_cloud_run_v2_service.inference[0]"
INVOKER = "google_cloud_run_v2_service_iam_member.invoker[0]"
REGISTRY_ADDITIONS = {MODULE + REGISTRY_API, MODULE + REPOSITORY}
RUNTIME_ADDITIONS = {MODULE + value for value in (RUN_API, RUNTIME, SERVICE, INVOKER)}
RUNTIME_EMAIL = f"ecoguard-inference@{PROJECT}.iam.gserviceaccount.com"
INVOKER_EMAIL = f"{IDENTITY.SA_ID}@{PROJECT}.iam.gserviceaccount.com"
RUNTIME_ENV = {
    "SERVICE_AUTH_MODE": "cloud-run",
    "COGNITO_ISSUER": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_Sog8ekMM1",
    "COGNITO_CLIENT_ID": "5gu7g1rgkmabdd551h5k3350f6",
    "SOURCE_S3_HOSTS": "ecoguard3184-personal-011154879765-media.s3.us-east-1.amazonaws.com",
    "SOURCE_KEY_PREFIXES": "derived/,queries/",
    "MODEL_MANIFEST_PATH": "/config/model.locked.json",
    "MODEL_MANIFEST_SHA256": IDENTITY.MANIFEST_SHA256,
    "INFERENCE_TIMEOUT_SECONDS": "240",
}


def managed(root):
    return [resource for resource in IDENTITY.resources(root) if resource.get("mode") == "managed"]


def at(value, path):
    for key in path:
        try:
            value = value[key]
        except (KeyError, IndexError, TypeError):
            return None
    return value


def has_unknown(value):
    if isinstance(value, dict):
        return any(has_unknown(item) for item in value.values())
    if isinstance(value, list):
        return any(has_unknown(item) for item in value)
    return value is True


def unknown_at(value, path):
    for key in path:
        if value is True:
            return True
        try:
            value = value[key]
        except (KeyError, IndexError, TypeError):
            return False
    return has_unknown(value)


def required_paths(address):
    suffix = address.removeprefix(MODULE)
    if suffix in (REGISTRY_API, RUN_API):
        return [(key,) for key in ("project", "service", "disable_on_destroy")]
    if suffix == REPOSITORY:
        return [(key,) for key in ("project", "location", "repository_id", "format", "mode",
                                  "remote_repository_config", "virtual_repository_config")]
    if suffix == RUNTIME:
        return [(key,) for key in ("project", "account_id", "disabled")]
    if suffix == INVOKER:
        return [(key,) for key in ("project", "location", "name", "role", "member", "condition")]
    paths = [(key,) for key in ("project", "location", "name", "ingress", "deletion_protection", "invoker_iam_disabled",
                               "scaling", "build_config", "iap_enabled", "default_uri_disabled", "custom_audiences")]
    paths += [("template", 0, key) for key in ("service_account", "timeout", "max_instance_request_concurrency",
                                              "scaling", "volumes", "vpc_access", "encryption_key", "sandboxes")]
    paths += [("template", 0, "containers", 0, key) for key in ("image", "ports", "resources", "env", "command", "args",
                                                               "volume_mounts", "base_image_uri", "sandbox_launcher")]
    return paths


def security_values_are_known(changes, planned, additions):
    for item in changes:
        address = item.get("address")
        change = item.get("change", {})
        if address not in additions:
            if has_unknown(change.get("after_unknown")):
                return False
            continue
        for path in required_paths(address):
            if (unknown_at(change.get("after_unknown", {}), path)
                    or at(change.get("after", {}), path) != at(planned.get(address, {}), path)):
                return False
    return True


def identity_is_exact(values):
    """Recheck the deployed identity semantics as well as requiring no-op actions."""
    def value(suffix):
        return values.get(MODULE + suffix, {})
    pool = value("google_iam_workload_identity_pool.aws")
    provider = value("google_iam_workload_identity_pool_provider.aws")
    grant = value("google_service_account_iam_member.aws_invoker")
    account = value("google_service_account.invoker")
    return (
        account.get("project") == PROJECT and account.get("account_id") == IDENTITY.SA_ID
        and account.get("disabled") is False
        and pool.get("project") == PROJECT and pool.get("workload_identity_pool_id") == IDENTITY.POOL_ID
        and pool.get("disabled") is False
        and provider.get("project") == PROJECT and provider.get("disabled") is False
        and provider.get("workload_identity_pool_id") == IDENTITY.POOL_ID
        and provider.get("workload_identity_pool_provider_id") == "aws-role"
        and provider.get("aws") == [{"account_id": IDENTITY.AWS_ACCOUNT}]
        and provider.get("attribute_mapping") == IDENTITY.MAPPING
        and provider.get("attribute_condition") == IDENTITY.CONDITION
        and not provider.get("oidc") and not provider.get("saml")
        and grant.get("service_account_id") == IDENTITY.SA_NAME
        and grant.get("member") == IDENTITY.PRINCIPAL
        and grant.get("role") == "roles/iam.workloadIdentityUser" and not grant.get("condition")
    )


def api_is_exact(value, service):
    return (value.get("project") == PROJECT and value.get("service") == service
            and value.get("disable_on_destroy") is False)


def registry_is_exact(values):
    repo = values.get(MODULE + REPOSITORY, {})
    return (api_is_exact(values.get(MODULE + REGISTRY_API, {}), "artifactregistry.googleapis.com")
            and repo.get("project") == PROJECT and repo.get("location") == IDENTITY.REGION
            and repo.get("repository_id") == "ecoguard" and repo.get("format") == "DOCKER"
            and repo.get("mode") == "STANDARD_REPOSITORY"
            and not repo.get("remote_repository_config") and not repo.get("virtual_repository_config"))


def runtime_is_exact(values, image):
    runtime = values.get(MODULE + RUNTIME, {})
    service = values.get(MODULE + SERVICE, {})
    grant = values.get(MODULE + INVOKER, {})
    templates = service.get("template", [])
    if len(templates) != 1:
        return False
    template = templates[0]
    containers = template.get("containers", [])
    if len(containers) != 1:
        return False
    container = containers[0]
    env = container.get("env", [])
    resources = container.get("resources", [])
    return (
        api_is_exact(values.get(MODULE + RUN_API, {}), "run.googleapis.com")
        and runtime.get("project") == PROJECT and runtime.get("account_id") == "ecoguard-inference"
        and runtime.get("disabled") is False
        and service.get("project") == PROJECT and service.get("location") == IDENTITY.REGION
        and service.get("name") == "ecoguard-inference"
        and service.get("ingress") == "INGRESS_TRAFFIC_ALL"
        and service.get("deletion_protection") is False
        and service.get("invoker_iam_disabled") is False
        and service.get("iap_enabled") in (None, False) and service.get("default_uri_disabled") in (None, False)
        and not service.get("custom_audiences")
        and not service.get("build_config")
        and len(service.get("scaling", [])) == 1
        and service["scaling"][0] == {"scaling_mode": "AUTOMATIC", "min_instance_count": 0,
                                     "max_instance_count": 1, "manual_instance_count": 0}
        and template.get("service_account") == RUNTIME_EMAIL
        and not template.get("volumes") and not template.get("vpc_access")
        and not template.get("encryption_key") and not template.get("sandboxes")
        and template.get("timeout") == "360s" and template.get("max_instance_request_concurrency") == 1
        and len(template.get("scaling", [])) == 1
        and template["scaling"][0].get("min_instance_count") == 0
        and template["scaling"][0].get("max_instance_count") == 1
        and container.get("image") == image
        and not container.get("command") and not container.get("args") and not container.get("volume_mounts")
        and not container.get("base_image_uri")
        and container.get("sandbox_launcher") in (None, False)
        and len(container.get("ports", [])) == 1 and container["ports"][0].get("container_port") == 8080
        and container["ports"][0].get("name") == "http1"
        and len(resources) == 1 and resources[0].get("limits") == {"cpu": "4", "memory": "8Gi"}
        and resources[0].get("cpu_idle") is True and resources[0].get("startup_cpu_boost") is True
        and len(env) == len(RUNTIME_ENV)
        and {item.get("name"): item.get("value") for item in env} == RUNTIME_ENV
        and not any(item.get("value_source") for item in env)
        and grant.get("project") == PROJECT and grant.get("location") == IDENTITY.REGION
        and grant.get("name") == "ecoguard-inference" and grant.get("role") == "roles/run.invoker"
        and grant.get("member") == "serviceAccount:" + INVOKER_EMAIL and not grant.get("condition")
    )


def inspect_plan(document, stage, image="", *, manifest_path=IDENTITY.MANIFEST):
    if stage not in ("registry", "private-inference"):
        raise ValueError("Only the registry and private-inference increments are supported")
    if (stage == "registry" and image) or (stage == "private-inference" and not IMAGE_PATTERN.fullmatch(image)):
        raise ValueError("Private inference requires an exact digest in the personal registry; registry requires no image")
    if not isinstance(document, dict):
        raise ValueError("Plan JSON must be an object")
    checks = []
    def check(name, passed):
        checks.append({"name": name, "passed": bool(passed)})
    identity = IDENTITY.expected_addresses()
    before_expected = identity if stage == "registry" else identity | REGISTRY_ADDITIONS
    additions = REGISTRY_ADDITIONS if stage == "registry" else RUNTIME_ADDITIONS
    after_expected = before_expected | additions
    prior_list = managed(document.get("prior_state", {}).get("values", {}).get("root_module", {}))
    planned_list = managed(document.get("planned_values", {}).get("root_module", {}))
    prior = {item["address"]: item.get("values", {}) for item in prior_list}
    planned = {item["address"]: item.get("values", {}) for item in planned_list}
    changes = [item for item in document.get("resource_changes", []) if item.get("mode") == "managed"]
    check("exact_existing_managed_state", len(prior_list) == len(before_expected) and set(prior) == before_expected)
    check("exact_increment_resource_set", len(planned_list) == len(after_expected) and set(planned) == after_expected)
    check("no_drift_deferred_or_incomplete_plan", not document.get("resource_drift")
          and not document.get("deferred_changes") and document.get("complete") is True
          and document.get("errored") is not True)
    check("only_expected_creates_and_unchanged_resources", len(changes) == len(after_expected)
          and {item.get("address") for item in changes} == after_expected
          and all(item.get("change", {}).get("actions") == (["create"] if item.get("address") in additions else ["no-op"])
                  and not item.get("previous_address") and not item.get("deposed")
                  and not item.get("importing") and not item.get("change", {}).get("importing")
                  and (item.get("change", {}).get("before") is None if item.get("address") in additions else
                       item.get("change", {}).get("before") == item.get("change", {}).get("after") == prior.get(item.get("address")) == planned.get(item.get("address")))
                  for item in changes))
    check("required_security_values_known_and_consistent", security_values_are_known(changes, planned, additions))
    check("existing_identity_stays_exact", identity_is_exact(prior) and identity_is_exact(planned))
    check("existing_identity_apis_retained", all(api_is_exact(values.get(MODULE + f'google_project_service.required["{api}"]', {}), api)
          for values in (prior, planned) for api in IDENTITY.APIS))
    check("private_registry_exact", registry_is_exact(planned) and (stage == "registry" or registry_is_exact(prior)))
    check("locked_checkout_manifest", hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest() == IDENTITY.MANIFEST_SHA256)
    projects = [item.get("values", {}) for root in (
        document.get("planned_values", {}).get("root_module", {}),
        document.get("prior_state", {}).get("values", {}).get("root_module", {}))
        for item in IDENTITY.resources(root) if item.get("mode") == "data" and item.get("type") == "google_project"]
    check("verified_personal_project_number", bool(projects)
          and all(item.get("project_id") == PROJECT and str(item.get("number")) == IDENTITY.PROJECT_NUMBER for item in projects))
    variables = document.get("variables", {})
    check("explicit_stage_and_image", variables.get("deployment_stage", {}).get("value") == stage
          and variables.get("inference_image", {}).get("value") == image)
    call = document.get("configuration", {}).get("root_module", {}).get("module_calls", {}).get("ecoguard", {})
    check("same_unconditional_module", call.get("source") == "../.."
          and not any(key in call for key in ("count_expression", "for_each_expression", "depends_on")))
    if stage == "private-inference":
        check("bounded_private_runtime_and_one_exact_invoker", runtime_is_exact(planned, image))
    return {"status": "offline-increment-plan-passed" if all(item["passed"] for item in checks) else "blocked",
            "stage": stage, "project": PROJECT, "projectNumber": IDENTITY.PROJECT_NUMBER,
            "priorManagedResources": len(prior_list), "managedResources": len(planned_list),
            "creates": len(additions), "checks": checks, "applyAuthorized": False,
            "cloudVerified": False, "fundingVerified": False, "imageProvenanceVerified": False,
            "crossCloudVerified": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-json", required=True, type=Path)
    parser.add_argument("--stage", required=True, choices=("registry", "private-inference"))
    parser.add_argument("--image", default="")
    args = parser.parse_args(argv)
    try:
        report = inspect_plan(json.loads(args.plan_json.read_text()), args.stage, args.image)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        print("Runtime increment gate blocked: invalid or incomplete private plan input.", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 0 if report["status"] != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
