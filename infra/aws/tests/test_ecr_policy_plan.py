"""Synthetic JSON plan checks only; no AWS SDK, Terraform, state or real ZIP."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
GATE=load("focused_ecr_gate",HERE.parent/"environments/personal/check_ecr_policy_plan.py")
FIRST=load("foundation_ecr_fixture",HERE/"test_personal_plan.py")
IMAGE=f"{GATE.ACCOUNT}.dkr.ecr.{GATE.REGION}.amazonaws.com/{GATE.REPOSITORY}@sha256:"+"0"*64


def fixture():
    doc=FIRST.plan_fixture();prior=copy.deepcopy(doc["planned_values"]);planned=copy.deepcopy(prior)
    rows=planned["root_module"]["child_modules"][0]["resources"]
    table={r["address"]:r["values"] for r in rows if r["mode"]=="managed"}
    for name in GATE.BASE.FUNCTIONS:
        table[GATE.MODULE+f'aws_lambda_function.zip["{name}"]']["environment"]=[{"variables":{
            "ECO_INFERENCE_URL":"https://ecoguard-inference-adlnb7yumq-uc.a.run.app",
            "ECO_GOOGLE_INVOKER_EMAIL":"ecoguard-aws-invoker@ecoguard-fit3184-a2-2026.iam.gserviceaccount.com"}}]
    role_policy=table[GATE.MODULE+"aws_iam_role_policy.runtime[0]"]
    policy=json.loads(role_policy["policy"])
    next(s for s in policy["Statement"] if s["Sid"]=="ProjectFunctionLogs")["Resource"].append(
        f"arn:aws:logs:{GATE.REGION}:{GATE.ACCOUNT}:log-group:/aws/lambda/{GATE.PREFIX}-ingest:log-stream:*")
    role_policy["policy"]=json.dumps(policy)
    additions={GATE.POLICY:{"repository":GATE.REPOSITORY,"policy":json.dumps(GATE.expected_policy())},
        GATE.INGEST:{"reserved_concurrent_executions":0,"role":GATE.BASE.EXECUTION_ROLE,"package_type":"Image",
            "image_uri":IMAGE,"function_name":GATE.PREFIX+"-ingest","architectures":["x86_64"],"timeout":120,"memory_size":2048,
            "image_config":[{"command":["ecoguard_aws.handlers.ingest"],"entry_point":[],"working_directory":""}]},
        GATE.MAPPING:{"enabled":False,"scaling_config":[]},
        GATE.LOG:{"name":"/aws/lambda/"+GATE.PREFIX+"-ingest","retention_in_days":7}}
    for address,value in additions.items():
        rows.append({"address":address,"mode":"managed","type":address[len(GATE.MODULE):].split(".")[0],"values":value})
    before={r["address"]:r["values"] for r in prior["root_module"]["child_modules"][0]["resources"] if r["mode"]=="managed"}
    doc.update(complete=True,errored=False,prior_state={"values":prior},planned_values=planned)
    doc["resource_changes"]=[{"address":r["address"],"mode":"managed","type":r["type"],"change":{
        "actions":["create"] if r["address"] in GATE.ADDITIONS else ["update"] if r["address"] in GATE.UPDATES else ["no-op"],
        "before":copy.deepcopy(before.get(r["address"])),"after":copy.deepcopy(r["values"]),"after_unknown":{}}}
        for r in rows if r["mode"]=="managed"]
    return doc


def value(doc,address):
    return next(r["values"] for r in GATE.BASE.resources(doc["planned_values"]["root_module"]) if r["address"]==address)
def change(doc,address):return next(r["change"] for r in doc["resource_changes"] if r["address"]==address)
def mutate_value(doc,address,operation):
    operation(value(doc,address));operation(change(doc,address)["after"])


class FocusedEcrTests(unittest.TestCase):
    def rejected(self,doc):
        with self.assertRaises((ValueError,TypeError,KeyError)):GATE.inspect_plan(doc,IMAGE)

    def test_exact_four_creates_keep_all_59_paused_without_apply_claim(self):
        result=GATE.inspect_plan(fixture(),IMAGE)
        self.assertEqual((result["priorManagedResources"],result["managedResources"],result["creates"],result["updates"],result["noops"]),(55,59,4,8,47))
        self.assertTrue(result["allFunctionsReservedZero"])
        self.assertFalse(result["fullIncrementGatePassed"]);self.assertFalse(result["applyAuthorized"])

    def test_service_function_account_region_actions_and_resource_are_exact(self):
        operations=[lambda p:p["Statement"][0].update(Principal="*"),
            lambda p:p["Statement"][0]["Action"].append("ecr:PutImage"),
            lambda p:p["Statement"][0].update(Resource="*"),
            lambda p:p["Statement"][0]["Condition"]["ArnEquals"].update({"aws:SourceArn":GATE.INGEST_ARN+":*"}),
            lambda p:p["Statement"][0]["Condition"]["ArnEquals"].update({"aws:SourceArn":GATE.INGEST_ARN.replace("us-east-1","ap-southeast-2")}),
            lambda p:p["Statement"][0]["Condition"]["StringEquals"].update({"aws:SourceAccount":"360493183467"}),
            lambda p:p["Statement"][0]["Condition"].pop("StringEquals"),
            lambda p:p["Statement"].append(copy.deepcopy(p["Statement"][0]))]
        for index,operation in enumerate(operations):
            with self.subTest(index=index):
                doc=fixture();policy=GATE.expected_policy();operation(policy)
                mutate_value(doc,GATE.POLICY,lambda v:v.update(policy=json.dumps(policy)));self.rejected(doc)

    def test_repository_target_and_unknown_policy_are_rejected(self):
        doc=fixture();mutate_value(doc,GATE.POLICY,lambda v:v.update(repository="unrelated-worker"));self.rejected(doc)
        doc=fixture();change(doc,GATE.POLICY)["after_unknown"]={"policy":True};self.rejected(doc)
        doc=fixture();change(doc,GATE.POLICY)["after"]["repository"]="unrelated-worker";self.rejected(doc)

    def test_wrong_account_data_cannot_pass_the_focused_gate(self):
        doc=fixture()
        next(r["values"] for r in GATE.BASE.resources(doc["planned_values"]["root_module"]) if r.get("type")=="aws_caller_identity")["account_id"]="360493183467"
        self.rejected(doc)

    def test_extra_create_missing_policy_delete_replace_import_drift_are_rejected(self):
        for kind in ("extra","missing","delete","replace","import","drift"):
            with self.subTest(kind=kind):
                doc=fixture()
                if kind=="extra":doc["resource_changes"].append(copy.deepcopy(doc["resource_changes"][0]))
                elif kind=="missing":doc["resource_changes"]=[r for r in doc["resource_changes"] if r["address"]!=GATE.POLICY]
                elif kind=="delete":change(doc,GATE.INGEST)["actions"]=["delete"]
                elif kind=="replace":change(doc,GATE.INGEST)["actions"]=["delete","create"]
                elif kind=="import":change(doc,GATE.POLICY)["importing"]={"id":"existing"}
                else:doc["resource_drift"]=[{"address":GATE.LOG}]
                self.rejected(doc)

    def test_reservation_polling_endpoint_signup_schedule_and_bucket_cannot_activate(self):
        cases=[(GATE.INGEST,lambda v:v.update(reserved_concurrent_executions=1)),
            (GATE.MAPPING,lambda v:v.update(enabled=True)),
            (GATE.MODULE+"aws_apigatewayv2_api.app[0]",lambda v:v.update(disable_execute_api_endpoint=False)),
            (GATE.MODULE+"aws_cognito_user_pool.users",lambda v:v.update(admin_create_user_config=[{"allow_admin_create_user_only":False}])),
            (GATE.MODULE+'aws_cloudwatch_event_rule.maintenance["outbox"]',lambda v:v.update(state="ENABLED")),
            (GATE.MODULE+"aws_s3_bucket_policy.media_tls",lambda v:v.update(policy='{"Version":"2012-10-17","Statement":[]}'))]
        for address,operation in cases:
            with self.subTest(address=address):
                doc=fixture();mutate_value(doc,address,operation);self.rejected(doc)

    def test_no_runtime_role_ecr_or_admin_permissions(self):
        for action in ("ecr:BatchGetImage","iam:PassRole","*"):
            with self.subTest(action=action):
                doc=fixture();address=GATE.MODULE+"aws_iam_role_policy.runtime[0]"
                policy=json.loads(value(doc,address)["policy"]);policy["Statement"][0]["Action"].append(action)
                mutate_value(doc,address,lambda v:v.update(policy=json.dumps(policy)));self.rejected(doc)


if __name__=="__main__":unittest.main()
