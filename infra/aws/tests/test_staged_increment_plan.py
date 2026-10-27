"""Meaningful pure fixtures for the full paused increment; no cloud/tool/ZIP."""
import base64
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
G=load("full_increment_gate",HERE.parent/"environments/personal/check_staged_increment_plan.py")
P=load("inert_increment_preparer",HERE.parents[2]/"scripts/prepare_aws_staged_increment.py")
F=load("increment_foundation_fixture",HERE/"test_personal_plan.py")
E=load("increment_focused_fixture",HERE/"test_ecr_policy_plan.py")
ZIP="/fixture/readonly-reviewed.zip"
IMAGE=E.IMAGE
WIF={"type":"external_account","audience":"//iam.googleapis.com/projects/995070689587/locations/global/workloadIdentityPools/ecoguard-aws/providers/aws-role",
    "subject_token_type":"urn:ietf:params:aws:token-type:aws4_request","token_url":"https://sts.googleapis.com/v1/token",
    "service_account_impersonation_url":"https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/"+G.INVOKER+":generateAccessToken",
    "universe_domain":"googleapis.com","credential_source":{"environment_id":"aws1",
    "region_url":"http://169.254.169.254/latest/meta-data/placement/availability-zone",
    "regional_cred_verification_url":"https://sts.{region}.amazonaws.com?Action=GetCallerIdentity&Version=2011-06-15",
    "url":"http://169.254.169.254/latest/meta-data/iam/security-credentials"}}


def table(document):return G.FOCUS.managed(document["root_module"])
def fixture():
    # Add provider-shaped, known safe defaults to the old first-plan fixture.
    doc=F.plan_fixture();prior=copy.deepcopy(doc["planned_values"]);old=table(prior)
    for name in G.BASE.FUNCTIONS:
        value=old[G.MODULE+f'aws_lambda_function.zip["{name}"]']
        value.update(filename=ZIP,source_code_hash=base64.b64encode(bytes.fromhex(G.ZIP_SHA)).decode(),
            package_type="Zip",image_uri=None,handler="ecoguard_aws.handlers."+name,
            timeout=120,memory_size=512,ephemeral_storage=[{"size":512}],publish=False,
            logging_config=[{"log_format":"Text","log_group":"/aws/lambda/"+G.PREFIX+"-"+name,
                "application_log_level":"","system_log_level":""}],tracing_config=[{"mode":"PassThrough"}],
            image_config=[],layers=[],vpc_config=[],file_system_config=[],dead_letter_config=[],snap_start=[],
            kms_key_arn="",source_kms_key_arn="",code_signing_config_arn="",last_modified="2026-10-23T00:00:00.000+0000",
            capacity_provider_config=[],durable_config=[],tenancy_config=[],tags={},tags_all={"Project":"FIT3184-A2","Application":"AussieEcoGuard","Environment":"personal"},
            skip_destroy=False,region=G.REGION,description="",s3_bucket=None,s3_key=None,s3_object_version=None,
            environment=[{"variables":{"ECO_INFERENCE_URL":"","ECO_GOOGLE_INVOKER_EMAIL":"",
                "ECO_GOOGLE_CREDENTIALS_FILE":"/var/task/config/google-wif.json","ECO_OTHER":"unchanged"}}])
        old[G.MODULE+f'aws_cloudwatch_log_group.functions["{name}"]'].update(name="/aws/lambda/"+G.PREFIX+"-"+name,
            retention_in_days=7,skip_destroy=False,log_group_class="STANDARD",kms_key_id="",name_prefix="",
            deletion_protection_enabled=False,tags={},tags_all={"Project":"FIT3184-A2","Application":"AussieEcoGuard","Environment":"personal"},region=G.REGION)
    for name in ("infer","delete","notify"):
        old[G.MODULE+f'aws_lambda_event_source_mapping.zip_queues["{name}"]'].update(
            function_name=f"arn:aws:lambda:{G.REGION}:{G.ACCOUNT}:function:{G.PREFIX}-{name}",
            event_source_arn=f"arn:aws:sqs:{G.REGION}:{G.ACCOUNT}:{G.PREFIX}-{name}",
            batch_size=1,function_response_types=["ReportBatchItemFailures"],maximum_batching_window_in_seconds=0,
            filter_criteria=[],destination_config=[],provisioned_poller_config=[],metrics_config=[],kms_key_arn="",
            topics=[],queues=[],source_access_configuration=[],self_managed_event_source=[],amazon_managed_kafka_event_source_config=[],
            self_managed_kafka_event_source_config=[],document_db_event_source_config=[],tumbling_window_in_seconds=0,
            starting_position="",starting_position_timestamp="",bisect_batch_on_function_error=False,
            maximum_record_age_in_seconds=0,maximum_retry_attempts=0,parallelization_factor=0,region=G.REGION,tags={},tags_all={})
    old[G.MODULE+'aws_sqs_queue.work["ingest"]']["arn"]=f"arn:aws:sqs:{G.REGION}:{G.ACCOUNT}:{G.PREFIX}-ingest"
    planned=copy.deepcopy(prior);future=table(planned)
    for address in G.ZIP_FUNCTIONS:future[address]["environment"][0]["variables"].update(G.ENV_BINDINGS)
    policy=json.loads(future[G.ROLE_POLICY]["policy"])
    next(s for s in policy["Statement"] if s["Sid"]=="ProjectFunctionLogs")["Resource"].append(
        f"arn:aws:logs:{G.REGION}:{G.ACCOUNT}:log-group:/aws/lambda/{G.PREFIX}-ingest:log-stream:*")
    future[G.ROLE_POLICY]["policy"]=json.dumps(policy)
    log=copy.deepcopy(old[G.MODULE+'aws_cloudwatch_log_group.functions["api"]']);log["name"]="/aws/lambda/"+G.PREFIX+"-ingest"
    ingest=G.strip_outputs(old[G.MODULE+'aws_lambda_function.zip["api"]'],G.NEW_READONLY[G.FOCUS.INGEST])
    ingest.update(function_name=G.PREFIX+"-ingest",package_type="Image",image_uri=IMAGE,filename=None,handler=None,runtime=None,
        source_code_hash=None,timeout=120,memory_size=2048,ephemeral_storage=[{"size":1024}],
        image_config=[{"command":["ecoguard_aws.handlers.ingest"],"entry_point":[],"working_directory":""}],
        environment=copy.deepcopy(future[G.MODULE+'aws_lambda_function.zip["api"]']["environment"]))
    ingest["logging_config"][0]["log_group"]="/aws/lambda/"+G.PREFIX+"-ingest"
    mapping=copy.deepcopy(old[G.MODULE+'aws_lambda_event_source_mapping.zip_queues["infer"]'])
    mapping.update(function_name=G.FOCUS.INGEST_ARN,event_source_arn=old[G.MODULE+'aws_sqs_queue.work["ingest"]']["arn"])
    additions={G.FOCUS.LOG:log,G.FOCUS.INGEST:ingest,G.FOCUS.MAPPING:mapping,G.FOCUS.POLICY:{
        "repository":G.FOCUS.REPOSITORY,"region":G.REGION,"policy":json.dumps(G.FOCUS.expected_policy())}}
    rows=planned["root_module"]["child_modules"][0]["resources"]
    rows.extend({"address":a,"mode":"managed","type":a[len(G.MODULE):].split(".")[0],"values":v} for a,v in additions.items())
    doc.update(complete=True,errored=False,resource_drift=[],prior_state={"values":prior},planned_values=planned,
        variables={k:{"value":v} for k,v in {"deployment_stage":"wiring-paused","lambda_zip":ZIP,"worker_image":IMAGE,"inference_url":G.RUN_URL}.items()})
    doc["resource_changes"]=[{"address":r["address"],"mode":"managed","type":r["type"],"change":{
        "actions":["create"] if r["address"] in additions else ["update"] if r["address"] in G.FOCUS.UPDATES else ["no-op"],
        "before":copy.deepcopy(old.get(r["address"])),"after":copy.deepcopy(r["values"]),"after_unknown":{}}}
        for r in rows if r["mode"]=="managed"]
    return doc,{"values":copy.deepcopy(prior)}


def review(doc,physical):return G.inspect_plan(doc,physical,image=IMAGE,zip_sha=G.ZIP_SHA,zip_filename=ZIP,run_url=G.RUN_URL,wif=copy.deepcopy(WIF))
def change(doc,address):return E.change(doc,address)
def mutate(doc,address,operation):E.mutate_value(doc,address,operation)


class IncrementTests(unittest.TestCase):
    def rejected(self,doc,physical):
        with self.assertRaises((ValueError,KeyError,TypeError)):review(doc,physical)

    def test_full_fifty_five_and_exact_actions_with_no_cloud_or_apply_claim(self):
        report=review(*fixture())
        self.assertEqual((report["creates"],report["updates"],report["noops"],report["existingFullValuesCompared"]),(4,8,47,55))
        self.assertTrue(report["fullIncrementGatePassed"])
        for name in ("applyAuthorized","cloudVerified","imageProvenanceVerified","googleRunProvenanceVerified"):self.assertFalse(report[name])

    def test_raw_checkpoint_binds_bytes_lineage_serial_count_and_taint(self):
        raw={"lineage":"fixture-lineage","serial":60,"resources":[{"mode":"managed","instances":[{} for _ in range(55)]}]}
        def check(value,sha=None,lineage="fixture-lineage",serial=60):
            data=json.dumps(value).encode();return G.raw_checkpoint(data,sha or hashlib.sha256(data).hexdigest(),lineage,serial)
        check(raw)
        for kind in ("hash","lineage","serial","count","taint","deposed"):
            with self.subTest(kind=kind):
                value=copy.deepcopy(raw)
                if kind=="count":value["resources"][0]["instances"].pop()
                if kind in ("taint","deposed"):value["resources"][0]["instances"][0].update({"status":"tainted"} if kind=="taint" else {"deposed":"old"})
                with self.assertRaises(ValueError):check(value,sha="0"*64 if kind=="hash" else None,
                    lineage="other" if kind=="lineage" else "fixture-lineage",serial=59 if kind=="serial" else 60)

    def test_physical_prior_drift_and_false_s3_create_cannot_be_hidden(self):
        for kind in ("physical","prior","drift","s3create"):
            with self.subTest(kind=kind):
                doc,physical=fixture();address=G.MODULE+"aws_s3_bucket_public_access_block.media"
                if kind=="physical":G.values(physical)[address]["bucket"]="unrelated-bucket"
                elif kind=="prior":table(doc["prior_state"]["values"])[address]["bucket"]="unrelated-bucket"
                elif kind=="drift":doc["resource_drift"]=[{"address":address}]
                else:change(doc,address).update(actions=["create"],before=None)
                self.rejected(doc,physical)

    def test_two_environment_keys_are_the_only_seven_existing_zip_edits(self):
        operations=[lambda v:v["environment"][0]["variables"].update(ECO_OTHER="different"),
            lambda v:v["environment"][0]["variables"].update(ECO_GOOGLE_CREDENTIALS_FILE="/tmp/other.json"),
            lambda v:v.update(filename="/fixture/other.zip"),lambda v:v.update(timeout=121),
            lambda v:v.update(source_code_hash="changed"),lambda v:v.update(layers=["arn:extra"])]
        for name in G.BASE.FUNCTIONS:
            for index,operation in enumerate(operations):
                with self.subTest(name=name,mutation=index):
                    doc,physical=fixture();mutate(doc,G.MODULE+f'aws_lambda_function.zip["{name}"]',operation);self.rejected(doc,physical)

    def test_only_pure_unknown_last_modified_is_tolerated_for_existing_zip(self):
        address=G.MODULE+'aws_lambda_function.zip["api"]'
        doc,physical=fixture();change(doc,address)["after_unknown"]={"last_modified":True}
        mutate(doc,address,lambda v:v.update(last_modified=None));review(doc,physical)
        for kind in ("known","contradiction","security","nested"):
            with self.subTest(kind=kind):
                doc,physical=fixture()
                if kind=="known":mutate(doc,address,lambda v:v.update(last_modified="changed"))
                elif kind=="contradiction":change(doc,address)["after_unknown"]={"last_modified":True}
                elif kind=="security":change(doc,address)["after_unknown"]={"environment":True}
                else:change(doc,address)["after_unknown"]={"last_modified":{"hidden":True}}
                self.rejected(doc,physical)

    def test_new_security_unknowns_and_unknown_known_contradictions_block(self):
        cases=[(G.FOCUS.INGEST,"logging_config"),(G.FOCUS.INGEST,"tracing_config"),
            (G.FOCUS.INGEST,"environment"),(G.FOCUS.INGEST,"image_config"),(G.FOCUS.INGEST,"role"),
            (G.FOCUS.INGEST,"reserved_concurrent_executions"),(G.FOCUS.INGEST,"layers"),
            (G.FOCUS.MAPPING,"function_name"),(G.FOCUS.MAPPING,"filter_criteria"),
            (G.FOCUS.MAPPING,"event_source_arn"),(G.FOCUS.MAPPING,"enabled"),(G.FOCUS.MAPPING,"scaling_config"),
            (G.FOCUS.MAPPING,"starting_position"),(G.FOCUS.MAPPING,"topics"),(G.FOCUS.MAPPING,"queues"),
            (G.FOCUS.LOG,"kms_key_id"),(G.FOCUS.LOG,"deletion_protection_enabled"),
            (G.FOCUS.LOG,"log_group_class"),(G.FOCUS.LOG,"tags"),(G.FOCUS.POLICY,"policy")]
        for address,field in cases:
            with self.subTest(address=address,field=field):
                doc,physical=fixture();change(doc,address)["after_unknown"]={field:True};mutate(doc,address,lambda v:v.update({field:None}));self.rejected(doc,physical)
        doc,physical=fixture();change(doc,G.FOCUS.INGEST)["after_unknown"]={"arn":True}
        mutate(doc,G.FOCUS.INGEST,lambda v:v.update(arn=None));review(doc,physical)
        mutate(doc,G.FOCUS.INGEST,lambda v:v.update(arn="arn:wrong"));self.rejected(doc,physical)

    def test_actual_new_resource_unknown_catalog_and_exact_unset_spellings_pass(self):
        # Actual provider6.67 plan catalog, after HCL makes log protection/class,
        # Lambda logging/tracing and tags known. No blanket computed wildcard.
        catalog={G.FOCUS.LOG:{"arn","id","name_prefix"},G.FOCUS.POLICY:{"id","registry_id"},
            G.FOCUS.INGEST:{"arn","id","code_sha256","source_code_hash","invoke_arn","last_modified",
                "qualified_arn","qualified_invoke_arn","response_streaming_invoke_arn","signing_job_arn",
                "signing_profile_version_arn","source_code_size","version"},
            G.FOCUS.MAPPING:{"arn","id","function_arn","last_modified","last_processing_result","state",
                "state_transition_reason","uuid","amazon_managed_kafka_event_source_config",
                "self_managed_kafka_event_source_config","maximum_record_age_in_seconds","maximum_retry_attempts","parallelization_factor"}}
        doc,physical=fixture()
        for address,fields in catalog.items():
            change(doc,address)["after_unknown"]={field:True for field in fields}
            mutate(doc,address,lambda v,fields=fields:v.update({field:None for field in fields}))
        mutate(doc,G.FOCUS.LOG,lambda v:v.update(kms_key_id=None))
        def unset_image(value):
            value.update({field:None for field in ("description","kms_key_arn","source_kms_key_arn","code_signing_config_arn","layers")})
            value["logging_config"][0].update(application_log_level=None,system_log_level=None)
            value["image_config"][0].update(entry_point=None,working_directory=None)
        mutate(doc,G.FOCUS.INGEST,unset_image)
        mutate(doc,G.FOCUS.MAPPING,lambda v:v.update({field:None for field in ("bisect_batch_on_function_error","kms_key_arn","queues","topics","starting_position","starting_position_timestamp","tumbling_window_in_seconds")}))
        report=review(doc,physical)
        self.assertEqual((report["creates"],report["updates"],report["noops"]),(4,8,47))
        self.assertEqual({address:{tuple(path) for path in paths} for address,paths in report["newResourceReviewedComputedUnknownPaths"].items()},
            {address:{(field,) for field in fields} for address,fields in catalog.items()})
        self.assertFalse(report["applyAuthorized"])

    def test_only_three_new_tags_accept_the_observed_known_null_or_empty_map(self):
        for tags in (None,{}):
            with self.subTest(tags=tags):
                doc,physical=fixture()
                for address in (G.FOCUS.LOG,G.FOCUS.INGEST,G.FOCUS.MAPPING):
                    mutate(doc,address,lambda value:value.update(tags=copy.deepcopy(tags)))
                report=review(doc,physical)
                self.assertEqual((report["creates"],report["updates"],report["noops"]),(4,8,47))
                self.assertFalse(report["applyAuthorized"])

    def test_new_empty_tags_reject_missing_nonempty_wrong_types_and_unknowns(self):
        for address in (G.FOCUS.LOG,G.FOCUS.INGEST,G.FOCUS.MAPPING):
            for kind,tags in (("missing",None),("nonempty",{"unexpected":"tag"}),("list",[]),
                    ("string",""),("bool",False),("number",0),("unknown",None),("nested_unknown",{})):
                with self.subTest(address=address,kind=kind):
                    doc,physical=fixture()
                    mutate(doc,address,lambda value:value.pop("tags",None) if kind=="missing" else value.update(tags=copy.deepcopy(tags)))
                    if kind=="unknown":change(doc,address)["after_unknown"]={"tags":True}
                    if kind=="nested_unknown":change(doc,address)["after_unknown"]={"tags":{"hidden":True}}
                    self.rejected(doc,physical)

    def test_new_tag_change_and_planned_representations_must_still_be_equal(self):
        for address in (G.FOCUS.LOG,G.FOCUS.INGEST,G.FOCUS.MAPPING):
            for side in ("change","planned"):
                with self.subTest(address=address,side=side):
                    doc,physical=fixture()
                    if side=="change":change(doc,address)["after"]["tags"]=None
                    else:table(doc["planned_values"])[address]["tags"]=None
                    self.rejected(doc,physical)

    def test_new_tag_allowance_requires_original_typed_empty_template(self):
        profiles=(G.MODULE+'aws_cloudwatch_log_group.functions["api"]',
            G.MODULE+'aws_lambda_function.zip["api"]',
            G.MODULE+'aws_lambda_event_source_mapping.zip_queues["infer"]')
        for address in profiles:
            for kind,tags in (("missing",None),("null",None),("list",[]),("nonempty",{"existing":"tag"})):
                with self.subTest(address=address,kind=kind):
                    doc,physical=fixture()
                    values=(G.values(physical)[address],table(doc["prior_state"]["values"])[address],
                        table(doc["planned_values"])[address],change(doc,address)["before"],change(doc,address)["after"])
                    for value in values:
                        if kind=="missing":value.pop("tags",None)
                        else:value["tags"]=copy.deepcopy(tags)
                    self.rejected(doc,physical)

    def test_old_fifty_five_tags_and_new_tags_all_remain_exact(self):
        for address in sorted(G.BASE.expected_addresses()):
            with self.subTest(existing=address):
                doc,physical=fixture();mutate(doc,address,lambda value:value.update(tags=None));self.rejected(doc,physical)
        for address in (G.FOCUS.LOG,G.FOCUS.INGEST,G.FOCUS.MAPPING):
            with self.subTest(tags_all=address):
                doc,physical=fixture();mutate(doc,address,lambda value:value.update(tags=None,tags_all=None));self.rejected(doc,physical)

    def test_ecr_policy_does_not_inherit_empty_tags_allowance(self):
        for tags in (None,{}):
            with self.subTest(tags=tags):
                doc,physical=fixture();mutate(doc,G.FOCUS.POLICY,lambda value:value.update(tags=copy.deepcopy(tags)));self.rejected(doc,physical)

    def test_projected_outputs_require_exact_image_and_disabled_sqs_context(self):
        cases=[(G.FOCUS.LOG,"name_prefix","arbitrary-"),(G.FOCUS.INGEST,"code_sha256","unreviewed-hash"),
            (G.FOCUS.INGEST,"source_code_hash","unreviewed-hash"),(G.FOCUS.INGEST,"filename","other.zip"),
            (G.FOCUS.INGEST,"package_type","Zip"),(G.FOCUS.MAPPING,"event_source_arn","arn:aws:kinesis:us-east-1:011154879765:stream/other"),
            (G.FOCUS.MAPPING,"enabled",True),(G.FOCUS.MAPPING,"maximum_retry_attempts",1),
            (G.FOCUS.MAPPING,"parallelization_factor",False),
            (G.FOCUS.MAPPING,"amazon_managed_kafka_event_source_config",[{"consumer_group_id":"other"}]),
            (G.FOCUS.MAPPING,"queues",["not-sqs"]),(G.FOCUS.MAPPING,"starting_position","LATEST"),
            (G.FOCUS.INGEST,"description","different"),(G.FOCUS.INGEST,"layers",["arn:extra"])]
        for address,field,value in cases:
            with self.subTest(address=address,field=field):
                doc,physical=fixture();mutate(doc,address,lambda v:v.update({field:value}));self.rejected(doc,physical)
        for address,field in ((G.FOCUS.LOG,"name_prefix"),(G.FOCUS.INGEST,"code_sha256"),(G.FOCUS.MAPPING,"maximum_retry_attempts")):
            with self.subTest(address=address,contradiction=field):
                doc,physical=fixture();change(doc,address)["after_unknown"]={field:True}
                # Unknown outputs cannot also carry the old known default.
                mutate(doc,address,lambda v:v.update({field:"" if address!=G.FOCUS.MAPPING else 0}));self.rejected(doc,physical)
        doc,physical=fixture();address=G.FOCUS.MAPPING
        change(doc,address)["after_unknown"]={"amazon_managed_kafka_event_source_config":[{"consumer_group_id":True}]}
        mutate(doc,address,lambda v:v.update(amazon_managed_kafka_event_source_config=[{"consumer_group_id":None}]))
        self.rejected(doc,physical)
        doc,physical=fixture();address=G.MODULE+'aws_lambda_function.zip["api"]'
        change(doc,address)["after_unknown"]={"source_code_hash":True}
        mutate(doc,address,lambda v:v.update(source_code_hash=None));self.rejected(doc,physical)

    def test_sqs_output_projection_still_requires_exact_old_inactive_profile(self):
        doc,physical=fixture();address=G.MODULE+'aws_lambda_event_source_mapping.zip_queues["infer"]'
        for value in (G.values(physical)[address],table(doc["prior_state"]["values"])[address],table(doc["planned_values"])[address],change(doc,address)["before"],change(doc,address)["after"]):
            value["maximum_retry_attempts"]=7
        change(doc,G.FOCUS.MAPPING)["after_unknown"]={"maximum_retry_attempts":True}
        mutate(doc,G.FOCUS.MAPPING,lambda v:v.update(maximum_retry_attempts=None))
        self.rejected(doc,physical)

    def test_every_new_profile_target_and_security_configuration_is_exact(self):
        cases=[(G.FOCUS.INGEST,lambda v:v.update(kms_key_arn="arn:extra")),
            (G.FOCUS.INGEST,lambda v:v.update(environment=[{"variables":{"ECO_INFERENCE_URL":G.RUN_URL}}])),
            (G.FOCUS.INGEST,lambda v:v.update(logging_config=[{"log_format":"JSON","log_group":"other"}])),
            (G.FOCUS.INGEST,lambda v:v.update(image_config=[{"command":["other"],"entry_point":[],"working_directory":""}])),
            (G.FOCUS.INGEST,lambda v:v.update(reserved_concurrent_executions=1)),
            (G.FOCUS.MAPPING,lambda v:v.update(function_name=G.FOCUS.INGEST_ARN+":alias")),
            (G.FOCUS.MAPPING,lambda v:v.update(event_source_arn="arn:other")),
            (G.FOCUS.MAPPING,lambda v:v.update(filter_criteria=[{"filter":[{"pattern":"{}"}]}])),
            (G.FOCUS.MAPPING,lambda v:v.update(enabled=True)),
            (G.FOCUS.LOG,lambda v:v.update(kms_key_id="arn:extra")),
            (G.FOCUS.LOG,lambda v:v.update(retention_in_days=0)),
            (G.FOCUS.POLICY,lambda v:v.update(repository="other")),
            (G.FOCUS.POLICY,lambda v:v.update(region="ap-southeast-2"))]
        for address,operation in cases:
            with self.subTest(address=address,operation=repr(operation)):
                doc,physical=fixture();mutate(doc,address,operation);self.rejected(doc,physical)

    def test_no_extra_iam_edges_or_changes_to_any_of_other_forty_seven_values(self):
        for address in sorted(G.BASE.expected_addresses()-G.FOCUS.UPDATES):
            with self.subTest(address=address):
                doc,physical=fixture();mutate(doc,address,lambda v:v.update(unexpected="change"));self.rejected(doc,physical)
        doc,physical=fixture();policy=json.loads(E.value(doc,G.ROLE_POLICY)["policy"])
        policy["Statement"][0]["Action"].append("iam:PassRole")
        mutate(doc,G.ROLE_POLICY,lambda v:v.update(policy=json.dumps(policy)));self.rejected(doc,physical)

    def test_exact_explicit_variables_and_public_wif_required(self):
        for key,value in (("deployment_stage","auth-smoke"),("lambda_zip","relative.zip"),("worker_image",IMAGE+"0"),("inference_url","https://example.com")):
            with self.subTest(key=key):
                doc,physical=fixture();doc["variables"][key]["value"]=value;self.rejected(doc,physical)
        wif=copy.deepcopy(WIF);wif["credential_source"]["url"]="https://example.com"
        with self.assertRaises(ValueError):G.inspect_plan(*fixture(),image=IMAGE,zip_sha=G.ZIP_SHA,zip_filename=ZIP,run_url=G.RUN_URL,wif=wif)


class PreparationTests(unittest.TestCase):
    def test_default_is_inert_and_prepare_rejects_pending_pins_before_subprocess(self):
        output=io.StringIO()
        with mock.patch.object(sys,"argv",["prepare"]),mock.patch.object(P.subprocess,"run",side_effect=AssertionError("No subprocess allowed")),contextlib.redirect_stdout(output):
            self.assertEqual(P.main(),0)
        self.assertEqual(json.loads(output.getvalue())["status"],"dry-run")
        with mock.patch.object(sys,"argv",["prepare","--prepare"]),mock.patch.object(sys,"platform","linux"),mock.patch.object(P.subprocess,"run",side_effect=AssertionError("No subprocess allowed")):
            with self.assertRaisesRegex(RuntimeError,"pins are missing"):P.main()

    def test_evidence_cannot_escape_scope_or_use_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary)/"task";base.mkdir();inside=base/"evidence.json";inside.write_text("{}")
            outside=Path(temporary)/"outside.json";outside.write_text("{}")
            (base/"link.json").symlink_to(inside)
            with mock.patch.object(P,"BASE",base):
                self.assertEqual(P.scoped_path(str(inside)),inside)
                for path in (outside,base/"missing.json",base/"link.json",Path("relative.json")):
                    with self.subTest(path=str(path)),self.assertRaises(RuntimeError):P.scoped_path(str(path))

    def test_publication_run_and_policy_absence_are_hash_bound_and_scope_checked(self):
        # Opaque ZIP bytes are not executed; its reviewed SHA is represented by
        # a fixture digest so the independent input/provenance reader is tested.
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);zipfile=base/"fixture.zip";zipfile.write_bytes(b"opaque-test-only")
            wiffile=base/"wif.json";wiffile.write_text(json.dumps(WIF))
            evidence={"workerPublication":{"status":"private-ingest-image-published-and-verified","imageUri":IMAGE,"registryDigest":IMAGE.rsplit("@",1)[1],
                    "remoteManifestAndConfigBytesMatch":True,"rawManifestConfigAndLayerBytesVerified":True,
                    "sourceTransactionRevision":G.BASELINE_SOURCE,"physicalManagedResources":55,"stateSHA256":P.STATE_SHA,"stateSerial":P.STATE_SERIAL,
                    "runtimeActivated":False,"stateModified":False,"iamModified":False,"repositoryPolicyModified":False,"resourcesCreated":False,"stateSourceIAMUnchanged":True},
                "googleRun":{"configurationVerified":True,"url":G.RUN_URL,"readyRevision":"fixture-revision"},
                "repositoryPolicyAbsence":{"status":"repository-policy-absent","accountId":G.ACCOUNT,"region":G.REGION,
                    "repositoryName":G.FOCUS.REPOSITORY,"errorCode":"RepositoryPolicyNotFoundException"}}
            paths={key:base/(key+".json") for key in evidence}
            inputs=base/"inputs.json";head="1"*40
            original_sha=P.sha
            def fake_sha(path):
                if path==zipfile:return G.ZIP_SHA
                if path==wiffile:return G.WIF_SHA
                return original_sha(path)
            record={"recordType":"reviewed-paused-aws-wiring-inputs-v1","sourceBaselineRevision":G.BASELINE_SOURCE,
                "sourceRevision":head,"workerImageUri":IMAGE,"zipFilename":str(zipfile),"zipSHA256":G.ZIP_SHA,
                "wifPath":str(wiffile),"wifSHA256":G.WIF_SHA,"googleRunURL":G.RUN_URL}
            def write():
                for key,value in evidence.items():
                    paths[key].write_text(json.dumps(value));record[key+"EvidencePath"]=str(paths[key]);record[key+"EvidenceSHA256"]=original_sha(paths[key])
                inputs.write_text(json.dumps(record));return original_sha(inputs)
            def read_record():
                with mock.patch.multiple(P,BASE=base,INPUTS=inputs,INPUTS_SHA=write(),NEW_HEAD=head),mock.patch.object(P,"sha",side_effect=fake_sha):
                    return P.reviewed_inputs(G)
            self.assertEqual(read_record()[0]["workerImageUri"],IMAGE)
            cases=[("workerPublication","remoteManifestAndConfigBytesMatch",False),
                ("workerPublication","rawManifestConfigAndLayerBytesVerified",False),("workerPublication","registryDigest","sha256:"+"f"*64),
                ("workerPublication","stateSHA256","f"*64),("workerPublication","stateSerial",59),("workerPublication","iamModified",True),
                ("workerPublication","imageUri",IMAGE+"0"),("googleRun","configurationVerified",False),
                ("googleRun","url","https://example.com"),("googleRun","readyRevision",""),
                ("repositoryPolicyAbsence","errorCode","AccessDenied"),
                ("repositoryPolicyAbsence","repositoryName","unrelated"),("repositoryPolicyAbsence","accountId","360493183467")]
            for scope,key,value in cases:
                with self.subTest(scope=scope,key=key):
                    old=evidence[scope][key];evidence[scope][key]=value
                    with self.assertRaises(RuntimeError):read_record()
                    evidence[scope][key]=old
            digest=write();paths["workerPublication"].write_text("{}")
            with mock.patch.multiple(P,BASE=base,INPUTS=inputs,INPUTS_SHA=digest,NEW_HEAD=head),mock.patch.object(P,"sha",side_effect=fake_sha):
                with self.assertRaisesRegex(RuntimeError,"evidence SHA differs"):P.reviewed_inputs(G)


if __name__=="__main__":unittest.main()
