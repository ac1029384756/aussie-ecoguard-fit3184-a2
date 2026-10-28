"""Review an initial three-create static frontend plan; never call cloud or apply."""
import argparse
import json
from pathlib import Path
import re

PROJECT = "ecoguard-fit3184-a2-2026"
NUMBER = "995070689587"
REGION = "us-central1"
IMAGE = re.compile(r"^us-central1-docker\.pkg\.dev/" + PROJECT + r"/ecoguard/frontend@sha256:[0-9a-f]{64}$")
EXPECTED = {
    "google_service_account.frontend",
    "google_cloud_run_v2_service.frontend",
    "google_cloud_run_v2_service_iam_member.frontend_public",
}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def one(value, name):
    require(isinstance(value, list) and len(value) == 1, "Expected one " + name)
    return value[0]


def empty(value):
    return value is None or value == [] or value == {} or value == ""


def review(plan, image):
    require(bool(IMAGE.fullmatch(image)), "Expected the reviewed immutable frontend image")
    require(plan.get("terraform_version") == "1.17.0", "Unexpected Terraform version")
    require(not plan.get("errored", False), "Plan contains an error")
    require(plan.get("applyable") is True and plan.get("complete") is True, "Expected a complete applicable plan")
    require(all(c.get("status") == "pass" for c in plan.get("checks", [])), "An actual plan check did not pass")
    require(not plan.get("resource_drift"), "Unexpected drift")
    require(plan.get("variables", {}).get("frontend_image", {}).get("value") == image, "Image variable mismatch")
    config = plan.get("configuration", {}).get("root_module", {})
    require(not config.get("module_calls"), "Unexpected child module")
    prior = plan.get("prior_state", {}).get("values", {}).get("root_module", {})
    require(not prior.get("child_modules"), "Unexpected prior child state")
    require(not [r for r in prior.get("resources", []) if r.get("mode") == "managed"], "Initial frontend state must be empty")
    changes = plan.get("resource_changes", [])
    managed = [c for c in changes if c.get("mode") == "managed"]
    require(len(managed) == 3 and {c.get("address") for c in managed} == EXPECTED, "Only three named frontend resources may change")
    for c in managed:
        require(c.get("provider_name") == "registry.terraform.io/hashicorp/google", "Unexpected provider")
        require(c["change"].get("actions") == ["create"] and c["change"].get("before") is None, "Only initial creates allowed")
        require(not c.get("previous_address") and not c["change"].get("importing"), "No move/import allowed")
    data = [c for c in changes if c.get("mode") == "data"]
    require(len(data) <= 1 and all(c.get("address") == "data.google_project.current" for c in data), "Unexpected data change")
    planned_root = plan.get("planned_values", {}).get("root_module", {})
    require(not planned_root.get("child_modules"), "Unexpected planned child module")
    planned = planned_root.get("resources", [])
    require({r.get("address") for r in planned if r.get("mode") == "managed"} == EXPECTED, "Unexpected planned managed resource")
    planned_data = [r for r in planned if r.get("mode") == "data"]
    prior_data = [r for r in prior.get("resources", []) if r.get("mode") == "data"]
    # Terraform may retain an already-read data source only in prior_state when
    # it is consumed solely by a precondition. Validate its resolved identity
    # wherever it occurs; never substitute an assumed/default project number.
    for group in (planned_data, prior_data):
        require(len(group) <= 1 and all(r.get("address") == "data.google_project.current" for r in group), "Unexpected project data resource")
    require(planned_data or prior_data, "Expected the resolved fixed project data read")
    for resolved in planned_data + prior_data:
        project = resolved["values"]
        require(project.get("project_id") == PROJECT and str(project.get("number")) == NUMBER, "Unexpected actual project identity")
    after = {c["address"]: c["change"]["after"] for c in managed}
    sa = after["google_service_account.frontend"]
    require(sa.get("project") == PROJECT and sa.get("account_id") == "ecoguard-frontend", "Unexpected service account")
    service = after["google_cloud_run_v2_service.frontend"]
    require(service.get("project") == PROJECT and service.get("location") == REGION and service.get("name") == "ecoguard-web", "Wrong service target")
    require(service.get("ingress") == "INGRESS_TRAFFIC_ALL" and service.get("invoker_iam_disabled") is False, "Unexpected ingress or IAM enforcement")
    require(service.get("deletion_protection") is False, "Reviewed cleanup must remain possible")
    scale = one(service.get("scaling"), "service scaling")
    require(scale.get("min_instance_count") == 0 and scale.get("max_instance_count") == 1 and scale.get("scaling_mode") == "AUTOMATIC", "Unexpected service scaling")
    require(scale.get("manual_instance_count") == 0, "Unexpected manual scaling")
    template = one(service.get("template"), "revision")
    require(template.get("service_account") == "ecoguard-frontend@" + PROJECT + ".iam.gserviceaccount.com", "Wrong runtime identity")
    require(template.get("execution_environment") == "EXECUTION_ENVIRONMENT_GEN2", "Unexpected execution environment")
    require(template.get("timeout") == "30s" and template.get("max_instance_request_concurrency") == 80, "Unexpected request limits")
    scale = one(template.get("scaling"), "revision scaling")
    require(scale.get("min_instance_count") == 0 and scale.get("max_instance_count") == 1, "Unexpected revision scaling")
    require(empty(template.get("volumes")) and empty(template.get("vpc_access")) and empty(template.get("encryption_key")), "Unexpected mount/network/key override")
    container = one(template.get("containers"), "container")
    require(container.get("image") == image, "Unexpected image")
    for field in ("env", "command", "args", "volume_mounts"):
        require(empty(container.get(field)), "Unexpected container " + field)
    port = one(container.get("ports"), "port")
    require(port.get("name") == "http1" and port.get("container_port") == 8080, "Unexpected port")
    resources = one(container.get("resources"), "resource limits")
    require(resources.get("limits") == {"cpu": "1", "memory": "256Mi"}, "Unexpected CPU/memory")
    require(resources.get("cpu_idle") is True and resources.get("startup_cpu_boost") is False, "Unexpected billing/boost settings")
    probe = one(container.get("startup_probe"), "startup probe")
    http = one(probe.get("http_get"), "HTTP probe")
    require(http.get("path") == "/healthz" and http.get("port") == 8080, "Unexpected health endpoint")
    require(probe.get("initial_delay_seconds") == 0 and probe.get("timeout_seconds") == 1 and probe.get("period_seconds") == 3 and probe.get("failure_threshold") == 10, "Unexpected startup budget")
    iam = after["google_cloud_run_v2_service_iam_member.frontend_public"]
    require(iam.get("project") == PROJECT and iam.get("location") == REGION and iam.get("name") == "ecoguard-web", "Public access must target only the frontend")
    require(iam.get("role") == "roles/run.invoker" and iam.get("member") == "allUsers" and empty(iam.get("condition")), "Unexpected public binding")
    return {"status": "PASS", "creates": 3, "updates": 0, "deletes": 0,
            "project": PROJECT, "projectNumber": NUMBER, "region": REGION,
            "image": image, "service": "ecoguard-web", "privateInferenceManaged": False,
            "projectIAMManaged": False, "cloudCallsOrApplyPerformed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--expected-image", required=True)
    args = parser.parse_args()
    try:
        result = review(json.loads(args.plan.read_text()), args.expected_image)
    except (ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "BLOCKED", "reason": str(error)}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
