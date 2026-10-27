"""Focused offline ECR policy/paused wiring review; never approves an apply.

Checks exact 55 -> 59 managed addresses and 4 creates/8 updates/47 no-ops,
the exact ECR statement, known image and paused entry points. It deliberately
does not replace the still-missing complete existing-state increment gate.
No cloud/credential/Terraform imports or calls occur.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import re

spec=importlib.util.spec_from_file_location("aws_foundation_gate",Path(__file__).with_name("check_plan.py"))
BASE=importlib.util.module_from_spec(spec);spec.loader.exec_module(BASE)
ACCOUNT,REGION,PREFIX=BASE.ACCOUNT,BASE.REGION,BASE.PREFIX
MODULE=BASE.MODULE
REPOSITORY=PREFIX+"-worker"
REPOSITORY_ARN=f"arn:aws:ecr:{REGION}:{ACCOUNT}:repository/{REPOSITORY}"
INGEST_ARN=f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:{PREFIX}-ingest"
POLICY=MODULE+"aws_ecr_repository_policy.lambda_ingest[0]"
INGEST=MODULE+"aws_lambda_function.ingest[0]"
MAPPING=MODULE+"aws_lambda_event_source_mapping.ingest[0]"
LOG=MODULE+'aws_cloudwatch_log_group.functions["ingest"]'
ADDITIONS={POLICY,INGEST,MAPPING,LOG}
UPDATES={MODULE+f'aws_lambda_function.zip["{name}"]' for name in BASE.FUNCTIONS}|{MODULE+"aws_iam_role_policy.runtime[0]"}
IMAGE_PATTERN=re.compile(re.escape(f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/{REPOSITORY}@sha256:")+r"[0-9a-f]{64}")


def require(ok,reason):
    if not ok:raise ValueError(reason)


def expected_policy():
    return {"Version":"2012-10-17","Statement":[{"Sid":"LambdaECRImageRetrievalPolicy","Effect":"Allow",
        "Principal":{"Service":"lambda.amazonaws.com"},"Action":["ecr:BatchGetImage","ecr:GetDownloadUrlForLayer"],
        "Resource":REPOSITORY_ARN,"Condition":{"ArnEquals":{"aws:SourceArn":INGEST_ARN},
        "StringEquals":{"aws:SourceAccount":ACCOUNT}}}]}


def policy_exact(value):
    if isinstance(value,str):value=json.loads(value)
    return value==expected_policy()


def has_unknown(value):
    if isinstance(value,dict):return any(has_unknown(v) for v in value.values())
    if isinstance(value,list):return any(has_unknown(v) for v in value)
    return value is True


def unknown_at(value,path):
    for key in path:
        if value is True:return True
        try:value=value[key]
        except (KeyError,IndexError,TypeError):return False
    return has_unknown(value)


def managed(root):
    rows=[r for r in BASE.resources(root) if r.get("mode")=="managed"]
    require(len(rows)==len({r["address"] for r in rows}),"Duplicate resource address")
    return {r["address"]:r["values"] for r in rows}


def at(value,path):
    for key in path:
        try:value=value[key]
        except (KeyError,IndexError,TypeError):return None
    return value


def inspect_plan(document,image,*,root_inventory_while_paused=False):
    require(type(root_inventory_while_paused) is bool,"Root inventory review opt-in must be an explicit boolean")
    require(IMAGE_PATTERN.fullmatch(image),"Exact personal immutable ingest manifest URI required")
    prior=managed(document["prior_state"]["values"]["root_module"])
    planned=managed(document["planned_values"]["root_module"])
    foundation=BASE.expected_addresses()
    require(len(foundation)==55 and set(prior)==foundation and set(planned)==foundation|ADDITIONS,"Expected exact 55 -> 59 resource set")
    identities=[r.get("values",{}).get("account_id") for root in (
        document["prior_state"]["values"]["root_module"],document["planned_values"]["root_module"])
        for r in BASE.resources(root) if r.get("mode")=="data" and r.get("type")=="aws_caller_identity"]
    require(identities and set(identities)=={ACCOUNT},"Expected personal account identity is missing/different")
    if root_inventory_while_paused:
        expression=document.get("configuration",{}).get("root_module",{}).get("module_calls",{}).get("ecoguard",{}).get("expressions",{}).get("allow_root_bucket_inventory_while_paused")
        require(isinstance(expression,dict) and set(expression)=={"constant_value"}
                and expression["constant_value"] is True,"Root inventory requires the exact constant-true module input")
        caller_rows=[r for root in (document["prior_state"]["values"]["root_module"],document["planned_values"]["root_module"])
            for r in BASE.resources(root) if r.get("mode")=="data" and r.get("type")=="aws_caller_identity"]
        require(all(r.get("values",{}).get("arn")==f"arn:aws:iam::{ACCOUNT}:root" for r in caller_rows),
                "Root inventory review requires the exact account-root caller")
        caller_addresses={r["address"] for r in caller_rows}
        caller_changes=[r.get("change",{}) for r in document.get("resource_changes",[]) if r.get("address") in caller_addresses]
        require(all(not has_unknown(c.get("after_unknown",{})) and isinstance(c.get("after"),dict)
            and c["after"].get("account_id")==ACCOUNT and c["after"].get("arn")==f"arn:aws:iam::{ACCOUNT}:root"
            for c in caller_changes),"Root caller identity is unknown/inconsistent")
    require(document.get("complete") is True and document.get("errored") is not True
            and not document.get("resource_drift") and not document.get("deferred_changes"),"Drift/incomplete/deferred plan")
    changes=[r for r in document.get("resource_changes",[]) if r.get("mode")=="managed"]
    require(len(changes)==59 and {r.get("address") for r in changes}==set(planned),"Resource changes are not exact fifty-nine")
    by_address={r["address"]:r for r in changes}
    for row in changes:
        address=row["address"];change=row.get("change",{})
        actions=["create"] if address in ADDITIONS else ["update"] if address in UPDATES else ["no-op"]
        require(change.get("actions")==actions and not any(row.get(k) or change.get(k) for k in ("previous_address","deposed","importing","replace_paths")),"Unexpected action/move/import/replacement")
        require(change.get("before")==(None if address in ADDITIONS else prior[address]),"Change before differs from refreshed prior")
        if address not in ADDITIONS|UPDATES:
            require(change.get("after")==prior[address]==planned[address] and not has_unknown(change.get("after_unknown")),"An expected no-op differs/is unknown")
    def known(address,paths):
        return all(not unknown_at(by_address[address]["change"].get("after_unknown",{}),path)
                   and at(by_address[address]["change"].get("after",{}),path)==at(planned[address],path) for path in paths)
    require(known(POLICY,[("repository",),("policy",)]) and planned[POLICY].get("repository")==REPOSITORY
            and policy_exact(planned[POLICY].get("policy")) and policy_exact(by_address[POLICY]["change"].get("after",{}).get("policy")),"ECR repository target/least-privilege policy differs or is unknown")
    for address in [MODULE+f'aws_lambda_function.zip["{name}"]' for name in BASE.FUNCTIONS]+[INGEST]:
        function=planned[address]
        require(known(address,[("reserved_concurrent_executions",),("role",)])
                and type(function.get("reserved_concurrent_executions")) is int and function["reserved_concurrent_executions"]==0
                and function.get("role")==BASE.EXECUTION_ROLE,"A function is not paused/on the dedicated role")
    ingest=planned[INGEST]
    require(known(INGEST,[("package_type",),("image_uri",),("function_name",),("architectures",),("timeout",),("memory_size",),("image_config",)])
            and ingest.get("package_type")=="Image" and ingest.get("image_uri")==image and ingest.get("function_name")==PREFIX+"-ingest"
            and ingest.get("architectures")==["x86_64"] and ingest.get("timeout")==120 and ingest.get("memory_size")==2048
            and len(ingest.get("image_config",[]))==1 and ingest["image_config"][0].get("command")==["ecoguard_aws.handlers.ingest"]
            and not ingest["image_config"][0].get("entry_point") and not ingest["image_config"][0].get("working_directory"),"Ingest image/config differs")
    for name in BASE.FUNCTIONS:
        address=MODULE+f'aws_lambda_function.zip["{name}"]'
        require(known(address,[("filename",),("source_code_hash",)]) and planned[address].get("source_code_hash")==prior[address].get("source_code_hash")
                and planned[address].get("filename")==prior[address].get("filename"),"Existing ZIP package changed")
    role_policy=MODULE+"aws_iam_role_policy.runtime[0]"
    require(known(role_policy,[("policy",),("role",)]),"Runtime policy/role is unknown/inconsistent")
    old_policy=json.loads(prior[role_policy]["policy"]);new_policy=json.loads(planned[role_policy]["policy"])
    require({k:v for k,v in planned[role_policy].items() if k!="policy"}=={k:v for k,v in prior[role_policy].items() if k!="policy"},"Runtime policy ownership/metadata changed")
    expected_role_policy=copy.deepcopy(old_policy)
    log_statements=[s for s in expected_role_policy["Statement"] if s.get("Sid")=="ProjectFunctionLogs"]
    require(len(log_statements)==1,"Missing/duplicate runtime log permission statement")
    log_statements[0]["Resource"]=sorted(log_statements[0]["Resource"]+[f"arn:aws:logs:{REGION}:{ACCOUNT}:log-group:/aws/lambda/{PREFIX}-ingest:log-stream:*"])
    actual_role_policy=copy.deepcopy(new_policy)
    for statement in actual_role_policy.get("Statement",[]):
        if statement.get("Sid")=="ProjectFunctionLogs":statement["Resource"]=sorted(statement["Resource"])
    require(actual_role_policy==expected_role_policy,"Runtime policy changed beyond the new ingest log stream")
    mappings=[MODULE+f'aws_lambda_event_source_mapping.zip_queues["{name}"]' for name in ("infer","delete","notify")]+[MAPPING]
    require(all(known(a,[("enabled",),("scaling_config",)]) and planned[a].get("enabled") is False and planned[a].get("scaling_config")==[] for a in mappings),"A queue consumer/scaling cap is active/unknown")
    require(planned[LOG].get("name")=="/aws/lambda/"+PREFIX+"-ingest" and planned[LOG].get("retention_in_days")==7,"Ingest log group differs")
    require(planned[MODULE+"aws_apigatewayv2_api.app[0]"].get("disable_execute_api_endpoint") is True,"API endpoint is active")
    signup=planned[MODULE+"aws_cognito_user_pool.users"].get("admin_create_user_config",[])
    require(len(signup)==1 and signup[0].get("allow_admin_create_user_only") is True,"Public signup is active")
    require(all(planned[MODULE+f'aws_cloudwatch_event_rule.maintenance["{name}"]'].get("state")=="DISABLED" for name in ("outbox","cleanup")),"A maintenance schedule is active")
    bucket_checks=[];BASE.inspect_bucket_security(lambda suffix:planned.get(MODULE+suffix,{}),lambda name,passed:bucket_checks.append((name,bool(passed))),
        root_inventory_while_paused=root_inventory_while_paused)
    require(all(passed for _,passed in bucket_checks),"Bucket pause/privacy boundary differs")
    require(not any("aws_s3_bucket_notification." in address for address in planned),"Upload destinations are managed/active")
    return {"status":"focused-ecr-policy-paused-profile-passed","projectAccount":ACCOUNT,"region":REGION,
        "priorManagedResources":55,"managedResources":59,"creates":4,"updates":8,"noops":47,
        "policyPrincipal":"lambda.amazonaws.com","sourceFunctionArn":INGEST_ARN,"repositoryArn":REPOSITORY_ARN,
        "allFunctionsReservedZero":True,"rootInventoryWhilePausedReviewed":root_inventory_while_paused,
        "applicationInvoked":False,"fullIncrementGatePassed":False,"applyAuthorized":False,"cloudVerified":False,
        "remaining":"Complete existing-state value/security/provenance/refresh gate and real Terraform/provider plan are still required."}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--plan-json",required=True,type=Path);parser.add_argument("--image",required=True)
    parser.add_argument("--root-inventory-while-paused",action="store_true",help="Review only the explicitly configured, exact-root listing exception")
    args=parser.parse_args()
    try:report=inspect_plan(json.loads(args.plan_json.read_text()),args.image,root_inventory_while_paused=args.root_inventory_while_paused)
    except (ValueError,KeyError,TypeError,OSError) as error:
        print(json.dumps({"status":"blocked","applyAuthorized":False,"reason":str(error)}));return 1
    print(json.dumps(report,indent=2));return 0


if __name__=="__main__":raise SystemExit(main())
