"""Default-inert exact read-only SDK batch bridge. No SDK imports at import time."""
import base64
import copy
from datetime import datetime
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time

ACCOUNT='011154879765'; REGION='us-east-1'; PREFIX='ecoguard3184-personal'
WORKERS=4; MAX_OUTPUT=4*1024*1024; CLEANUP_RESERVE=1.0
# Exact modeled datetime paths present in the original boundary catalog.
DATES={('iam','get-role'):{('Role','CreateDate'),('Role','RoleLastUsed','LastUsedDate')},
 ('cognito-idp','describe-user-pool'):{('UserPool','CreationDate'),('UserPool','LastModifiedDate')},
 ('apigatewayv2','get-api'):{('CreatedDate',)},
 ('apigatewayv2','get-stage'):{('CreatedDate',),('LastUpdatedDate',)},
 ('lambda','get-event-source-mapping'):{('LastModified',),('StartingPositionTimestamp',)}}
OPERATIONS={
 'sts':{'get-caller-identity':'get_caller_identity'},
 'lambda':{k:k.replace('-','_') for k in ('get-account-settings','get-function-configuration','get-function-concurrency','get-policy','get-event-source-mapping')},
 'iam':{k:k.replace('-','_') for k in ('get-role','list-attached-role-policies','list-role-policies','get-role-policy')},
 'ecr':{'get-repository-policy':'get_repository_policy'},
 'apigatewayv2':{'get-api':'get_api','get-stage':'get_stage'},
 'cognito-idp':{'describe-user-pool':'describe_user_pool'},
 'events':{'describe-rule':'describe_rule','list-targets-by-rule':'list_targets_by_rule'},
 'dynamodb':{'scan':'scan'},'sqs':{'get-queue-attributes':'get_queue_attributes'}}


def require(ok,message):
    if not ok:raise ValueError(message)
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def regular(path,expected,private=False):
    path=Path(path); require(path.is_absolute() and not any(p.is_symlink() for p in (path,*path.parents)),'Pinned real absolute file required')
    s=path.stat();require(stat.S_ISREG(s.st_mode) and s.st_uid in (0,os.getuid()) and not s.st_mode&0o022,'Pinned file permissions differ')
    if private:require(s.st_uid==os.getuid() and stat.S_IMODE(s.st_mode)==0o600 and s.st_nlink==1,'Private file permissions differ')
    require(type(expected) is str and re.fullmatch('[0-9a-f]{64}',expected) and file_sha(path)==expected,'Pinned file SHA differs');return path

def python_tool(path,expected):
    # The observed CloudShell virtualenv entry point must remain the executable:
    # running /usr/bin/python3.13 directly would change isolated import paths.
    require(path=='/usr/local/python3.13/bin/python3' and str(Path(path).resolve())=='/usr/bin/python3.13'
      and expected=='33a0bf50d1e98dfaf4b15f342c9187cb6af4787d86c8708f846cfd8ea8498f24','Exact observed interpreter alias differs')
    return regular('/usr/bin/python3.13',expected)

def load(path,expected,name):
    regular(path,expected);s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m

def backlog_jobs():
    jobs={}
    for n in ('media','operations','outbox','search','subscriptions'):
        jobs['table:'+n]=('dynamodb','scan',{'TableName':PREFIX+'-'+n,'ConsistentRead':True,'Select':'COUNT','Limit':100})
    for n in ('ingest','infer','delete','notify'):
        for suffix in ('','-dlq'):
            n2=n+suffix;jobs['queue:'+n2]=('sqs','get-queue-attributes',{'QueueUrl':f'https://sqs.{REGION}.amazonaws.com/{ACCOUNT}/{PREFIX}-{n2}',
             'AttributeNames':['QueueArn','ApproximateNumberOfMessages','ApproximateNumberOfMessagesNotVisible','ApproximateNumberOfMessagesDelayed']})
    return jobs

def exact_jobs(runtime,scope,kind,jobs):
    require(type(scope) is dict and set(scope)=={'context','readonly'},'Exact read scope required')
    expected=(runtime.RawReader(None,scope['context'],scope['readonly'],None,None).boundary_jobs() if kind=='boundary' else backlog_jobs() if kind=='backlog' else None)
    require(expected is not None and digest(jobs)==digest(expected),'Only complete exact boundary/backlog catalog is allowed')
    require(len(jobs)==(27 if kind=='boundary' else 13),'Read catalog count differs')
    selector=object.__new__(runtime.FixedCLI);selector.scope=copy.deepcopy(scope)
    for name,(service,operation,params) in jobs.items():
        require(type(name) is str and service in OPERATIONS and operation in OPERATIONS[service]
          and selector.request_is_exact(service,operation,params,False),'SDK read selector differs')
    return copy.deepcopy(expected)

def serialize_sdk(value,service,operation,*,modeled=False,path=()):
    """Raw evidence tags datetime/bytes; modeled copy follows reviewed CLI paths."""
    if isinstance(value,datetime):
        require(value.tzinfo is not None and value.utcoffset().total_seconds()==0,'SDK datetime must be aware UTC; no date-string normalization')
        iso=value.isoformat()
        if modeled:
            require(path in DATES.get((service,operation),set()),'Unexpected SDK datetime field');return iso
        return {'__sdk_datetime_iso8601__':iso}
    if isinstance(value,bytes):
        require(not modeled,'Unexpected binary field in fixed business response')
        return {'__sdk_bytes_base64__':base64.b64encode(value).decode('ascii')}
    if type(value) is dict:
        require(all(type(k) is str for k in value),'SDK object key must be string')
        return {k:serialize_sdk(v,service,operation,modeled=modeled,path=path+(k,)) for k,v in value.items() if not(modeled and not path and k=='ResponseMetadata')}
    if type(value) is list:return [serialize_sdk(v,service,operation,modeled=modeled,path=path+(i,)) for i,v in enumerate(value)]
    require(value is None or type(value) in (str,int,bool,float),'Unexpected SDK response type')
    if type(value) is float:require(math.isfinite(value),'Nonfinite SDK number')
    return value

def verify_sdk_manifest(reference):
    """Native -I -B observed distribution files; no SDK install/download."""
    require(type(reference) is dict and set(reference)=={'path','sha256'},'Actual SDK inventory pin pending')
    path=regular(reference['path'],reference['sha256'],True);m=json.loads(path.read_text())
    required={'recordType','observedAtUtc','cloudAPIsCalled','credentialsRead','pythonPath','pythonRealPath','pythonVersion','pythonSHA256','platformLibraryAlias','packages'}
    require(type(m) is dict and set(m)==required and m['recordType']=='actual-existing-official-cloudshell-sdk-package-file-metadata' and m['cloudAPIsCalled'] is False and m['credentialsRead'] is False,'Exact native SDK inventory required')
    require(m['pythonPath']==sys.executable and m['pythonRealPath']==str(Path(sys.executable).resolve()) and m['pythonVersion']==sys.version,'Actual isolated Python identity differs')
    require(m['pythonSHA256']=='33a0bf50d1e98dfaf4b15f342c9187cb6af4787d86c8708f846cfd8ea8498f24','Python native SHA differs')
    python_tool(m['pythonPath'],m['pythonSHA256'])
    alias=m['platformLibraryAlias'];require(type(alias) is dict and set(alias)=={'path','resolved','uid'} and alias=={
      'path':'/usr/local/python3.13/lib64','resolved':'/usr/local/python3.13/lib','uid':1000},'Observed standard library alias differs')
    ap=Path(alias['path']);require(ap.is_symlink() and os.readlink(ap)=='lib' and ap.lstat().st_uid==1000 and str(ap.resolve())==alias['resolved'],'Observed library alias changed')
    versions={'boto3':'1.43.83','botocore':'1.43.97','jmespath':'1.1.0','python-dateutil':'2.9.0.post0','urllib3':'2.8.0','s3transfer':'0.19.2','six':'1.17.0'}
    modules={'python-dateutil':'dateutil',**{k:k for k in versions if k!='python-dateutil'}}
    require(type(m['packages']) is dict and set(m['packages'])==set(versions),'Full SDK dependency set differs')
    count=0
    for name,record in m['packages'].items():
        require(type(record) is dict and set(record)=={'installed','version','root','files','excludedOutsidePackageRoot'} and record['installed'] is True
          and record['version']==versions[name] and type(record['excludedOutsidePackageRoot']) is list,'SDK package version/schema differs')
        root=Path(record['root']);files=record['files'];require(root.is_absolute() and str(root.resolve())==str(root) and type(files) is dict and files,'Canonical SDK inventory pending')
        for absolute,entry in files.items():
            fp=Path(absolute);require(fp.is_relative_to(root) and type(entry) is dict and set(entry)=={'sha256','bytes','uid','mode'},'SDK inventory file escaped')
            regular(fp,entry['sha256']);st=fp.stat()
            require(type(entry['bytes']) is int and st.st_size==entry['bytes'] and st.st_uid==entry['uid'] and stat.S_IMODE(st.st_mode)==entry['mode'],'SDK inventory file metadata changed')
        # Distribution root may be site-packages. Restrict executable package
        # trees independently, rejecting newly inserted code/data in each tree.
        origin=Path(importlib.util.find_spec(modules[name]).origin).resolve();require(str(origin) in files,'SDK import origin is not a pinned file')
        code_root=origin.parent if origin.name=='__init__.py' else origin
        if code_root.is_dir():require(not any(q.is_symlink() for q in code_root.rglob('*')),'SDK package tree contains an unreviewed link')
        actual={str(q) for q in code_root.rglob('*') if q.is_file() and '__pycache__' not in q.parts and q.suffix!='.pyc'} if code_root.is_dir() else {str(code_root)}
        expected={f for f in files if Path(f).is_relative_to(code_root)} if code_root.is_dir() else {str(code_root)}
        require(actual==expected,'SDK executable package tree changed')
        count+=len(files)
    require(count==2179,'Native SDK file count differs')
    return m

def capture_worker_identity(proc, child, nonce, argv, deadline, *, monotonic=time.monotonic, sleep=time.sleep):
    """Wait at most one second for this owned child to expose its final argv.

    The request remains outside stdin until full identity proof succeeds. The
    owned Popen child is never replaced, and no numeric PID signal is allowed.
    """
    limit=min(deadline,monotonic()+1.0)
    expected_argv=hashlib.sha256(b'\0'.join(x.encode() for x in argv)+b'\0').hexdigest()
    incarnation=None
    while monotonic()<limit:
        require(child.poll() is None,'SDK worker exited before exact startup ownership')
        try:
            captured=proc.snapshot(child.pid,nonce)
        except RuntimeError as error:
            # /proc cmdline can briefly be empty while the owned child execs.
            # Every other observation error stays fatal, without logging text.
            if error.args!=('Process command is unbounded/malformed',):
                raise
            captured=None
        if captured is not None:
            identity=captured['identity']
            require(captured['ppid']==os.getpid() and identity['pid']==child.pid
              and identity['uid']==os.getuid() and identity['pgid']==os.getpgrp()
              and identity['sid']==os.getsid(0) and identity['bootID']==proc.boot,
              'SDK owned child process scope differs during startup')
            current=(identity['pid'],identity['startTicks'])
            require(incarnation is None or current==incarnation,'SDK owned child incarnation changed during startup')
            incarnation=current
            if identity['nonce']==nonce and identity['cmdlineSHA256']==expected_argv:
                require(monotonic()<=limit and child.poll() is None,'SDK startup proof deadline or child exit')
                return identity
        remaining=limit-monotonic()
        if remaining>0:
            sleep(min(.01,remaining))
    raise ValueError('SDK worker exact startup ownership unavailable within bounded window')


class BatchTransport:
    """One direct child in the current PGID; no session/process-group creation."""
    def __init__(self,runtime,cli,store,pins,proc,nonce,*,popen=subprocess.Popen,monotonic=time.monotonic):
        self.runtime,self.cli,self.store,self.pins,self.proc,self.nonce=runtime,cli,store,copy.deepcopy(pins),proc,nonce
        self.Popen,self.now=popen,monotonic;self.number=0
        require(type(nonce) is str and re.fullmatch('[0-9a-f]{64}',nonce),'Exact SDK worker nonce required')
    def batch(self,jobs,deadline,kind):
        expected=exact_jobs(self.runtime,self.cli.scope,kind,jobs)
        self.number+=1
        slot=f'{os.getpid()}-{self.number:06d}'  # a later scheduled observation is not a retry
        require(self.number<=10000,'SDK logical group count exceeded')
        p=self.pins;require(type(p) is dict and set(p)=={'python','worker','bridge','runtime','sdkManifest'},'Actual SDK worker pins pending')
        python_tool(p['python']['path'],p['python']['sha256'])
        for k in ('worker','bridge','runtime'):regular(p[k]['path'],p[k]['sha256'])
        regular(p['sdkManifest']['path'],p['sdkManifest']['sha256'],True)
        require(Path(p['worker']['path']).parent==Path(p['bridge']['path']).parent==Path(p['runtime']['path']).parent,'Worker reviewed siblings differ')
        require(self.cli.env==self.cli._initial_env and self.cli.env==self.runtime.reviewed_environment(self.cli.env,credential_route=self.cli.credential_route),'SDK memory-only credential route changed')
        remaining=deadline-self.now();require(math.isfinite(remaining) and CLEANUP_RESERVE<remaining<=10.01,'SDK group deadline expired/unbounded')
        evidence=Path(self.store.path)/('sdk-'+kind+'-'+slot+'-raw')
        require(evidence.is_absolute() and not any(x.is_symlink() for x in (evidence,*evidence.parents)),'SDK evidence path differs')
        evidence.mkdir(mode=0o700)  # exclusive: preserves a failed group, no retry/overwrite
        (evidence/'empty-pycache').mkdir(mode=0o700)
        request={'recordType':'exact-sdk-readonly-batch-v1','kind':kind,'jobs':expected,'scope':self.cli.scope,'deadline':deadline-CLEANUP_RESERVE,
          'evidenceDir':str(evidence),'nonce':self.nonce,'parentPID':os.getpid(),'parentPGID':os.getpgrp(),'parentSID':os.getsid(0),'uid':os.getuid(),'bootID':self.proc.boot,
          'runtime':p['runtime'],'bridge':p['bridge'],'sdkManifest':p['sdkManifest'],'credentialRoute':self.cli.credential_route}
        self.store.intent('sdk:'+kind+':'+slot,{'kind':kind,'logicalReadSlot':slot,'jobs':expected,'mutation':False})
        argv=[p['python']['path'],'-I','-B','-X','pycache_prefix='+str(evidence/'empty-pycache'),p['worker']['path'],'--sdk-batch-readonly','--nonce',self.nonce]
        child=None;identity=None;outcome={'kind':kind,'rawEvidenceDirectory':str(evidence),'requestSHA256':digest(request),'startedMonotonic':self.now(),'outerProcessMaximum':1,'AWS_MAX_ATTEMPTS':1,'mutation':False}
        try:
            # No PIPE secret output is displayed or logged; bounded private result only.
            outcome['phase']='spawn-worker'
            child=self.Popen(argv,env=dict(self.cli.env),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,shell=False,start_new_session=False)
            outcome['phase']='acquire-exact-worker-identity'
            identity=capture_worker_identity(self.proc,child,self.nonce,argv,deadline-CLEANUP_RESERVE,monotonic=self.now)
            outcome['phase']='communicate-reviewed-request'
            stdout,_=child.communicate(json.dumps(request,allow_nan=False).encode(),timeout=max(.001,deadline-CLEANUP_RESERVE-self.now()))
            outcome.update(exitCode=child.returncode,stdoutBytes=len(stdout))
            require(len(stdout)<=MAX_OUTPUT and child.returncode==0,'SDK worker failed/unbounded result')
            result=json.loads(stdout);require(type(result) is dict and set(result)=={'status','kind','requestSHA256','outcomes','responses'}
              and result['status']=='complete-readonly-sdk-batch' and result['kind']==kind and result['requestSHA256']==digest(request),'SDK batch protocol differs')
            require(set(result['responses'])==set(expected) and len(result['outcomes'])==len(expected),'SDK batch incomplete')
            for row in result['outcomes']:
                require(type(row) is dict and set(row)=={'job','request','startedMonotonic','endedMonotonic','rawSDKResponse','response'}
                  and row['job'] in expected and digest(row['request'])==digest(expected[row['job']]) and digest(row['response'])==digest(result['responses'][row['job']]),'SDK outcome differs')
                require(type(row['rawSDKResponse']) is dict and type(row['response']) is dict,'SDK object response required')
                self.store.append_json('sdk-raw-outcome',row)
            require(len({r['job'] for r in result['outcomes']})==len(expected),'Duplicate SDK outcome')
            require(self.now()<=deadline-CLEANUP_RESERVE,'SDK result exceeded work deadline')
            outcome.update(success=True,exitCode=0,phase='complete-readonly-batch');return result['responses']
        except Exception:
            outcome.update(success=False,category='sdk-batch-unverified-no-retry');raise RuntimeError('sdk-batch-unverified-no-retry') from None
        finally:
            if child is not None and child.poll() is None:
                if identity is None and child.stdin is not None:
                    child.stdin.close()  # worker has received no request and cannot call AWS
                    try:child.wait(timeout=max(.001,min(.2,deadline-self.now())))
                    except subprocess.TimeoutExpired:pass
                # Identity may be unavailable: never fall back to a numeric PID.
                if identity is not None:
                    for sig in (signal.SIGTERM,signal.SIGKILL):
                        if child.poll() is not None:break
                        try:self.proc.signal_exact(identity,sig,self.nonce)
                        except (ProcessLookupError,FileNotFoundError):pass
                        except Exception:outcome['ownedCleanupVerified']=False;break
                        try:child.wait(timeout=max(.001,min(.35,deadline-self.now())))
                        except subprocess.TimeoutExpired:pass
                outcome['ownedCleanupVerified']=child.poll() is not None
            if child is not None:
                for handle in (child.stdin,child.stdout):
                    if handle is not None and not handle.closed:handle.close()
            outcome['endedMonotonic']=self.now()
            if self.now()>deadline:outcome.update(success=False,category='sdk-parent-cleanup-or-evidence-deadline-exceeded')
            self.store.append_json('sdk-batch-outcome',outcome)
            require(self.now()<=deadline,'SDK full parent shared deadline exceeded')

def reader_class(runtime):
    class SDKRawReader(runtime.RawReader):
        def __init__(self,*args,batch_transport,**kwargs):super().__init__(*args,**kwargs);self.batch_transport=batch_transport
        def batch(self,jobs,deadline,kind):return self.batch_transport.batch(jobs,deadline,kind)
    return SDKRawReader
