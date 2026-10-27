"""Pure offline review of the exact paused 55 -> 59 AWS wiring increment.

Physical values must be exported from the SHA-pinned local raw state with the
same frozen Terraform/provider, without refresh. No AWS/credential/SDK call or
apply occurs. Only the seven two-key environment edits and one log ARN addition
are allowed. Existing Lambda last_modified may be a pure unknown; all other
existing attributes stay exact. New security configuration must be known.
"""
import argparse
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re

SPEC=importlib.util.spec_from_file_location("paused_ecr_gate",Path(__file__).with_name("check_ecr_policy_plan.py"))
FOCUS=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(FOCUS)
BASE=FOCUS.BASE
MODULE,ACCOUNT,REGION,PREFIX=BASE.MODULE,BASE.ACCOUNT,BASE.REGION,BASE.PREFIX
BASELINE_SOURCE="29367645d62d47f16ac64659266dc3ba1540b89d"
ZIP_SHA="fafb94bf948312f1fef8998b5619567ad3c3471381a34e9e816cec87b034d9f6"
WIF_SHA="c8747dc930080ba76b9fede868e9a4fe0d3c165c779c6f7145913f9eb08b7815"
RUN_URL="https://ecoguard-inference-adlnb7yumq-uc.a.run.app"
INVOKER=BASE.WIF.INVOKER
ZIP_FUNCTIONS={MODULE+f'aws_lambda_function.zip["{name}"]' for name in BASE.FUNCTIONS}
ROLE_POLICY=MODULE+"aws_iam_role_policy.runtime[0]"
ENV_BINDINGS={"ECO_INFERENCE_URL":RUN_URL,"ECO_GOOGLE_INVOKER_EMAIL":INVOKER}
# These explicit output paths were reviewed against AWS provider 6.67.0's
# actual local schema. Optional security/default blocks are never wildcarded.
NEW_READONLY={
    FOCUS.LOG:{"arn","id"}, FOCUS.POLICY:{"id","registry_id"},
    FOCUS.INGEST:{"arn","id","invoke_arn","qualified_arn","qualified_invoke_arn","response_streaming_invoke_arn",
        "last_modified","source_code_size","version","signing_job_arn","signing_profile_version_arn"},
    FOCUS.MAPPING:{"arn","id","uuid","function_arn","last_modified","last_processing_result","state","state_transition_reason"},
}
# Provider 6.67.0 also marks these optional attributes/blocks unknown when the
# corresponding AWS feature does not apply. These are NOT a general computed
# allowlist: only the exact named log, immutable Image Lambda and disabled SQS
# mapping below may project them. Known nonempty alternatives are rejected.
NEW_APPLICABILITY_OUTPUTS={
    FOCUS.LOG:{"name_prefix"},
    FOCUS.INGEST:{"code_sha256","source_code_hash"},
    FOCUS.MAPPING:{"amazon_managed_kafka_event_source_config","self_managed_kafka_event_source_config",
        "maximum_record_age_in_seconds","maximum_retry_attempts","parallelization_factor"},
    FOCUS.POLICY:set(),
}
SQS_COMPUTED_DEFAULTS={"amazon_managed_kafka_event_source_config":[],"self_managed_kafka_event_source_config":[],
    "maximum_record_age_in_seconds":0,"maximum_retry_attempts":0,"parallelization_factor":0}
# Exact known null spellings observed in the new SQS plan, versus the refreshed
# existing SQS profile. Never apply these to another resource or unknown value.
SQS_UNSET_DEFAULTS={"bisect_batch_on_function_error":False,"kms_key_arn":"",
    "queues":[],"topics":[],"starting_position":"","starting_position_timestamp":"","tumbling_window_in_seconds":0}


def new_output_fields(address):return NEW_READONLY[address]|NEW_APPLICABILITY_OUTPUTS[address]


def require(ok,reason):
    if not ok:raise ValueError(reason)


def unknown_paths(value,prefix=()):
    if value is True:return [prefix]
    if isinstance(value,dict):return [p for k,v in value.items() for p in unknown_paths(v,prefix+(k,))]
    if isinstance(value,list):return [p for k,v in enumerate(value) for p in unknown_paths(v,prefix+(k,))]
    return []


def strip_outputs(value,fields):return {k:copy.deepcopy(v) for k,v in value.items() if k not in fields}


def values(document):
    root=document.get("values",{}).get("root_module",{})
    return FOCUS.managed(root)


def raw_checkpoint(data,expected_sha,lineage,serial):
    """Pin raw bytes and physical identity; no provider-specific normalization."""
    require(re.fullmatch(r"[0-9a-f]{64}",expected_sha) and hashlib.sha256(data).hexdigest()==expected_sha,"Raw state SHA differs")
    raw=json.loads(data);require(raw.get("lineage")==lineage and isinstance(lineage,str) and lineage
            and type(serial) is int and raw.get("serial")==serial,"State lineage/serial differs")
    instances=[i for r in raw.get("resources",[]) if r.get("mode")=="managed" for i in r.get("instances",[])]
    require(len(instances)==55 and all(i.get("status") in (None,"ready") and not i.get("deposed") for i in instances),"Physical state is not fifty-five current untainted instances")
    return raw


def existing_zip_values(old,after,planned,unknown,address):
    require(set(unknown_paths(unknown)) <= {("last_modified",)},"Unreviewed existing ZIP unknown path: "+address)
    expected=copy.deepcopy(old)
    blocks=expected.get("environment",[])
    require(len(blocks)==1 and isinstance(blocks[0].get("variables"),dict),"Existing ZIP environment shape differs")
    variables=blocks[0]["variables"]
    require(all(variables.get(k)=="" for k in ENV_BINDINGS),"Physical ZIP did not start with empty inference bindings")
    require(variables.get("ECO_GOOGLE_CREDENTIALS_FILE")=="/var/task/config/google-wif.json","Physical public WIF path differs")
    variables.update(ENV_BINDINGS)
    if unknown.get("last_modified") is True:
        require(after.get("last_modified") is None and planned.get("last_modified") is None,"Unknown last_modified also contains a known value")
        expected.pop("last_modified",None)
        after=strip_outputs(after,{"last_modified"});planned=strip_outputs(planned,{"last_modified"})
    require(after==planned==expected,"Existing ZIP differs outside the two exact environment keys: "+address)


def new_known_values(address,change,planned,image):
    fields=new_output_fields(address);unknown=change.get("after_unknown",{})
    after=change["after"]
    if address==FOCUS.LOG:
        require(all(value.get("name")=="/aws/lambda/"+PREFIX+"-ingest" for value in (after,planned)),"Optional log prefix projection requires the exact explicit log name")
        require(all(value.get("name_prefix") in (None,"") for value in (after,planned)),"Named log includes a generated name prefix")
    elif address==FOCUS.INGEST:
        require(FOCUS.IMAGE_PATTERN.fullmatch(image) and all(value.get("package_type")=="Image" and value.get("image_uri")==image
            and value.get("function_name")==PREFIX+"-ingest" and all(value.get(key) in (None,"") for key in ("filename","handler","runtime","code_sha256","source_code_hash")) for value in (after,planned)),
            "Image hash projection requires the exact digest image and no ZIP configuration")
    elif address==FOCUS.MAPPING:
        queue=f"arn:aws:sqs:{REGION}:{ACCOUNT}:{PREFIX}-ingest"
        require(all(value.get("event_source_arn")==queue and value.get("function_name")==FOCUS.INGEST_ARN
            and value.get("enabled") is False and value.get("batch_size")==1 and value.get("scaling_config")==[]
            for value in (after,planned)),"Inapplicable stream/Kafka outputs require the exact disabled SQS target")
        for field,default in SQS_COMPUTED_DEFAULTS.items():
            if unknown.get(field) is True:continue
            require(all(field in value and type(value[field]) is type(default) and value[field]==default for value in (after,planned)),
                "Known SQS stream/Kafka output differs from the existing inactive default: "+field)
    for path in unknown_paths(unknown):
        require(len(path)==1 and path[0] in fields and unknown.get(path[0]) is True,
                "New resource has unreviewed/security unknown path: "+address+" "+str(path))
        require(change["after"].get(path[0]) is None and planned.get(path[0]) is None,"Unknown output also contains known value")
    require(strip_outputs(after,fields)==strip_outputs(planned,fields),"New planned/change configured values differ")
    for field in fields:
        if field in unknown and unknown[field] is True:continue
        require(after.get(field)==planned.get(field),"Known new output differs")
    return strip_outputs(planned,fields)


def match_new_empty_tags(template,value,address):
    """Only these three creations may spell the existing empty tags as null."""
    require(address in {FOCUS.LOG,FOCUS.INGEST,FOCUS.MAPPING},"Empty-tag representation is not reviewed for this resource")
    require("tags" in template and type(template["tags"]) is dict and template["tags"]=={},
            "Physical template tags must be a present typed empty map")
    require("tags" in value and (value["tags"] is None or type(value["tags"]) is dict and value["tags"]=={}),
            "New known tags must be present null or a typed empty map")
    # Preserve the actual new representation in the template. New change.after
    # must still equal planned values; no old55 or tags_all values are projected.
    template["tags"]=copy.deepcopy(value["tags"])


def known_arn(value,key,expected):
    require(value.get(key) in (None,expected),"New output identity differs: "+key)


def inspect_plan(document,physical,*,image,zip_sha,zip_filename,run_url,wif,root_inventory_while_paused=False):
    require(type(root_inventory_while_paused) is bool,"Root inventory review opt-in must be an explicit boolean")
    require(zip_sha==ZIP_SHA and isinstance(zip_filename,str) and zip_filename.startswith("/") and zip_filename.endswith(".zip"),"Reviewed ZIP SHA/absolute filename differs")
    require(run_url==RUN_URL,"Run origin differs from the explicitly verified private service")
    BASE.WIF.validate_personal_wif(wif)
    canonical_wif=BASE.WIF.parse_personal_wif(json.dumps(wif))
    require(canonical_wif==wif,"Public WIF configuration differs")
    prior=FOCUS.managed(document["prior_state"]["values"]["root_module"])
    physical_values=values(physical)
    require(len(physical_values)==55 and set(physical_values)==BASE.expected_addresses() and prior==physical_values,
            "Refreshed prior differs from the full physical55 checkpoint; no refresh bypass permitted")
    focused=FOCUS.inspect_plan(document,image,root_inventory_while_paused=root_inventory_while_paused)
    planned=FOCUS.managed(document["planned_values"]["root_module"])
    rows={r["address"]:r for r in document["resource_changes"] if r.get("mode")=="managed"}
    code_hash=base64.b64encode(bytes.fromhex(ZIP_SHA)).decode("ascii")
    for address,old in physical_values.items():
        change=rows[address]["change"];after=change["after"];future=planned[address]
        if address in ZIP_FUNCTIONS:
            require(old.get("filename")==zip_filename and old.get("source_code_hash")==code_hash,"Physical ZIP path/hash differs")
            require(old.get("reserved_concurrent_executions")==0 and old.get("role")==BASE.EXECUTION_ROLE,"Physical function was not paused/on exact role")
            existing_zip_values(old,after,future,change.get("after_unknown",{}),address)
        elif address==ROLE_POLICY:
            require(not unknown_paths(change.get("after_unknown",{})),"Runtime IAM policy is unknown")
            require(strip_outputs(after,{"policy"})==strip_outputs(future,{"policy"})==strip_outputs(old,{"policy"}),"Runtime policy ownership/metadata changed")
            expected=json.loads(old["policy"]);actual=json.loads(future["policy"])
            target=[s for s in expected["Statement"] if s.get("Sid")=="ProjectFunctionLogs"]
            require(len(target)==1,"Physical log SID missing/duplicated")
            arn=f"arn:aws:logs:{REGION}:{ACCOUNT}:log-group:/aws/lambda/{PREFIX}-ingest:log-stream:*"
            require(arn not in target[0]["Resource"],"Physical role already contains ingest log ARN")
            target[0]["Resource"]=sorted(target[0]["Resource"]+[arn])
            for statement in actual.get("Statement",[]):
                if statement.get("Sid")=="ProjectFunctionLogs":statement["Resource"]=sorted(statement["Resource"])
            require(actual==expected and json.loads(after["policy"])==json.loads(future["policy"]),"IAM edges changed beyond one ingest log ARN")
        else:
            require(not unknown_paths(change.get("after_unknown",{})) and old==after==future,"Existing no-op full values differ")
    new={a:new_known_values(a,rows[a]["change"],planned[a],image) for a in FOCUS.ADDITIONS}
    # The new log group uses the same known safe profile as the deployed API log.
    old_log=physical_values[MODULE+'aws_cloudwatch_log_group.functions["api"]']
    require(old_log.get("name_prefix") in (None,""),"Physical named log has a generated prefix")
    log_template=strip_outputs(old_log,new_output_fields(FOCUS.LOG))
    require(log_template.get("retention_in_days")==7 and not log_template.get("kms_key_id")
            and log_template.get("deletion_protection_enabled") is False and log_template.get("skip_destroy") is False
            and log_template.get("log_group_class")=="STANDARD","Physical log profile is not the reviewed safe default")
    require(log_template.get("kms_key_id") in (None,"") and new[FOCUS.LOG].get("kms_key_id") in (None,""),"Log must have no KMS override")
    log_template["kms_key_id"]=new[FOCUS.LOG].get("kms_key_id")
    match_new_empty_tags(log_template,new[FOCUS.LOG],FOCUS.LOG)
    log_template["name"]="/aws/lambda/"+PREFIX+"-ingest"
    require(new[FOCUS.LOG]==log_template,"New log profile differs beyond its exact name")
    known_arn(planned[FOCUS.LOG],"arn",f"arn:aws:logs:{REGION}:{ACCOUNT}:log-group:/aws/lambda/{PREFIX}-ingest")
    known_arn(planned[FOCUS.LOG],"id","/aws/lambda/"+PREFIX+"-ingest")
    require(set(new[FOCUS.POLICY]) <= {"policy","repository","region"} and new[FOCUS.POLICY].get("repository")==FOCUS.REPOSITORY
            and new[FOCUS.POLICY].get("region",REGION)==REGION and FOCUS.policy_exact(new[FOCUS.POLICY]["policy"]),"New ECR policy has extra configuration")
    known_arn(planned[FOCUS.POLICY],"id",FOCUS.REPOSITORY);known_arn(planned[FOCUS.POLICY],"registry_id",ACCOUNT)
    # Every remaining Image setting mirrors the physical API Lambda default.
    image_template=strip_outputs(physical_values[MODULE+'aws_lambda_function.zip["api"]'],new_output_fields(FOCUS.INGEST))
    image_value=new[FOCUS.INGEST]
    match_new_empty_tags(image_template,image_value,FOCUS.INGEST)
    for field in ("filename","handler","runtime"):
        require(image_value.get(field) in (None,""),"Image Lambda includes ZIP/code-hash configuration")
        if field in image_value:image_template[field]=image_value[field]
        else:image_template.pop(field,None)
    for field in ("description","kms_key_arn","source_kms_key_arn","code_signing_config_arn"):
        require(image_template.get(field)=="" and image_value.get(field) in (None,""),"Image optional empty setting differs: "+field)
        if field in image_value:image_template[field]=image_value[field]
        else:image_template.pop(field,None)
    require(image_template.get("layers")==[] and image_value.get("layers") in (None,[]),"Image Lambda must have no layers")
    image_template["layers"]=image_value.get("layers")
    image_template.update(function_name=PREFIX+"-ingest",package_type="Image",image_uri=image,
        timeout=120,memory_size=2048,ephemeral_storage=[{"size":1024}],environment=copy.deepcopy(planned[MODULE+'aws_lambda_function.zip["api"]']["environment"]))
    config=image_value.get("image_config",[])
    require(len(config)==1 and config[0].get("command")==["ecoguard_aws.handlers.ingest"]
            and not config[0].get("entry_point") and not config[0].get("working_directory"),"Image runtime command/entrypoint/workdir differs")
    image_template["image_config"]=copy.deepcopy(config)
    logging=image_template.get("logging_config",[])
    require(len(logging)==1 and logging[0].get("log_format")=="Text","Physical Lambda logging profile differs")
    logging[0]["log_group"]="/aws/lambda/"+PREFIX+"-ingest"
    actual_logging=image_value.get("logging_config",[])
    require(len(actual_logging)==1,"Image logging must be known and explicit")
    for field in ("application_log_level","system_log_level"):
        require(logging[0].get(field)=="" and actual_logging[0].get(field) in (None,""),"Text logging has an unreviewed log level")
        if field in actual_logging[0]:logging[0][field]=actual_logging[0][field]
        else:logging[0].pop(field,None)
    require(image_template.get("tracing_config")==[{"mode":"PassThrough"}] and image_template.get("publish") is False
            and not image_template.get("kms_key_arn") and not image_template.get("source_kms_key_arn")
            and not any(image_template.get(k) for k in ("layers","vpc_config","file_system_config","dead_letter_config","snap_start","capacity_provider_config","durable_config","tenancy_config","code_signing_config_arn")),"Physical Lambda security/default profile differs")
    require(image_value==image_template,"Image Lambda differs outside the exact new-function profile")
    known_arn(planned[FOCUS.INGEST],"arn",FOCUS.INGEST_ARN);known_arn(planned[FOCUS.INGEST],"id",PREFIX+"-ingest")
    # Copy the existing disabled inference SQS profile; only its two targets vary.
    old_mapping=physical_values[MODULE+'aws_lambda_event_source_mapping.zip_queues["infer"]']
    require(all(field in old_mapping and type(old_mapping[field]) is type(default) and old_mapping[field]==default
            for field,default in SQS_COMPUTED_DEFAULTS.items()),"Physical SQS stream/Kafka profile differs from reviewed inactive defaults")
    mapping_template=strip_outputs(old_mapping,new_output_fields(FOCUS.MAPPING))
    mapping_value=new[FOCUS.MAPPING]
    match_new_empty_tags(mapping_template,mapping_value,FOCUS.MAPPING)
    for field,default in SQS_UNSET_DEFAULTS.items():
        require(field in mapping_template and type(mapping_template[field]) is type(default) and mapping_template[field]==default
                and (mapping_value.get(field) is None or type(mapping_value[field]) is type(default) and mapping_value[field]==default),
                "New SQS unset spelling differs from the exact existing inactive default: "+field)
        if field in mapping_value:mapping_template[field]=mapping_value[field]
        else:mapping_template.pop(field,None)
    mapping_template["function_name"]=FOCUS.INGEST_ARN
    queue_arn=physical_values[MODULE+'aws_sqs_queue.work["ingest"]'].get("arn")
    require(queue_arn==f"arn:aws:sqs:{REGION}:{ACCOUNT}:{PREFIX}-ingest","Physical ingest queue ARN differs")
    mapping_template["event_source_arn"]=queue_arn
    require(mapping_template.get("enabled") is False and mapping_template.get("batch_size")==1
            and mapping_template.get("function_response_types")==["ReportBatchItemFailures"]
            and not any(mapping_template.get(k) for k in ("scaling_config","filter_criteria","destination_config","kms_key_arn","provisioned_poller_config","metrics_config","self_managed_event_source","source_access_configuration","amazon_managed_kafka_event_source_config","self_managed_kafka_event_source_config","document_db_event_source_config","topics","queues","starting_position","starting_position_timestamp","tumbling_window_in_seconds")),"Physical SQS profile has unreviewed non-SQS/active settings")
    require(mapping_value==mapping_template,"New disabled mapping differs outside its exact queue/function targets")
    known_arn(planned[FOCUS.MAPPING],"function_arn",FOCUS.INGEST_ARN)
    require(planned[FOCUS.MAPPING].get("state") in (None,"Disabled"),"New mapping output is not disabled")
    variables=document.get("variables",{})
    require(all(variables.get(key,{}).get("value")==value for key,value in {
        "deployment_stage":"wiring-paused","worker_image":image,"inference_url":RUN_URL,"lambda_zip":zip_filename}.items()),"Explicit stage/image/URL/ZIP inputs differ")
    call=document.get("configuration",{}).get("root_module",{}).get("module_calls",{}).get("ecoguard",{})
    require(call.get("source")=="../.." and not any(k in call for k in ("count_expression","for_each_expression","depends_on")),"Legacy-provider module scope differs")
    return {**focused,"status":"offline-paused-wiring-increment-passed","fullIncrementGatePassed":True,
        "baselineSourceRevision":BASELINE_SOURCE,"zipSHA256":ZIP_SHA,"workerImageUri":image,"inferenceURL":RUN_URL,
        "existingFullValuesCompared":55,"exactEnvironmentUpdates":7,"extraRuntimeIAMLogARNs":1,
        "newResourceReviewedComputedUnknownPaths":{a:[list(path) for path in unknown_paths(rows[a]["change"].get("after_unknown",{}))] for a in sorted(FOCUS.ADDITIONS)},
        "newECRPolicyStatements":1,"physicalPriorFullyEqual":True,"resourceDriftEntries":0,
        "applyAuthorized":False,"cloudVerified":False,"imageProvenanceVerified":False,"googleRunProvenanceVerified":False,
        "remaining":"Actual SHA-bound physical/plan and live publication/Run/policy-absence evidence are required; an apply needs separate review."}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("physical-json","plan-json","wif"):parser.add_argument("--"+name,required=True,type=Path)
    for name in ("image","zip-sha256","zip-filename","run-url"):parser.add_argument("--"+name,required=True)
    parser.add_argument("--root-inventory-while-paused",action="store_true",help="Review only the explicitly configured, exact-root listing exception")
    args=parser.parse_args()
    try:report=inspect_plan(json.loads(args.plan_json.read_text()),json.loads(args.physical_json.read_text()),image=args.image,
        zip_sha=args.zip_sha256,zip_filename=args.zip_filename,run_url=args.run_url,wif=BASE.WIF.parse_personal_wif(args.wif.read_bytes()),
        root_inventory_while_paused=args.root_inventory_while_paused)
    except (OSError,ValueError,KeyError,TypeError) as error:
        print(json.dumps({"status":"blocked","applyAuthorized":False,"reason":str(error)}));return 1
    print(json.dumps(report,indent=2));return 0


if __name__=="__main__":raise SystemExit(main())
