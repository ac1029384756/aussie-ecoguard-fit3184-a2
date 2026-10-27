"""Prepare exactly one refreshed paused AWS wiring plan; default is inert.

Run only after root has reviewed/frozen every PENDING evidence/tool/source pin,
restored the existing official Terraform/provider/local backend, and supplied
the actual published ECR/verified Run/policy-absence records. No apply, tool
download, init, AWS CLI, application invocation, state refresh-write, generic
refresh=false, approval reuse or retry exists in this helper.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode=True
BASE=Path.home()/"ecoguard-c-personal-20261023"
SOURCE=BASE/"source";ROOT=SOURCE/"infra/aws/environments/personal";STATE=ROOT/"state/terraform.tfstate"
RESULT=ROOT/"private/staged-wiring-plan-20261024-1"
TF=Path("/tmp/ecoguard-c-personal-20261023/tools/terraform")
DATA=Path("/tmp/ecoguard-aws-tool-restore-20261024-1/terraform-data")
INPUTS=BASE/"aws-wiring-inputs-20261024-1.json"
INPUTS_SHA="PENDING_ROOT_REVIEWED_INPUTS_SHA"
NEW_HEAD="PENDING_CONTROLLED_SOURCE_TRANSITION_HEAD"
TF_SHA="664b66cc0bcd7ed28fd27569719ccaa8a40c230b8be45060ce4d65e2852e1bcc"
PROVIDER_SHA="PENDING_ACTUAL_RESTORED_LINUX_PROVIDER_BINARY_SHA"
STATE_SHA="644e48c482187a7f782f65750059c8e84f084c68e5c400567c67c79fe4d4a26d"
STATE_SERIAL=60
STATE_LINEAGE="PENDING_ROOT_READ_PHYSICAL_LINEAGE"
LOCK_SHA="d0b2d276d73e5f5a0ab88528b096de21da5202a4cc29c4338422ccba56751c97"
ENV={**os.environ,"TF_DATA_DIR":str(DATA),"CHECKPOINT_DISABLE":"1","TF_IN_AUTOMATION":"1",
     "AWS_PAGER":"","AWS_CLI_AUTO_PROMPT":"off","PYTHONDONTWRITEBYTECODE":"1"}


def require(ok,reason):
    if not ok:raise RuntimeError(reason)
def now():return datetime.now(timezone.utc).isoformat()
def sha(path):
    value=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024**2),b""):value.update(block)
    return value.hexdigest()
def read(argv,timeout=90):
    result=subprocess.run([str(v) for v in argv],env=ENV,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=timeout,shell=False)
    require(result.returncode==0,"Read-only preparation command failed");return result.stdout.strip()
def local(path):return json.loads(path.read_text())
def scoped_path(value):
    require(isinstance(value,str),"Evidence path is not text");path=Path(value)
    require(path.is_absolute() and path.resolve().is_relative_to(BASE.resolve()) and path.is_file() and not path.is_symlink(),"Evidence path escaped the task/missing/symlinked")
    return path
def save(name,value):
    with (RESULT/name).open("x") as output:json.dump(value,output,indent=2);output.write("\n")


def reviewed_inputs(gate):
    require(INPUTS.is_file() and not INPUTS.is_symlink() and sha(INPUTS)==INPUTS_SHA,"Reviewed input record differs")
    value=local(INPUTS)
    keys={"recordType","sourceBaselineRevision","sourceRevision","workerImageUri","zipFilename","zipSHA256","wifPath","wifSHA256",
        "googleRunURL","workerPublicationEvidencePath","workerPublicationEvidenceSHA256","googleRunEvidencePath","googleRunEvidenceSHA256",
        "repositoryPolicyAbsenceEvidencePath","repositoryPolicyAbsenceEvidenceSHA256"}
    require(set(value)==keys and value["recordType"]=="reviewed-paused-aws-wiring-inputs-v1"
            and value["sourceBaselineRevision"]==gate.BASELINE_SOURCE and value["sourceRevision"]==NEW_HEAD
            and gate.FOCUS.IMAGE_PATTERN.fullmatch(value["workerImageUri"]) and value["zipSHA256"]==gate.ZIP_SHA
            and value["wifSHA256"]==gate.WIF_SHA and value["googleRunURL"]==gate.RUN_URL,"Reviewed input scope differs")
    paths={"zip":scoped_path(value["zipFilename"]),"wif":scoped_path(value["wifPath"])}
    require(paths["zip"].suffix==".zip" and sha(paths["zip"])==gate.ZIP_SHA and sha(paths["wif"])==gate.WIF_SHA,"Real ZIP/public WIF SHA differs")
    wif=gate.BASE.WIF.parse_personal_wif(paths["wif"].read_bytes())
    for key in ("workerPublication","googleRun","repositoryPolicyAbsence"):
        paths[key]=scoped_path(value[key+"EvidencePath"])
        require(re.fullmatch(r"[0-9a-f]{64}",value[key+"EvidenceSHA256"]) and sha(paths[key])==value[key+"EvidenceSHA256"],"Verified external evidence SHA differs")
    publication=local(paths["workerPublication"])
    require(publication.get("status")=="private-ingest-image-published-and-verified" and publication.get("imageUri")==value["workerImageUri"]
            and publication.get("registryDigest")==value["workerImageUri"].rsplit("@",1)[1]
            and publication.get("remoteManifestAndConfigBytesMatch") is True and publication.get("rawManifestConfigAndLayerBytesVerified") is True
            and publication.get("sourceTransactionRevision")==gate.BASELINE_SOURCE and publication.get("physicalManagedResources")==55
            and publication.get("stateSHA256")==STATE_SHA and publication.get("stateSerial")==STATE_SERIAL
            and publication.get("stateSourceIAMUnchanged") is True
            and all(publication.get(k) is False for k in ("runtimeActivated","stateModified","iamModified","repositoryPolicyModified","resourcesCreated")),
            "Exact ECR image publication or unchanged paused checkpoint is not verified")
    run=local(paths["googleRun"])
    require(run.get("configurationVerified") is True and run.get("url")==gate.RUN_URL
            and isinstance(run.get("readyRevision"),str) and run["readyRevision"],"Private Run URL/revision is not verified")
    absence=local(paths["repositoryPolicyAbsence"])
    require(absence.get("status")=="repository-policy-absent" and absence.get("accountId")==gate.ACCOUNT
            and absence.get("region")==gate.REGION and absence.get("repositoryName")==gate.FOCUS.REPOSITORY
            and absence.get("errorCode")=="RepositoryPolicyNotFoundException","Existing ECR policy absence is not established; do not overwrite an untracked policy")
    return value,paths,wif


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--prepare",action="store_true");args=parser.parse_args()
    if not args.prepare:
        print(json.dumps({"status":"dry-run","cloudInvoked":False,"planExecuted":False,"applyExecuted":False,
            "expectedPhysicalResources":55,"expectedPlannedResources":59,"creates":4,"updates":8,"noops":47,
            "requiresActualStateToolSourceAndEvidencePins":True,"refresh":True,"applicationInvoked":False}));return 0
    require(sys.platform=="linux","Existing Linux AWS CloudShell workspace required")
    require(re.fullmatch(r"[0-9a-f]{40}",NEW_HEAD) and all(re.fullmatch(r"[0-9a-f]{64}",v) for v in (INPUTS_SHA,TF_SHA,PROVIDER_SHA))
            and STATE_LINEAGE and not STATE_LINEAGE.startswith("PENDING"),"Final source/tool/lineage/input pins are missing")
    require(not RESULT.exists() and not RESULT.is_symlink(),"Plan attempt exists; no retry/overwrite")
    for key,value in os.environ.items():
        require(not(value and (key.startswith(("TF_CLI_ARGS","TF_VAR_")) or key in ("TF_WORKSPACE","TF_LOG","TF_LOG_PATH","TF_CLI_CONFIG_FILE","TF_REATTACH_PROVIDERS","TF_PLUGIN_CACHE_DIR"))),"Unreviewed Terraform override")
        require(not(value and (key in {"AWS_PROFILE","AWS_DEFAULT_PROFILE","AWS_CONFIG_FILE","AWS_SHARED_CREDENTIALS_FILE",
            "AWS_ROLE_ARN","AWS_WEB_IDENTITY_TOKEN_FILE","AWS_CA_BUNDLE","CURL_CA_BUNDLE","REQUESTS_CA_BUNDLE",
            "SSL_CERT_FILE","SSL_CERT_DIR","HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","http_proxy","https_proxy","all_proxy"}
            or key.startswith("AWS_ENDPOINT_URL"))),"Unreviewed AWS identity/endpoint/TLS/proxy selector")
    require(not (Path.home()/".terraformrc").exists(),"Unexpected Terraform CLI configuration")
    require(TF.is_file() and not TF.is_symlink() and sha(TF)==TF_SHA and (DATA/"terraform.tfstate").is_file(),"Restore the verified official tool/provider/local backend first; helper does not download/init")
    providers=list((DATA/"providers/registry.terraform.io/hashicorp/aws/6.67.0/linux_amd64").glob("terraform-provider-aws_v6.67.0*"))
    require(len(providers)==1 and providers[0].is_file() and not providers[0].is_symlink() and sha(providers[0])==PROVIDER_SHA,"Actual restored Linux AWS provider binary differs")
    def source_exact():return read(["git","-C",SOURCE,"rev-parse","HEAD"])==NEW_HEAD and not read(["git","-C",SOURCE,"status","--porcelain","--untracked-files=all"])
    require(source_exact(),"Controlled new source transition differs/is dirty")
    require(not any(list(ROOT.glob(pattern)) for pattern in ("*.auto.tfvars","*.auto.tfvars.json","terraform.tfvars","terraform.tfvars.json")),"Unexpected root input file")
    require(sha(ROOT/".terraform.lock.hcl")==LOCK_SHA,"Original AWS provider lock changed")
    version=json.loads(read([TF,"-chdir="+str(ROOT),"version","-json"]))
    backend=local(DATA/"terraform.tfstate")["backend"]
    require(version.get("terraform_version")=="1.17.0" and version.get("provider_selections")=={"registry.terraform.io/hashicorp/aws":"6.67.0"}
            and backend.get("type")=="local" and backend["config"]["path"]=="state/terraform.tfstate"
            and read([TF,"-chdir="+str(ROOT),"workspace","show"])=="default","Tool/provider/backend/workspace differs")
    gate_path=ROOT/"check_staged_increment_plan.py"
    spec=importlib.util.spec_from_file_location("actual_paused_wiring_gate",gate_path);gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
    original=STATE.read_bytes();gate.raw_checkpoint(original,STATE_SHA,STATE_LINEAGE,STATE_SERIAL)
    inputs,paths,wif=reviewed_inputs(gate)
    physical=json.loads(read([TF,"-chdir="+str(ROOT),"show","-json",STATE]))
    require(set(gate.values(physical))==gate.BASE.expected_addresses(),"Physical local export is not exact fifty-five")
    frozen_files={INPUTS,TF,providers[0],ROOT/".terraform.lock.hcl",*paths.values()}
    hashes={path:sha(path) for path in frozen_files}
    def stable():
        require(source_exact() and STATE.read_bytes()==original and all(path.is_file() and not path.is_symlink() and sha(path)==digest for path,digest in hashes.items()),"Source/state/input evidence changed")
    stable();os.umask(0o077);RESULT.mkdir(mode=0o700)
    (RESULT/"physical55-before-private.tfstate").write_bytes(original)
    save("physical55-values-private.json",physical);save("reviewed-inputs-copy.json",inputs)
    save("input-evidence-sha256-private.json",{str(path):digest for path,digest in hashes.items()})
    save("preflight-private.json",{"baselineSourceRevision":gate.BASELINE_SOURCE,"sourceRevision":NEW_HEAD,"stateSHA256":STATE_SHA,
        "lineage":STATE_LINEAGE,"serial":STATE_SERIAL,"managedResources":55,"zipSHA256":gate.ZIP_SHA,"inputsSHA256":INPUTS_SHA,"observedAtUtc":now()})
    report={"status":"blocked","applyExecuted":False,"applyAuthorized":False,"applicationInvoked":False,"stateModified":False,"iamModified":False,"automaticRetry":False}
    try:
        validation=json.loads(read([TF,"-chdir="+str(ROOT),"validate","-json"]));save("validate.json",validation)
        require(validation.get("valid") is True and validation.get("error_count")==0 and validation.get("warning_count")==0,"Validation failed/warned")
        binary=RESULT/"paused-wiring.tfplan"
        save("plan-started.json",{"startedAtUtc":now(),"refresh":True,"refreshOnly":False,"targetUsed":False,"retryPermitted":False})
        with (RESULT/"plan-private.log").open("x") as log:
            result=subprocess.run([str(TF),"-chdir="+str(ROOT),"plan","-input=false","-no-color","-refresh=true","-lock-timeout=60s",
                "-var=deployment_stage=wiring-paused","-var=lambda_zip="+inputs["zipFilename"],"-var=worker_image="+inputs["workerImageUri"],
                "-var=inference_url="+inputs["googleRunURL"],"-out="+str(binary)],env=ENV,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=600,shell=False)
        require(result.returncode==0,"Read-only plan failed; inspect private log. S3 HEAD 403/refresh failures stay blocked; no retry/bypass")
        stable();document=json.loads(read([TF,"-chdir="+str(ROOT),"show","-json",binary]));save("paused-wiring-plan-private.json",document)
        save("unknown-paths-private.json",[{"address":r["address"],"path":list(path)} for r in document.get("resource_changes",[])
            if r.get("mode")=="managed" for path in gate.unknown_paths(r.get("change",{}).get("after_unknown",{}))])
        reviewed=gate.inspect_plan(document,physical,image=inputs["workerImageUri"],zip_sha=gate.ZIP_SHA,
            zip_filename=inputs["zipFilename"],run_url=inputs["googleRunURL"],wif=wif)
        require("Warning:" not in (RESULT/"plan-private.log").read_text(),"Plan emitted warning")
        report.update(reviewed,status="paused-aws-wiring-saved-plan-review-passed",sourceRevision=NEW_HEAD,stateSHA256=STATE_SHA,
            lineage=STATE_LINEAGE,serial=STATE_SERIAL,savedPlanSHA256=sha(binary),inputsSHA256=INPUTS_SHA,
            workerPublicationEvidenceSHA256=inputs["workerPublicationEvidenceSHA256"],googleRunEvidenceSHA256=inputs["googleRunEvidenceSHA256"],
            repositoryPolicyAbsenceEvidenceSHA256=inputs["repositoryPolicyAbsenceEvidenceSHA256"],wifSHA256=gate.WIF_SHA,
            inputProvenanceHashBound=True,refresh=True,refreshOnly=False,targetUsed=False)
    except Exception as error:
        report.update(status="blocked",errorType=type(error).__name__,error=str(error) if isinstance(error,(RuntimeError,ValueError)) else "Inspect private preparation evidence; no retry")
    finally:
        (RESULT/"physical55-after-private.tfstate").write_bytes(STATE.read_bytes())
        try:stable();report["stateSourceAndEvidenceUnchanged"]=True
        except Exception as error:report.update(status="blocked",stateSourceAndEvidenceUnchanged=False,postVerificationErrorType=type(error).__name__)
        report["observedAtUtc"]=now();save("review-summary.json",report);print(json.dumps(report,separators=(",",":")),flush=True)
    return 0 if report["status"]=="paused-aws-wiring-saved-plan-review-passed" else 1


if __name__=="__main__":
    try:raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"status":"blocked","applyExecuted":False,"errorType":type(error).__name__,
            "error":str(error) if isinstance(error,(RuntimeError,ValueError)) else "Invalid/incomplete paused wiring prerequisites"}),flush=True)
        raise SystemExit(1)
