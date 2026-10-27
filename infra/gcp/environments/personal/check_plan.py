"""Offline gate for the first personal GCP identity-only saved plan.

No Google/AWS SDK, credentials, Terraform invocation or cloud mutation is used.
Read private `terraform show -json` output; never commit or paste that document.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

PROJECT = "ecoguard-fit3184-a2-2026"
PROJECT_NUMBER = "995070689587"
REGION = "us-central1"
AWS_ACCOUNT = "011154879765"
AWS_ROLE = "ecoguard3184-personal-lambda"
MANIFEST_SHA256 = "639595e1e9ffe18cb11ead1c7480ffe7a31bf767f6cbaf6b8375829227a569ae"
MANIFEST = Path(__file__).resolve().parents[4] / "config/model.locked.json"
MODULE = "module.ecoguard."
APIS = {"iam.googleapis.com", "iamcredentials.googleapis.com", "sts.googleapis.com"}
POOL_ID = "ecoguard-aws"
POOL_NAME = f"projects/{PROJECT_NUMBER}/locations/global/workloadIdentityPools/{POOL_ID}"
SA_ID = "ecoguard-aws-invoker"
SA_NAME = f"projects/{PROJECT}/serviceAccounts/{SA_ID}@{PROJECT}.iam.gserviceaccount.com"
ROLE_ARN = f"arn:aws:sts::{AWS_ACCOUNT}:assumed-role/{AWS_ROLE}"
PRINCIPAL = f"principalSet://iam.googleapis.com/{POOL_NAME}/attribute.aws_role/{ROLE_ARN}"
CONDITION = f"assertion.account == '{AWS_ACCOUNT}' && attribute.aws_role == '{ROLE_ARN}'"
MAPPING = {
    "google.subject": "assertion.arn",
    "attribute.aws_role": "assertion.arn.contains('assumed-role') ? assertion.arn.extract('{account_arn}assumed-role/') + 'assumed-role/' + assertion.arn.extract('assumed-role/{role_name}/') : assertion.arn",
}
ROOT_INPUTS = {
    "project_id": PROJECT, "identity_only": True, "region": REGION,
    "prefix": "ecoguard3184", "aws_account_id": AWS_ACCOUNT,
    "aws_role_name": AWS_ROLE, "aws_region": "us-east-1",
    "manifest_sha256": MANIFEST_SHA256, "image": "", "cognito_issuer": "",
    "cognito_client_id": "", "media_bucket": "", "inference_environment": {},
}


def expected_addresses():
    return {MODULE + address for address in (
        "google_service_account.invoker", "google_iam_workload_identity_pool.aws",
        "google_iam_workload_identity_pool_provider.aws", "google_service_account_iam_member.aws_invoker",
        *[f'google_project_service.required["{service}"]' for service in APIS],
    )}


def resources(module):
    yield from module.get("resources", [])
    for child in module.get("child_modules", []):
        yield from resources(child)


def inspect_plan(document, *, manifest_path=MANIFEST):
    if not isinstance(document, dict):
        raise ValueError("Plan JSON must be an object")
    checks = []

    def check(name, passed):
        checks.append({"name": name, "passed": bool(passed)})

    planned = list(resources(document.get("planned_values", {}).get("root_module", {})))
    prior = list(resources(document.get("prior_state", {}).get("values", {}).get("root_module", {})))
    managed_list = [r for r in planned if r.get("mode") == "managed"]
    managed = {r["address"]: r for r in managed_list}
    projects = [r.get("values", {}) for r in planned
                if r.get("mode") == "data" and r.get("type") == "google_project"]
    if not projects:
        projects = [r.get("values", {}) for r in prior
                    if r.get("mode") == "data" and r.get("type") == "google_project"]
    check("verified_personal_project", len(projects) == 1 and projects[0].get("project_id") == PROJECT
          and str(projects[0].get("number")) == PROJECT_NUMBER)
    call = document.get("configuration", {}).get("root_module", {}).get("module_calls", {}).get("ecoguard", {})
    expressions = call.get("expressions", {})
    check("fixed_identity_only_module_inputs", call.get("source") == "../.."
          and set(expressions) == set(ROOT_INPUTS)
          and all(expressions.get(key, {}).get("constant_value") == value for key, value in ROOT_INPUTS.items()))
    check("unconditional_legacy_module_call", not any(key in call for key in
          ("count_expression", "for_each_expression", "depends_on")))
    check("locked_checkout_manifest", hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest() == MANIFEST_SHA256)
    check("only_seven_identity_resources", len(managed_list) == 7 and set(managed) == expected_addresses())
    changes = [r for r in document.get("resource_changes", []) if r.get("mode") == "managed"]
    check("first_plan_only_creates_expected_resources", len(changes) == 7
          and {r.get("address") for r in changes} == expected_addresses()
          and all(r.get("change", {}).get("actions") == ["create"]
                  and not r.get("change", {}).get("importing") and not r.get("importing")
                  and not r.get("previous_address") and not r.get("deposed")
                  and r.get("change", {}).get("before") is None for r in changes))
    check("no_existing_managed_state", not any(r.get("mode") == "managed" for r in prior))
    check("complete_unerrored_plan", document.get("errored") is not True
          and document.get("complete") is not False and not document.get("deferred_changes"))

    def values(address):
        return managed.get(MODULE + address, {}).get("values", {})

    check("required_identity_apis_retained", all(
        values(f'google_project_service.required["{service}"]').get("project") == PROJECT
        and values(f'google_project_service.required["{service}"]').get("service") == service
        and values(f'google_project_service.required["{service}"]').get("disable_on_destroy") is False
        for service in APIS))
    check("identity_resources_target_personal_project", all(values(address).get("project") == PROJECT for address in (
        "google_service_account.invoker", "google_iam_workload_identity_pool.aws",
        "google_iam_workload_identity_pool_provider.aws")))
    check("dedicated_invoker_account", values("google_service_account.invoker").get("account_id") == SA_ID)
    pool = values("google_iam_workload_identity_pool.aws")
    provider = values("google_iam_workload_identity_pool_provider.aws")
    check("dedicated_aws_pool_and_provider", pool.get("workload_identity_pool_id") == POOL_ID
          and provider.get("workload_identity_pool_id") == POOL_ID
          and provider.get("workload_identity_pool_provider_id") == "aws-role")
    check("aws_account_role_and_mapping_exact", provider.get("aws") == [{"account_id": AWS_ACCOUNT}]
          and provider.get("attribute_condition") == CONDITION and provider.get("attribute_mapping") == MAPPING
          and not provider.get("oidc") and not provider.get("saml"))
    grant = values("google_service_account_iam_member.aws_invoker")
    check("one_exact_workload_identity_grant", grant.get("service_account_id") == SA_NAME
          and grant.get("role") == "roles/iam.workloadIdentityUser"
          and grant.get("member") == PRINCIPAL and not grant.get("condition"))
    return {
        "status": "offline-first-identity-plan-passed" if all(c["passed"] for c in checks) else "blocked",
        "project": PROJECT, "projectNumber": PROJECT_NUMBER, "managedResources": len(managed_list),
        "checks": checks, "cloudVerified": False, "awsRoleVerified": False,
        "crossCloudVerified": False, "applyAuthorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-json", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = inspect_plan(json.loads(args.plan_json.read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        print("Offline identity gate blocked: invalid or incomplete private plan input.", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 0 if report["status"] != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
