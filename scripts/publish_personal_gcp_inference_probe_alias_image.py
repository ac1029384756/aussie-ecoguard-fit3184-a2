"""Inert by default; one AR-only push of the reviewed probe-alias image.

Uses the existing official crane and gcloud credential helper. The new tag is
unique; old tags/digests, exact thirteen-resource physical state, full IAM and
identities remain unchanged. No old deployment/publication approval is reused.
Funding is a fresh read-only UI observation; standing member-C authorization
is recorded honestly. No Run mutation/application HTTP, Terraform, IAM/API or
state write, credential export, explicit push retry or tool download exists.
Crane's underlying bounded transport retries are distinct from the one push.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tarfile
from zoneinfo import ZoneInfo

sys.dont_write_bytecode=True
BASE=Path.home()/"ecoguard-c-personal-20261023"
SOURCE=BASE/"source"; ROOT=SOURCE/"infra/gcp/environments/personal"; STATE=ROOT/"state/terraform.tfstate"
RESULT=BASE/"image-publication-20261024-4"
HEAD="9b16f12872c067163f41de5c3d29d01e78cebbdd"
STATE_SHA="f3b6113be12f34b05701da2e095d0df5763a97d8efdcd6a38a7fdbfc0d1d8fad"
PROJECT,NUMBER,REGION="ecoguard-fit3184-a2-2026","995070689587","us-central1"
HOST="us-central1-docker.pkg.dev"; IMAGE=HOST+"/"+PROJECT+"/ecoguard/inference"
TARGET=IMAGE+":c-20261024-2"; OLD_TAG="c-20261024-1"; NEW_TAG="c-20261024-2"
OLD_DIGEST="sha256:7e481399309c8a90276c864e9765545657e44c00e9061ee668b4e56db4f22fdb"
MANIFEST="sha256:0e274acc0dff67b2f233ebd5914235ea328147b8505044de23cfc135217e5c91"
CONFIG="sha256:dea2da475fc169ca21a1fb637e54f61f29d97b48d0604f49cf5c9735c0af0287"
IMAGE_BYTES=375657296  # docker inspect image Size; never the gzip size.
ARCHIVE=BASE/"inference-amd64-20261024-2.tar.gz"
ARCHIVE_BYTES=373263746; ARCHIVE_SHA="2f7f395e7e2eb07610270ae730803cbc7e076271bba3f232a45b873ce996ec35"
EXPORT=BASE/"inference-amd64-20261024-2.json"; EXPORT_SHA="c486eb38e5a95967a1026bac0909ad3155c20cfb32d45cc9e4a5c2a0b72d32d4"
CRANE=BASE/"image-publication-20261024-3/crane"
CRANE_SHA="8e75c326adb43b053cfd78b9b987663f8f4fe4557f4d3915905643f25c730992"
CLIENT=BASE/"image-publication-20261024-1/docker-client"
FROZEN_HTTP=BASE/"frozen-verify-private-http-20261024-2.py"
FROZEN_HTTP_SHA="fb9d9d791b872a13e77c09cc65cc320976ffd363b67a0ee0e13a43c41923eb50"
FUNDING=BASE/"gcp-funding-private-20261024-3.json"
FUNDING_SHA="014dc3b37c764aff0e5ee69e2e36d1f02aa77f5dbe21799b3dda411f268f0d6e"
FUNDING_TIME="2026-10-23T23:44:47.410035+00:00"
STANDING="user requested finish member C and default agree within existing credits; no IAM/capacity change"
ENV={**os.environ,"CLOUDSDK_CORE_DISABLE_PROMPTS":"1","CLOUDSDK_CORE_LOG_HTTP":"false",
     "PYTHONDONTWRITEBYTECODE":"1","DOCKER_CONFIG":str(CLIENT),"NO_COLOR":"1"}


def require(ok,reason):
    if not ok: raise RuntimeError(reason)


def now(): return datetime.now(timezone.utc).isoformat()
def sha(path):
    value=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024**2),b""): value.update(block)
    return value.hexdigest()
def local(path): return json.loads(path.read_text())
def exact(record,expected): return all(type(record.get(k)) is type(v) and record[k]==v for k,v in expected.items())
def load(name,path,expected):
    require(path.is_file() and not path.is_symlink() and sha(path)==expected,"Frozen helper differs")
    spec=importlib.util.spec_from_file_location(name,path); module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def read(argv,timeout=90):
    result=subprocess.run([str(v) for v in argv],env=ENV,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=timeout,shell=False)
    require(result.returncode==0,"Read-only prerequisite/metadata command failed");return result.stdout.strip()
def save(name,value):
    with (RESULT/name).open("x") as output:json.dump(value,output,indent=2);output.write("\n")


def funding(current=None):
    require(FUNDING.is_file() and not FUNDING.is_symlink() and sha(FUNDING)==FUNDING_SHA,"Fresh funding evidence differs")
    value=local(FUNDING)
    expected={"project":PROJECT,"billingAccountMatched":True,"eligibleExistingCreditsPositive":True,
        "currencyVerified":False,"expiresDate":"2026-10-28","additionalOutOfPocketLimitAUD":0,
        "standingAuthorization":STANDING,"source":"official Google Cloud Credits UI"}
    require(set(value)==set(expected)|{"observedAtUtc"} and exact(value,expected),"Funding schema/scope differs")
    stamp=datetime.fromisoformat(value["observedAtUtc"].replace("Z","+00:00")); current=current or datetime.now(timezone.utc)
    require(stamp==datetime.fromisoformat(FUNDING_TIME) and stamp.tzinfo is not None
            and 0 <= (current-stamp).total_seconds() <= 3600,"Funding observation future/expired/different")
    require(current.astimezone(ZoneInfo("Australia/Melbourne")).date().isoformat()<value["expiresDate"],"Recorded credits expired")
    return value


def extract_archive(archive,layout):
    """Bounded local OCI extraction; checks every compressed blob before push."""
    require(type(ARCHIVE_BYTES) is int and 0<ARCHIVE_BYTES<512*1024**2 and archive.is_file()
            and not archive.is_symlink() and archive.stat().st_size==ARCHIVE_BYTES and sha(archive)==ARCHIVE_SHA,"New archive size/hash differs")
    require(not layout.exists() and not layout.is_symlink(),"OCI layout already exists")
    layout.mkdir(mode=0o700); seen=set(); total=0
    with tarfile.open(archive,"r|gz") as package:
        for entry in package:
            path=PurePosixPath(entry.name);name=str(path)
            require(not path.is_absolute() and ".." not in path.parts and "\\" not in entry.name,"Unsafe archive path")
            if entry.isdir():
                require(name in (".","blobs","blobs/sha256"),"Unexpected archive directory");continue
            require(entry.isfile() and name not in seen and (name in {"index.json","oci-layout","manifest.json"}
                    or re.fullmatch(r"blobs/sha256/[0-9a-f]{64}",name)),"Archive link/duplicate/unexpected entry")
            seen.add(name);require(0<entry.size<=512*1024**2,"Archive entry size outside bound")
            if name in {"index.json","oci-layout","manifest.json"}:require(entry.size<1024**2,"Oversized metadata")
            total+=entry.size;require(total<512*1024**2,"OCI extraction exceeds bound")
            out=layout/name;out.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            count=0;digest=hashlib.sha256()
            with out.open("xb") as target:
                source=package.extractfile(entry)
                for block in iter(lambda:source.read(1024**2),b""):
                    count+=len(block);require(count<=entry.size,"Entry exceeds declared size");digest.update(block);target.write(block)
            require(count==entry.size,"Truncated entry")
            if name.startswith("blobs/"):require(digest.hexdigest()==path.name,"Compressed OCI blob SHA mismatch")
    manifest_path=layout/"blobs/sha256"/MANIFEST[7:];config_path=layout/"blobs/sha256"/CONFIG[7:]
    require(manifest_path.stat().st_size<1024**2 and config_path.stat().st_size<1024**2,"OCI manifest/config too large")
    manifest,config=local(manifest_path),local(config_path);index=local(layout/"index.json");classic=local(layout/"manifest.json")
    layers=manifest.get("layers",[])
    require(local(layout/"oci-layout")=={"imageLayoutVersion":"1.0.0"} and index.get("schemaVersion")==2
            and len(index.get("manifests",[]))==1,"Single OCI layout/index required")
    descriptor=index["manifests"][0]
    require(descriptor.get("digest")==MANIFEST and descriptor.get("size")==manifest_path.stat().st_size
            and descriptor.get("mediaType")==manifest.get("mediaType")=="application/vnd.oci.image.manifest.v1+json"
            and manifest.get("schemaVersion")==2 and manifest.get("config",{}).get("digest")==CONFIG
            and manifest["config"].get("size")==config_path.stat().st_size and len(layers)==10,"New OCI manifest/config chain differs")
    required={"index.json","oci-layout","manifest.json","blobs/sha256/"+MANIFEST[7:],"blobs/sha256/"+CONFIG[7:]}
    for layer in layers:
        require(re.fullmatch(r"sha256:[0-9a-f]{64}",layer.get("digest","")) and type(layer.get("size")) is int
                and layer.get("mediaType")=="application/vnd.oci.image.layer.v1.tar+gzip","Unexpected layer descriptor")
        name="blobs/sha256/"+layer["digest"][7:];required.add(name)
        require((layout/name).stat().st_size==layer["size"],"Layer descriptor size differs")
    require(seen==required and len(required)==15,"Archive must contain the exact twelve blobs and three metadata files")
    require(len(classic)==1 and classic[0].get("RepoTags")==["ecoguard-inference:c-20261024-2"]
            and classic[0].get("Config")=="blobs/sha256/"+CONFIG[7:]
            and classic[0].get("Layers")==["blobs/sha256/"+v["digest"][7:] for v in layers],"Classic Docker linkage differs")
    require(config.get("architecture")=="amd64" and config.get("os")=="linux" and config.get("rootfs",{}).get("type")=="layers"
            and len(config.get("rootfs",{}).get("diff_ids",[]))==10 and config.get("config",{}).get("User")=="10001:10001"
            and config["config"].get("WorkingDir")=="/app","Image platform/nonroot/rootfs differs")
    # Classic metadata is verified but is not part of the pushed OCI layout.
    (layout/"manifest.json").unlink()
    return manifest,config


def remote_small(operation,reference,filename):
    result=subprocess.run([str(CRANE),operation,reference],env=ENV,stdin=subprocess.DEVNULL,capture_output=True,timeout=120,shell=False)
    require(result.returncode==0 and len(result.stdout)<1024**2,"Remote manifest/config read failed/oversized")
    (RESULT/filename).write_bytes(result.stdout);return result.stdout


def verify_remote_layers(layers):
    verified=[]
    for index,layer in enumerate(layers):
        path=RESULT/("remote-layer-"+str(index)+".partial")
        try:
            with path.open("xb") as output:
                result=subprocess.run([str(CRANE),"blob",IMAGE+"@"+layer["digest"]],env=ENV,stdin=subprocess.DEVNULL,
                    stdout=output,stderr=subprocess.PIPE,timeout=300,shell=False)
            require(result.returncode==0 and path.stat().st_size==layer["size"]
                    and "sha256:"+sha(path)==layer["digest"],"Remote compressed layer bytes/size differ")
            verified.append({"digest":layer["digest"],"size":layer["size"],"rawBytesMatchArchive":True})
        finally:
            if path.exists():path.unlink()
    return verified


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--publish",action="store_true");args=parser.parse_args()
    if not args.publish:
        print(json.dumps({"status":"dry-run","cloudInvoked":False,"target":TARGET,"imageUri":IMAGE+"@"+MANIFEST,
            "onePushCommand":True,"oldImagePreserved":True,"runtimeActivated":False,"requiresActualUploadedArchive":True}));return 0
    require(sys.platform=="linux" and platform.machine()=="x86_64" and os.environ.get("CLOUD_SHELL")=="true","Existing x86_64 CloudShell required")
    require(type(ARCHIVE_BYTES) is int and all(re.fullmatch(r"[0-9a-f]{64}",v) for v in (ARCHIVE_SHA,EXPORT_SHA)),"Final archive/export pins missing")
    require(not RESULT.exists() and not RESULT.is_symlink(),"Publication attempt exists; no retry")
    for key in ("DOCKER_AUTH_CONFIG","REGISTRY_AUTH_FILE","GOOGLE_APPLICATION_CREDENTIALS","GOOGLE_OAUTH_ACCESS_TOKEN","GOOGLE_CREDENTIALS","GOOGLE_IMPERSONATE_SERVICE_ACCOUNT","GOOGLE_IMPERSONATE_SERVICE_ACCOUNT_DELEGATES","GOOGLE_CLOUD_KEYFILE_JSON","GCLOUD_KEYFILE_JSON","CLOUDSDK_AUTH_ACCESS_TOKEN","CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT","CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE","SSL_CERT_FILE","SSL_CERT_DIR","CURL_CA_BUNDLE","HTTPS_PROXY","HTTP_PROXY","ALL_PROXY","https_proxy","http_proxy","all_proxy"):
        require(not os.environ.get(key),"Unreviewed credential/TLS/proxy override: "+key)
    require(CRANE.is_file() and not CRANE.is_symlink() and sha(CRANE)==CRANE_SHA,"Existing official crane binary differs")
    require(CLIENT.is_dir() and not CLIENT.is_symlink() and not (CLIENT/"config.json").is_symlink()
            and local(CLIENT/"config.json")=={"credHelpers":{HOST:"gcloud"}} and shutil.which("docker-credential-gcloud"),"Existing credential-helper configuration differs")
    require(read([CRANE,"version"]).lstrip("v")=="0.22.1" and "crane blob BLOB" in read([CRANE,"blob","--help"]),"Official crane version/blob command shape differs")
    h=load("image2_historical_http",FROZEN_HTTP,FROZEN_HTTP_SHA)
    m=h.load_frozen("image2_historical_publisher",h.FROZEN_PUBLISH,h.FROZEN_PUBLISH_SHA);m.ENV=ENV
    a=h.load_frozen("image2_historical_apply",h.FROZEN_APPLY,h.FROZEN_APPLY_SHA)
    require(h.BASE==BASE and h.STATE==STATE and h.IMAGE==IMAGE+"@"+OLD_DIGEST,"Historical proof scope differs")
    def source_exact():
        return read(["git","-C",SOURCE,"rev-parse","HEAD"])==HEAD and not read(["git","-C",SOURCE,"status","--porcelain","--untracked-files=no"])
    require(source_exact() and sha(SOURCE/"config/model.locked.json")==h.MANIFEST_SHA,"New source/model manifest differs")
    _,detail_path,evidence=h.deployment_evidence(a,m);detail=local(detail_path)
    require(sha(STATE)==STATE_SHA and a.raw_state(STATE.read_bytes(),13)["serial"]==17,"Exact physical13/serial17 differs")
    a.GATE=load("image2_runtime_gate",ROOT/"check_runtime_plan.py",sha(ROOT/"check_runtime_plan.py"))
    require(EXPORT.is_file() and not EXPORT.is_symlink() and sha(EXPORT)==EXPORT_SHA,"Reviewed export evidence differs")
    export=local(EXPORT)
    require(exact(export,{"imageId":MANIFEST,"imageConfigDigest":CONFIG,"archiveBytes":ARCHIVE_BYTES,"archiveSHA256":ARCHIVE_SHA,
        "imageSizeBytes":IMAGE_BYTES,"hostCredentialPathsFound":[],"unexpectedAppOrConfigFiles":[],"modelCacheIncluded":False,
        "buildCommit":HEAD,"buildInputFilesVerified":22,"installedSourceFilesVerified":20,"verifiedLayers":10,
        "firstEightBaseDependencyDiffIdsMatchPriorReviewedImage":True}),"Export artifact identity/safety evidence differs")
    approval_link=local(h.PLAN/"apply-approval.json")["billingAccountName"]  # Identity anchor only; never treated as publication approval.
    require(read(["gcloud","auth","list","--filter=status:ACTIVE","--format=value(account)"])==h.OPERATOR
            and read(["gcloud","config","get-value","project"])==PROJECT,"Existing operator/project differs")
    for setting in ("auth/impersonate_service_account","auth/credential_file_override"):
        require(read(["gcloud","config","get-value",setting]) in ("","(unset)"),"Configured credential override")
    project=m.cloud("projects","describe",PROJECT)
    require(project.get("projectId")==PROJECT and str(project.get("projectNumber"))==NUMBER
            and project.get("lifecycleState")=="ACTIVE","Canonical live project differs")
    funding()
    billing=m.cloud("billing","projects","describe",PROJECT)
    require(billing.get("billingEnabled") is True and billing.get("billingAccountName")==approval_link,"Existing live project billing link differs")
    def identities():return a.HTTP_IDENTITY_READER(m,after=True)
    def service_iam():return m.cloud("run","services","get-iam-policy","ecoguard-inference","--region="+REGION,"--project="+PROJECT)
    require(m.private_policies()==detail["iamAfter"] and identities()==detail["identityAfter"]
            and service_iam()==detail["run"]["servicePolicy"] and not a.edges(m.cloud("iam","service-accounts","get-iam-policy",a.RUNTIME,"--project="+PROJECT)),"Full existing IAM/identities differ")
    services=m.cloud("services","list","--enabled","--project="+PROJECT)
    enabled={v.get("config",{}).get("name") for v in services}
    require({"artifactregistry.googleapis.com","run.googleapis.com"}<=enabled and not enabled.intersection({"containerscanning.googleapis.com","ondemandscanning.googleapis.com"}),"Existing API/scanning state differs")
    def repository():return m.cloud("artifacts","repositories","describe","ecoguard","--location="+REGION,"--project="+PROJECT)
    before_repo=repository()
    require(before_repo.get("name")==f"projects/{PROJECT}/locations/{REGION}/repositories/ecoguard" and before_repo.get("format")=="DOCKER"
            and before_repo.get("mode")=="STANDARD_REPOSITORY" and before_repo.get("labels")=={"goog-terraform-provisioned":"true"}
            and not before_repo.get("remoteRepositoryConfig") and not before_repo.get("virtualRepositoryConfig"),"Existing private repository differs")
    observed=BASE/"image2-publication-preflight-observation-20261024-1/repository-private.json"
    require(observed.is_file() and not observed.is_symlink()
            and sha(observed)=="2db97ca7c0e7908207fabb0b0378981f2b868bddb8f7e23d12012daf0e8a0943"
            and before_repo==local(observed),"Exact retained preflight repository observation differs")
    tags=read([CRANE,"ls",IMAGE]).splitlines()
    require(OLD_TAG in tags and NEW_TAG not in tags and len(tags)==len(set(tags))
            and read([CRANE,"digest",IMAGE+":"+OLD_TAG])==OLD_DIGEST,"Old image/tag missing or new target already exists")
    hashes={p:sha(p) for p in evidence|{FROZEN_HTTP,CRANE,CLIENT/"config.json",FUNDING,EXPORT,observed}}
    def stable():
        require(source_exact() and sha(STATE)==STATE_SHA and all(p.is_file() and not p.is_symlink() and sha(p)==v for p,v in hashes.items()),"Source/state/historical evidence changed")
        require(m.private_policies()==detail["iamAfter"] and identities()==detail["identityAfter"] and service_iam()==detail["run"]["servicePolicy"]
                and not a.edges(m.cloud("iam","service-accounts","get-iam-policy",a.RUNTIME,"--project="+PROJECT)),"Existing full IAM/identities changed")
    stable();require(shutil.disk_usage(BASE).free>1024**3,"Insufficient private working space")
    os.umask(0o077);RESULT.mkdir(mode=0o700)
    summary={"status":"blocked","sourceRevision":HEAD,"project":PROJECT,"projectNumber":NUMBER,"target":TARGET,
        "archiveSHA256":ARCHIVE_SHA,"archiveBytes":ARCHIVE_BYTES,"configDigest":CONFIG,"registryDigest":None,
        "standingAuthorization":STANDING,"fundingEvidenceSHA256":FUNDING_SHA,"toolBinarySHA256":CRANE_SHA,
        "pushAttempted":False,"pushReturnedSuccess":False,"pushCommandCount":0,"automaticPushCommandRetry":False,
        "underlyingClientTransportRetriesPossible":True,"runtimeActivated":False,"iamModified":False,"apisModified":False,"tokensPersisted":False}
    try:
        save("attempt-started.json",{**summary,"startedAtUtc":now()});save("input-evidence-sha256-private.json",{str(p):v for p,v in hashes.items()})
        save("funding-copy-private.json",funding());save("repository-before-private.json",before_repo)
        save("enabled-apis-before-private.json",services)
        (RESULT/"state-before-private-backup.tfstate").write_bytes(STATE.read_bytes())
        layout=RESULT/"oci-layout";manifest,config=extract_archive(ARCHIVE,layout)
        require(config["rootfs"]["diff_ids"]==export["rootFsDiffIds"]
                and [{"digest":v["digest"],"size":v["size"],"mediaType":v["mediaType"]} for v in manifest["layers"]]
                    == [{"digest":v["digest"],"size":v["bytes"],"mediaType":v["mediaType"]} for v in export["layerEvidence"]],"Reviewed export/rootfs/layer chain differs")
        save("oci-layout-verification.json",{"manifestDigest":MANIFEST,"configDigest":CONFIG,"layers":manifest["layers"],"rootFsDiffIds":config["rootfs"]["diff_ids"],"sourceRevision":HEAD})
        funding();stable();require(repository()==before_repo and read([CRANE,"ls",IMAGE]).splitlines()==tags,"Repository/tag inventory changed before push")
        save("push-started.json",{"target":TARGET,"imageUri":IMAGE+"@"+MANIFEST,"startedAtUtc":now(),"pushCommandCount":1})
        summary.update(pushAttempted=True,pushCommandCount=1)
        with (RESULT/"push-private.log").open("xb") as log:
            result=subprocess.run([str(CRANE),"push",str(layout),TARGET,"--image-refs",str(RESULT/"published-reference.txt")],env=ENV,
                stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=1200,shell=False)
        require(result.returncode==0,"Single push failed; do not retry");summary["pushReturnedSuccess"]=True
        require((RESULT/"published-reference.txt").read_text().strip()==IMAGE+"@"+MANIFEST,"Pushed immutable reference differs")
        require(read([CRANE,"digest",TARGET])==MANIFEST and read([CRANE,"digest",IMAGE+":"+OLD_TAG])==OLD_DIGEST
                and set(read([CRANE,"ls",IMAGE]).splitlines())==set(tags)|{NEW_TAG},"New/old tag preservation differs")
        raw_manifest=remote_small("manifest",IMAGE+"@"+MANIFEST,"registry-manifest-private.json")
        raw_config=remote_small("config",IMAGE+"@"+MANIFEST,"registry-config-private.json")
        require(raw_manifest==(layout/"blobs/sha256"/MANIFEST[7:]).read_bytes() and raw_config==(layout/"blobs/sha256"/CONFIG[7:]).read_bytes(),"Remote original manifest/config bytes differ")
        save("registry-layer-verification-private.json",verify_remote_layers(manifest["layers"]))
        after_repo=repository();save("repository-after-private.json",after_repo)
        require({k:v for k,v in before_repo.items() if k not in {"updateTime","sizeBytes"}}=={k:v for k,v in after_repo.items() if k not in {"updateTime","sizeBytes"}}
                and datetime.fromisoformat(after_repo["updateTime"].replace("Z","+00:00"))>datetime.fromisoformat(before_repo["updateTime"].replace("Z","+00:00")),"Repository changed beyond exact upload metadata")
        stable();after_services=m.cloud("services","list","--enabled","--project="+PROJECT);save("enabled-apis-after-private.json",after_services)
        require({v.get("config",{}).get("name") for v in after_services}==enabled,"Enabled APIs changed")
        summary.update(status="private-inference-image-published-and-verified",registryDigest=MANIFEST,imageUri=IMAGE+"@"+MANIFEST,
            remoteManifestAndConfigBytesMatch=True,remoteCompressedLayersMatchArchive=True,oldImagePreserved=True,
            repositoryObservationPath=str(RESULT/"repository-after-private.json"),repositoryObservationSHA256=sha(RESULT/"repository-after-private.json"),
            repositoryUpdateTime=after_repo["updateTime"],cloudInferenceVerified=False,crossCloudVerified=False)
    except Exception as error:
        summary.update(errorType=type(error).__name__,error=str(error) if isinstance(error,RuntimeError) else "Inspect private publication evidence; no retry")
        if isinstance(error,subprocess.TimeoutExpired):summary["processOutcomeUncertain"]=True
    finally:
        try:
            (RESULT/"state-after-private-backup.tfstate").write_bytes(STATE.read_bytes());stable()
            summary["stateFileUnchanged"]=True;summary["fullIAMUnchanged"]=True
        except Exception as error:summary.update(status="blocked",stateFileUnchanged=sha(STATE)==STATE_SHA,postVerificationErrorType=type(error).__name__)
        summary["observedAtUtc"]=now();save("summary.json",summary);print(json.dumps(summary,separators=(",",":")),flush=True)
    return 0 if summary["status"]=="private-inference-image-published-and-verified" else 1


if __name__=="__main__":
    try:raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"status":"blocked","pushAttempted":False,"errorType":type(error).__name__,
            "error":str(error) if isinstance(error,RuntimeError) else "Invalid/incomplete image2 publication prerequisites"}),flush=True)
        raise SystemExit(1)
