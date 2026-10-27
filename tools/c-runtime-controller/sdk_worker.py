"""Default inert. Fixed AWS SDK read batch worker, never a mutation dispatcher."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import importlib.util
import json
import logging
import math
import os
from pathlib import Path
import re
import sys
import stat
import time

sys.dont_write_bytecode=True
# Must be filled only from the reviewed bridge bytes before a real invocation.
BRIDGE_SHA256='aaedd932c2870fcb3031f1749b5f2e9b72dd4d5abfd47a173eb2dd6d2a78eec0'
PHASE="startup"
FAILURE_SAVE=None


def main():
    global PHASE,FAILURE_SAVE
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--sdk-batch-readonly',action='store_true');parser.add_argument('--nonce');args=parser.parse_args()
    if not args.sdk_batch_readonly:print('{"status":"sdk-read-batch-inert","cloudInvoked":false}');return 0
    if not isinstance(BRIDGE_SHA256,str) or not re.fullmatch('[0-9a-f]{64}',BRIDGE_SHA256):raise ValueError('Reviewed bridge pin pending')
    bridge=Path(__file__).with_name('sdk_batch.py');raw=bridge.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=BRIDGE_SHA256:raise ValueError('Bridge SHA differs')
    spec=importlib.util.spec_from_file_location('fixed_sdk_batch_bridge',bridge);b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
    b.regular(bridge,BRIDGE_SHA256)
    payload=sys.stdin.buffer.read(262145);b.require(len(payload)<=262144,'SDK batch input bound exceeded');p=json.loads(payload)
    b.require(type(p) is dict and set(p)=={'recordType','kind','jobs','scope','deadline','evidenceDir','nonce','parentPID','parentPGID','parentSID','uid','bootID','runtime','bridge','sdkManifest','credentialRoute'} and p['recordType']=='exact-sdk-readonly-batch-v1','Exact SDK batch protocol required')
    b.require(p['nonce']==args.nonce and type(args.nonce) is str and re.fullmatch('[0-9a-f]{64}',args.nonce),'Worker nonce differs')
    b.require(sys.platform=='linux' and p['uid']==os.getuid()==1000 and p['parentPID']==os.getppid() and p['parentPGID']==os.getpgrp() and p['parentSID']==os.getsid(0)
      and p['bootID']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'Worker parent/VM identity differs')
    b.require(type(p['deadline']) in (int,float) and math.isfinite(p['deadline']) and 0<p['deadline']-time.monotonic()<=9.01,'Worker shared deadline invalid')
    b.require(p['bridge']=={'path':str(bridge),'sha256':BRIDGE_SHA256} and Path(p['runtime']['path'])==bridge.with_name('aws_runtime.py'),'Worker sibling pins differ')
    runtime=b.load(p['runtime']['path'],p['runtime']['sha256'],'fixed_sdk_read_runtime')
    expected=b.exact_jobs(runtime,p['scope'],p['kind'],p['jobs'])
    env=runtime.reviewed_environment(dict(os.environ),credential_route=p['credentialRoute']);b.require(env==dict(os.environ),'Worker isolated environment differs')
    evidence=Path(p['evidenceDir']);info=evidence.stat()
    b.require(evidence.is_relative_to(Path('/home/cloudshell-user/ecoguard-c-personal-20261023')) and re.fullmatch('sdk-'+p['kind']+'-'+str(p['parentPID'])+r'-[0-9]{6}-raw',evidence.name)
      and not any(x.is_symlink() for x in (evidence,*evidence.parents)) and info.st_uid==os.getuid() and stat.S_IMODE(info.st_mode)==0o700,'Exact private SDK evidence directory differs')
    cache=evidence/'empty-pycache'
    b.require(sys.pycache_prefix==str(cache) and cache.is_dir() and not cache.is_symlink() and not any(cache.iterdir()) and stat.S_IMODE(cache.stat().st_mode)==0o700,'Isolated empty bytecode cache prefix differs')
    def save(name,value):
        data=json.dumps(value,allow_nan=False).encode();b.require(len(data)<=b.MAX_OUTPUT,'SDK raw response bound exceeded')
        with (evidence/name).open('xb') as f:os.fchmod(f.fileno(),0o600);f.write(data);f.flush();os.fsync(f.fileno())
        fd=os.open(evidence,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(fd)
        finally:os.close(fd)
    FAILURE_SAVE=save;PHASE='native-sdk-file-verification'
    native=b.verify_sdk_manifest(p['sdkManifest'])
    PHASE='sdk-import'
    import boto3
    import botocore
    from botocore.config import Config
    b.require(boto3.__version__==native['packages']['boto3']['version'] and botocore.__version__==native['packages']['botocore']['version'],'SDK installed version differs')
    # Explicit Session/client construction is sequential; clients alone are shared.
    PHASE='client-construction'
    session=boto3.session.Session(region_name=b.REGION)
    services=sorted({value[0] for value in expected.values()});clients={}
    for service in services:
        b.require(time.monotonic()<p['deadline'],'SDK client creation exceeded shared deadline')
        clients[service]=session.client(service,region_name=b.REGION,verify=True,config=Config(connect_timeout=2,read_timeout=2,retries={'mode':'standard','total_max_attempts':1},max_pool_connections=b.WORKERS))
    def read(item):
        name,(service,operation,params)=item;start=time.monotonic();b.require(start<p['deadline'],'SDK read expired before call')
        b.require(env==dict(os.environ) and env==runtime.reviewed_environment(dict(os.environ),credential_route=p['credentialRoute']),'SDK credential route changed')
        wire=({'registryId':params['RegistryId'],'repositoryName':params['RepositoryName']} if (service,operation)==('ecr','get-repository-policy') else params)
        # Method names are selected only through the closed reviewed table.
        key=hashlib.sha256(name.encode()).hexdigest()
        row={'job':name,'request':(service,operation,params),'startedMonotonic':start}
        save(key+'-intent.json',row)  # durable exact one API-call intent
        try:
            response=getattr(clients[service],b.OPERATIONS[service][operation])(**wire)
            row['rawSDKResponse']=b.serialize_sdk(response,service,operation)
            end=time.monotonic();row['endedMonotonic']=end
            b.require(end<=p['deadline'],'SDK response exceeded shared deadline')
            modeled=b.serialize_sdk(response,service,operation,modeled=True)
            b.require(type(modeled) is dict and not modeled.get('NextMarker') and not modeled.get('NextToken') and not modeled.get('IsTruncated'),'Incomplete SDK pagination blocked')
            row['response']=modeled;return row
        except Exception as error:
            # Full service error response is private; exception text, credentials,
            # request headers/endpoint and traceback are never emitted.
            row['errorType']=type(error).__name__;row['endedMonotonic']=time.monotonic()
            if type(getattr(error,'response',None)) is dict:row['rawSDKErrorResponse']=b.serialize_sdk(error.response,service,operation)
            raise
        finally:save(key+'-outcome.json',row)
    PHASE='fixed-service-reads'
    with ThreadPoolExecutor(max_workers=b.WORKERS) as executor:
        futures=[executor.submit(read,item) for item in expected.items()]
        outcomes=[f.result(timeout=max(.001,p['deadline']-time.monotonic())) for f in futures]
    b.require(time.monotonic()<=p['deadline'] and env==dict(os.environ),'SDK batch serialization deadline/environment differs')
    output={'status':'complete-readonly-sdk-batch','kind':p['kind'],'requestSHA256':b.digest(p),'outcomes':outcomes,'responses':{v['job']:v['response'] for v in outcomes}}
    PHASE='serialize-complete-group'
    encoded=json.dumps(output,allow_nan=False).encode();b.require(len(encoded)<=b.MAX_OUTPUT and time.monotonic()<=p['deadline'],'SDK batch output bound exceeded')
    sys.stdout.buffer.write(encoded);return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        if FAILURE_SAVE is not None:
            try:FAILURE_SAVE('worker-failure.json',{'phase':PHASE,'errorType':type(error).__name__,'reason':'fixed-sdk-worker-phase-unverified','retryPermitted':False})
            except Exception:pass
        raise SystemExit(1)
