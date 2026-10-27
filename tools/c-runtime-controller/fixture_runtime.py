"""Owned-writer fixed transport for frozen automatic_fixture helper; import inert.

Only seed TransactWriteItems and one conditional source PutObject can write.
Google checks consume fresh pinned raw observations, never operator model HTTP.
"""
import base64
from datetime import datetime,timezone,timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
import uuid

PROJECT='ecoguard-fit3184-a2-2026';NUMBER='995070689587';GCP_REGION='us-central1'
ACCOUNT='011154879765';REGION='us-east-1';PREFIX='ecoguard3184-personal'
RUN='https://ecoguard-inference-adlnb7yumq-uc.a.run.app'
INVOKER='ecoguard-aws-invoker@'+PROJECT+'.iam.gserviceaccount.com'
RUNTIME='ecoguard-inference@'+PROJECT+'.iam.gserviceaccount.com'
POOL='projects/'+NUMBER+'/locations/global/workloadIdentityPools/ecoguard-aws'
AWS_ROLE='arn:aws:sts::'+ACCOUNT+':assumed-role/'+PREFIX+'-lambda'
PRINCIPAL='principalSet://iam.googleapis.com/'+POOL+'/attribute.aws_role/'+AWS_ROLE
MAPPING={'google.subject':'assertion.arn','attribute.aws_role':"assertion.arn.contains('assumed-role') ? assertion.arn.extract('{account_arn}assumed-role/') + 'assumed-role/' + assertion.arn.extract('assumed-role/{role_name}/') : assertion.arn"}
PRIVATE_GCP_BASELINE_SHA256='247c9ffaed655fb33338f72ddfd0c67110e4090cef253677d10f3b484f9415f2'
RUNTIME_ENV={'SERVICE_AUTH_MODE':'cloud-run',
 'COGNITO_ISSUER':'https://cognito-idp.us-east-1.amazonaws.com/us-east-1_Sog8ekMM1','COGNITO_CLIENT_ID':'5gu7g1rgkmabdd551h5k3350f6',
 'SOURCE_S3_HOSTS':PREFIX+'-'+ACCOUNT+'-media.s3.'+REGION+'.amazonaws.com','SOURCE_KEY_PREFIXES':'derived/,queries/',
 'MODEL_MANIFEST_PATH':'/config/model.locked.json','MODEL_MANIFEST_SHA256':'639595e1e9ffe18cb11ead1c7480ffe7a31bf767f6cbaf6b8375829227a569ae',
 'INFERENCE_TIMEOUT_SECONDS':'240'}


def require(ok,reason):
    if not ok:raise ValueError(reason)


def stamp(s):
    d=datetime.fromisoformat(s.replace('Z','+00:00'));require(d.tzinfo is not None,'Aware UTC timestamp required');return d


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def file_record(spec):
    require(type(spec) is dict and set(spec)=={'path','sha256'} and type(spec['sha256']) is str and re.fullmatch('[0-9a-f]{64}',spec['sha256']),'Actual fresh GCP/artifact pins pending')
    p=Path(spec['path']);require(p.is_absolute() and p.is_file() and not any(q.is_symlink() for q in (p,*p.parents)) and sha(p)==spec['sha256'],'Frozen evidence path/SHA differs')
    return json.loads(p.read_text())


def sole_binding(policy,role,member):
    b=policy.get('bindings')
    return (type(b) is list and len(b)==1 and type(b[0]) is dict and b[0].get('role')==role
      and b[0].get('members')==[member] and b[0].get('condition') is None)


def exact(a,b):
    return json.dumps(a,sort_keys=True,separators=(',',':'),allow_nan=False)==json.dumps(b,sort_keys=True,separators=(',',':'),allow_nan=False)


def gcp_fresh(spec,context,*,now=None,required_until=None):
    """Hard gate from actual fresh raw Run/IAM/WIF and official credit evidence.

    No gcloud credentials/CLI are copied into AWS. Root must freshly collect the
    read-only raw observation in GCP, retain its reader/source evidence chain and
    pin those bytes here. A configVerified=True assertion alone is insufficient.
    """
    now=now or datetime.now(timezone.utc)
    require(type(spec) is dict and set(spec)=={'observation','funding','billing','imageURI','readyRevision','serviceUID','privateBaseline'},'GCP readiness spec incomplete')
    require(type(spec['privateBaseline']) is dict and spec['privateBaseline'].get('sha256')==PRIVATE_GCP_BASELINE_SHA256,'Original successful image3 private baseline SHA required')
    baseline=file_record(spec['privateBaseline'])
    require(baseline.get('stateSHA256')=='8fceea80600b2b02caea3402951d8f7954c975845b3503522be69b69f2881358'
      and type(baseline.get('serial')) is int and baseline['serial']==21 and type(baseline.get('managedResources')) is int and baseline['managedResources']==13,'Original successful13-resource baseline differs')
    raw=file_record(spec['observation']);fund=file_record(spec['funding']);billing=file_record(spec['billing'])
    require(set(raw)=={'recordType','observedAtUtc','project','readerHelperSHA256','run','identity','policies','runtimeAccountPolicy'},'Fresh raw GCP observation schema differs')
    require(raw['recordType']=='controller-readonly-gcp-observation-v1' and raw['project']==PROJECT
      and type(raw['readerHelperSHA256']) is str and re.fullmatch('[0-9a-f]{64}',raw['readerHelperSHA256']),'GCP observation identity/reader differs')
    observed=stamp(raw['observedAtUtc']);require(0<=(now-observed).total_seconds()<=3600,'GCP metadata stale/future')
    # Service-local IAM alone cannot exclude an inherited public invoker or a
    # newly privileged runtime SA. Preserve every captured project/repository/
    # ancestor/identity field from the REAL successful baseline, without edge
    # sorting, redaction, fabricated baseline or generic IAM normalization.
    require(type(baseline.get('iamAfter')) is dict and baseline['iamAfter']
      and exact(raw['policies'],baseline['iamAfter']) and exact(raw['identity'],baseline['identityAfter'])
      and exact(raw['run'],baseline['run']),'Full private Run/identity/project/ancestor baseline changed')
    require(type(raw['runtimeAccountPolicy']) is dict,'Runtime own IAM response must be an object')
    own_bindings=raw['runtimeAccountPolicy'].get('bindings',[])
    require(type(own_bindings) is list and own_bindings==[],'Runtime service account acquired or returned malformed own IAM bindings')
    run=raw['run'];service=run.get('service',{});revision=run.get('revision',{})
    metadata=service.get('metadata',{});status=service.get('status',{});ann=metadata.get('annotations',{})
    require(service.get('apiVersion')=='serving.knative.dev/v1' and service.get('kind')=='Service'
      and metadata.get('name')=='ecoguard-inference' and str(metadata.get('namespace'))==NUMBER
      and metadata.get('uid')==spec['serviceUID'] and metadata.get('labels',{}).get('cloud.googleapis.com/location')==GCP_REGION,'Raw Run identity differs')
    require(type(spec['readyRevision']) is str and re.fullmatch(r'ecoguard-inference-[0-9]{5}-[a-z0-9]+',spec['readyRevision'])
      and type(spec['serviceUID']) is str and bool(spec['serviceUID']), 'Ready revision/service UID pending')
    require(type(spec['imageURI']) is str and re.fullmatch(r'us-central1-docker[.]pkg[.]dev/'+PROJECT+r'/[^@]+@sha256:[0-9a-f]{64}',spec['imageURI'])
      and run.get('url')==RUN and run.get('readyRevision')==spec['readyRevision'],'Ready Run URL/image/revision pending')
    require(ann.get('run.googleapis.com/invoker-iam-disabled','false')=='false'
      and ann.get('run.googleapis.com/maxScale')=='1' and ann.get('run.googleapis.com/minScale','0')=='0'
      and ann.get('run.googleapis.com/scalingMode','automatic')=='automatic' and ann.get('run.googleapis.com/manualInstanceCount','0')=='0','Run auth/scaling differs')
    template=service.get('spec',{}).get('template',{});ra=template.get('metadata',{}).get('annotations',{})
    require(ra.get('autoscaling.knative.dev/maxScale')=='1' and ra.get('autoscaling.knative.dev/minScale','0')=='0','Revision max/min differs')
    for cfg in (template.get('spec',{}),revision.get('spec',{})):
        containers=cfg.get('containers',[])
        require(cfg.get('serviceAccountName')==RUNTIME and type(cfg.get('containerConcurrency')) is int and cfg['containerConcurrency']==1
          and cfg.get('timeoutSeconds')==360 and len(containers)==1 and containers[0].get('image')==spec['imageURI'],'Run template/revision runtime differs')
        c=containers[0];env=c.get('env',[])
        require(not c.get('command') and not c.get('args') and not cfg.get('volumes') and not c.get('volumeMounts')
          and c.get('resources',{}).get('limits',{}).get('cpu') in ('4','4000m') and c.get('resources',{}).get('limits',{}).get('memory') in ('8Gi','8192Mi')
          and type(env) is list and len(env)==len(RUNTIME_ENV) and all(type(x) is dict and set(x)=={'name','value'} and type(x['name']) is str and type(x['value']) is str for x in env)
          and {x['name']:x['value'] for x in env}==RUNTIME_ENV,'Run capacity/auth/environment configuration differs')
    require(status.get('latestReadyRevisionName')==status.get('latestCreatedRevisionName')==spec['readyRevision']
      and str(status.get('observedGeneration'))==str(metadata.get('generation')) and any(x.get('type')=='Ready' and x.get('status')=='True' for x in status.get('conditions',[]))
      and revision.get('status',{}).get('imageDigest') in (spec['imageURI'],spec['imageURI'].split('@',1)[1])
      and revision.get('metadata',{}).get('name')==spec['readyRevision'] and any(x.get('type')=='Ready' and x.get('status')=='True' for x in revision.get('status',{}).get('conditions',[])),'Run not exact ready revision')
    traffic=status.get('traffic',[])
    require(len(traffic)==1 and traffic[0].get('percent')==100 and traffic[0].get('revisionName')==spec['readyRevision'] and not traffic[0].get('tag')
      and sole_binding(run.get('servicePolicy',{}),'roles/run.invoker','serviceAccount:'+INVOKER),'Run traffic/sole invoker differs')
    identity=raw['identity'];pool=identity.get('pool',{});provider=identity.get('provider',{})
    require(pool.get('name')==POOL and pool.get('state')=='ACTIVE' and pool.get('disabled',False) is False
      and provider.get('name')==POOL+'/providers/aws-role' and provider.get('state')=='ACTIVE' and provider.get('disabled',False) is False
      and provider.get('aws')=={'accountId':ACCOUNT} and provider.get('attributeMapping')==MAPPING
      and provider.get('attributeCondition')=="assertion.account == '"+ACCOUNT+"' && attribute.aws_role == '"+AWS_ROLE+"'"
      and not provider.get('oidc') and not provider.get('saml') and sole_binding(identity.get('grant',{}),'roles/iam.workloadIdentityUser',PRINCIPAL)
      and type(identity.get('userManagedKeyCount')) is int and identity['userManagedKeyCount']==0,'Real role WIF identity differs')
    required={'project':PROJECT,'billingAccountMatched':True,'eligibleExistingCreditsPositive':True,'currencyVerified':False,
      'expiresDate':'2026-10-28','additionalOutOfPocketLimitAUD':0,'standingAuthorization':'user requested finish member C and default agree within existing credits; no IAM/capacity change','source':'official Google Cloud Credits UI'}
    require(set(fund)==set(required)|{'observedAtUtc'} and all(type(fund.get(k)) is type(v) and fund[k]==v for k,v in required.items()),'Fresh official GCP credits record differs')
    ftime=stamp(fund['observedAtUtc']);require(0<=(now-ftime).total_seconds()<=3600,'GCP funding stale/future')
    require(billing.get('projectId')==PROJECT and billing.get('billingEnabled') is True and type(billing.get('billingAccountName')) is str
      and re.fullmatch('billingAccounts/[A-F0-9-]+',billing['billingAccountName']),'GCP billing link differs')
    until=required_until or now+timedelta(seconds=context['windowSeconds']+max(context['actualFunctionTimeouts'].values())+context['propagationReadAllowanceSeconds'])
    require(now<=until<=min(observed,ftime)+timedelta(seconds=3600)
      and until.date()<=datetime.fromisoformat(fund['expiresDate']).date(),'GCP freshness cannot cover active and independent drain windows')
    return True


def verified_head_json_absence(returncode,stdout,stderr):
    """Only the fixed HeadObject service error; never infer absence from exit254."""
    if type(returncode) is not int or returncode!=254 or type(stdout) is not bytes or stdout!=b'':
        return False,'head-error-exit-or-stdout-mismatch'
    if type(stderr) is not bytes or not 0<len(stderr)<=16384:
        return False,'head-error-body-type-or-bound'
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate error JSON key')
            result[key]=value
        return result
    def reject_constant(value):raise ValueError('Nonfinite error JSON value')
    try:
        error=json.loads(stderr.decode('utf-8'),object_pairs_hook=unique,parse_constant=reject_constant)
    except (ValueError,UnicodeError):
        return False,'head-error-not-strict-json'
    if type(error) is not dict or set(error)!={'Code','Message'} or type(error['Code']) is not str or type(error['Message']) is not str:
        return False,'head-error-schema-mismatch'
    if error!={'Code':'404','Message':'Not Found'}:
        return False,'head-service-error-not-absence'
    return True,'head-json-404-verified'


class FixtureTransport:
    """Callable for the frozen helper Request, with fixed AWS CLI commands only."""
    def __init__(self,helper,core,context,armed,store,proc,tool,env,*,role,before_external_write,freshness_guard,
                 run=subprocess.run,monotonic=time.monotonic,utc_now=lambda:datetime.now(timezone.utc),self_pid=None):
        require(role in ('writer','watchdog'),'Owned role required')
        self.h=helper;self.c=core;self.ctx=context;self.arm=armed;self.store=store;self.proc=proc;self.tool=tool;self.env=dict(env)
        self.role=role;self.before=before_external_write;self.fresh=freshness_guard;self.run=run;self.now=monotonic;self.utc=utc_now;self.pid=os.getpid() if self_pid is None else self_pid
        require(self.env.get('AWS_MAX_ATTEMPTS')=='1' and self.env.get('AWS_REGION')==self.env.get('AWS_DEFAULT_REGION')==REGION
          and self.env.get('AWS_IGNORE_CONFIGURED_ENDPOINT_URLS')=='true' and self.env.get('AWS_CONFIG_FILE')==self.env.get('AWS_SHARED_CREDENTIALS_FILE')=='/dev/null'
          and not any(v and (k.startswith('AWS_ENDPOINT_URL') or k in {'AWS_PROFILE','AWS_DEFAULT_PROFILE','AWS_CA_BUNDLE','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'}) for k,v in self.env.items()),'CLI reviewed environment/retry guard differs')

    def owned(self):
        require(self.c.digest(self.ctx)==self.arm['contextSHA256']==self.store.context_sha and self.ctx['nonce']==self.store.nonce==self.arm['nonce'],'Immutable fixture context changed')
        full=self.store.identity(self.role)
        require(full['pid']==self.pid and self.c.same(self.proc.identity(self.pid,self.arm['nonce']),full),'Only registered live owned process may use fixture port')
        return full

    def allowed(self,request):
        h,ctx=self.h,self.ctx;f=ctx['fixture'];p=request.params;service,op=request.service,request.operation
        require(type(p) is dict and type(request.max_response_bytes) is int and 0<request.max_response_bytes<=2*1024**2,'Request/response bound differs')
        if service=='dynamodb' and op=='TransactWriteItems':
            require(h.exact(request.params,h.seed_request(f).params) and request.body is None,'Only exact3 seed rows permitted');return 'seed'
        if service=='s3' and op=='PutObject':
            require(h.exact(p,h.source_params(f)) and type(request.body) is bytes and len(request.body)==h.SAMPLE_BYTES
              and hashlib.sha256(request.body).hexdigest()==h.SAMPLE_SHA,'Only exact conditional source bytes permitted');return 'source-put'
        if service=='dynamodb' and op=='Scan':
            require(p in [{'TableName':v,'ConsistentRead':True,'Limit':100} for v in h.TABLES.values()] and request.body is None,'Only fixed project scan permitted');return None
        if service=='sqs' and op=='GetQueueAttributes':
            require(p in [{'QueueUrl':f'https://sqs.{REGION}.amazonaws.com/{ACCOUNT}/{PREFIX}-{n}{s}','AttributeNames':['QueueArn','ApproximateNumberOfMessages','ApproximateNumberOfMessagesNotVisible','ApproximateNumberOfMessagesDelayed']} for n in ('ingest','infer','delete','notify') for s in ('','-dlq')],'Queue scope differs');return None
        if service=='dynamodb' and op=='GetItem':
            require(set(p)=={'TableName','Key','ConsistentRead'} and p['ConsistentRead'] is True,'GetItem options differ')
            table=next((k for k,v in h.TABLES.items() if v==p['TableName']),None);key={k:h.unwire(v) for k,v in p['Key'].items()}
            if table=='media':ok=key=={'mediaId':f['mediaId']}
            elif table=='operations':
                value=key.get('operationId');ok=set(key)=={'operationId'} and type(value) is str and (value in (f['jobId'],'DEDUP#'+f['ownerSub']+'#'+h.SAMPLE_SHA) or re.fullmatch('ARTIFACTS#'+f['jobId']+'#1#[1-9][0-9]*',value))
            elif table=='outbox':
                value=key.get('eventId');ok=set(key)=={'eventId'} and type(value) is str and (value in ('INGEST:'+f['jobId']+':1','NOTIFY:'+f['mediaId']+':2') or re.fullmatch('INFER:'+f['jobId']+':1:[1-9][0-9]*',value))
            elif table=='search':ok=key=={'scopeSpecies':'USER#'+f['ownerSub']+'#_all','observedAtMediaId':f['createdAtUtc']+'#'+f['mediaId']}
            else:ok=False
            require(ok,'GetItem key escapes fixture');return None
        if service=='s3' and op in ('HeadObject','GetObject'):
            require(set(p)==({'Bucket','Key','ExpectedBucketOwner','ChecksumMode'} if op=='HeadObject' else {'Bucket','Key','ExpectedBucketOwner'})
              and p.get('Bucket')==h.BUCKET and p.get('ExpectedBucketOwner')==ACCOUNT and (op!='HeadObject' or p['ChecksumMode']=='ENABLED'),'Object scope/owner differs')
            key=p.get('Key','');prefix='derived/'+f['mediaId']+'/1/'
            features=re.fullmatch(re.escape(prefix)+r'inference-[1-9][0-9]*/features[.]json',key)
            visible=(key=='incoming/library/'+f['jobId'] or re.fullmatch(re.escape(prefix)+r'[1-9][0-9]*/(?:frame-0[.]jpg|thumbnail[.]jpg)',key)
              or re.fullmatch(r'library/(?:pet|invasive|mixed|uncertain)/'+f['ownerSub']+'/'+f['mediaId']+r'/1/[1-9][0-9]*/original',key))
            require(bool(features) if op=='GetObject' else bool(visible),'Object key escapes fixture');return None
        raise ValueError('Request outside fixed fixture port')

    def __call__(self,request):
        self.owned();phase=self.allowed(request);fingerprint=request.fingerprint()
        if phase:
            require(self.role=='writer' and self.fresh() is True,'Only owned writer with fresh GCP proof may write')
            require(fingerprint==self.ctx['fixtureRequestSHA256'][phase],'Write fingerprint changed')
            self.before(phase,fingerprint)
            require(stamp(self.ctx['fixture']['createdAtUtc'])<=self.utc()<stamp(self.ctx['fixture']['createdAtUtc'])+timedelta(seconds=600),'Fixture upload window expired/future; do not write')
            if phase=='source-put':
                require(self.store.read_singleton('fixture-seed-confirmed.json')=={'requestSHA256':self.ctx['fixtureRequestSHA256']['seed'],'contextSHA256':self.arm['contextSHA256']},'Seed transaction not durably confirmed; no source put')
            intent='fixture:'+phase;record=self.store.read_json('intent-'+hashlib.sha256(intent.encode()).hexdigest()+'.json')
            require(record=={'action':intent,'requestSHA256':fingerprint},'Exact durable controller permit missing')
            require(self.store.mark_once('external-call:fixture:'+phase,self.arm['contextSHA256'],self.arm['nonce'],fingerprint),'Fixture external call consumed; never resubmit')
        elif self.role=='writer':
            require(self.store.input_is_open() and self.store.read_stop() is None,'Writer input closed; no new fixture reads')
        else:
            require(request.service in ('dynamodb','sqs') and self.store.read_stop() is not None,'Watchdog drain can only read project DynamoDB/queue state after STOP')
        require(sha(self.tool['path'])==self.tool['sha256'],'Frozen CLI changed')
        deadline=min(self.arm['stopNewWorkBy'] if self.role=='writer' else self.now()+self.ctx['callTimeoutSeconds'],self.now()+self.ctx['callTimeoutSeconds'])
        remaining=deadline-self.now();require(remaining>0,'Fixture call deadline exhausted')
        params=dict(request.params);service='s3api' if request.service=='s3' else request.service
        operation={'TransactWriteItems':'transact-write-items','PutObject':'put-object','GetItem':'get-item','Scan':'scan','GetQueueAttributes':'get-queue-attributes','HeadObject':'head-object','GetObject':'get-object'}[request.operation]
        outfile=None
        if request.operation=='GetObject':params['Range']='bytes=0-'+str(request.max_response_bytes)
        argv=[self.tool['path'],service,operation,'--cli-input-json',json.dumps(params,separators=(',',':'),allow_nan=False),
          '--region',REGION,'--output','json','--no-cli-pager','--no-cli-auto-prompt','--no-paginate',
          '--cli-connect-timeout',str(max(1,math.ceil(remaining))),'--cli-read-timeout',str(max(1,math.ceil(remaining)))]
        if request.operation=='HeadObject':argv+=['--cli-error-format','json']
        if phase=='source-put':
            sample=Path(self.ctx['samplePath'])
            require(sample.is_file() and not any(p.is_symlink() for p in (sample,*sample.parents)) and sha(sample)==self.h.SAMPLE_SHA,'Frozen fixture file changed')
            argv+=['--body',str(sample)]
        if request.operation=='GetObject':
            outfile=self.store.path/('fixture-response-'+uuid.uuid4().hex+'.bin')
            fd=os.open(outfile,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);os.close(fd);argv.append(str(outfile))
        outcome={'service':service,'operation':operation,'requestSHA256':fingerprint,'phase':phase,'startedMonotonic':self.now(),'outerCallMaximum':1,'AWS_MAX_ATTEMPTS':1,'automaticRetry':False}
        result=None;diagnostic='fixture-command-did-not-return'
        try:
            result=self.run(argv,env=self.env,stdin=subprocess.DEVNULL,capture_output=True,timeout=remaining,shell=False)
            outcome['exitCode']=result.returncode
            diagnostic='fixture-success-response-unverified'
            if result.returncode:
                diagnostic='fixture-command-nonzero-exit'
                exact404=False
                if request.operation=='HeadObject':
                    exact404,diagnostic=verified_head_json_absence(result.returncode,result.stdout,result.stderr)
                if exact404:data={'exists':False,'verifiedHTTPStatus':404}
                else:raise ValueError('Unverified fixture command failure; no retry')
            else:
                require(len(result.stdout)<=request.max_response_bytes,'Fixture metadata output bound exceeded')
                data=json.loads(result.stdout) if result.stdout.strip() else {};require(type(data) is dict,'Fixture response object required')
                if request.operation=='HeadObject':data={'exists':True,**data}
                if outfile:
                    require(outfile.is_file() and not outfile.is_symlink() and outfile.stat().st_size<=request.max_response_bytes,'Feature object body bound exceeded')
                    if data.get('ContentRange'):
                        match=re.fullmatch(r'bytes 0-[0-9]+/([0-9]+)',data['ContentRange']);require(match and int(match[1])<=request.max_response_bytes,'Partial oversized feature body rejected')
                    data['body']=outfile.read_bytes()
            outcome['responseSHA256']=hashlib.sha256(json.dumps({k:v for k,v in data.items() if k!='body'},sort_keys=True,separators=(',',':')).encode()).hexdigest()
            if 'body' in data:outcome['bodySHA256']=hashlib.sha256(data['body']).hexdigest();outcome['bodyPrivatePath']=str(outfile)
            if phase:
                marker='fixture-'+('seed' if phase=='seed' else 'source-put')+'-confirmed.json'
                require(self.store.write_once(marker,{'requestSHA256':fingerprint,'contextSHA256':self.arm['contextSHA256']}),'Write success confirmation already exists; never resubmit')
            answer={'ok':True,'data':data}
        except Exception as error:
            outcome['category']='uncertain-or-unverified-fixture-call';outcome['errorType']=type(error).__name__
            outcome['diagnosticCategory']=diagnostic
            for channel in ('stdout','stderr'):
                body=getattr(result,channel,None)
                outcome[channel+'Bytes']=len(body) if type(body) is bytes else None
                outcome[channel+'SHA256']=hashlib.sha256(body).hexdigest() if type(body) is bytes else None
            answer={'ok':False,'category':outcome['category']}
        outcome['endedMonotonic']=self.now();self.store.append_json('fixture-outcome',outcome)
        return answer
