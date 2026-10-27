"""Fixed project-only AWS metadata/reduction port. Import does not execute commands.

All real calls require a separately pinned binding. This module neither discovers
credentials nor accepts service names/argv from a caller. Raw stdout is private;
stderr is never printed or persisted. It does not submit a fixture or invoke an app.
"""
from __future__ import annotations
import concurrent.futures
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import time

ACCOUNT = '011154879765'
REGION = 'us-east-1'
PREFIX = 'ecoguard3184-personal'
BUCKET = PREFIX + '-' + ACCOUNT + '-media'
ROLE = PREFIX + '-lambda'
ROLE_ARN = 'arn:aws:iam::' + ACCOUNT + ':role/' + ROLE
FUNCTIONS = ('api', 'ingest', 'infer', 'delete', 'notify', 'outbox', 'cleanup', 'lex_fulfillment')
OTHER_FUNCTIONS = ('api', 'delete', 'notify', 'cleanup', 'lex_fulfillment')
READS = frozenset({
 ('sts','get-caller-identity'),('lambda','get-account-settings'), ('events','describe-rule'), ('events','list-targets-by-rule'),
 ('lambda','get-function-configuration'), ('lambda','get-function-concurrency'),
 ('lambda','get-function'), ('lambda','get-event-source-mapping'), ('lambda','get-policy'),
 ('s3api','get-bucket-policy'), ('s3api','get-bucket-notification-configuration'),
 ('s3api','get-public-access-block'), ('s3api','get-bucket-ownership-controls'),
 ('s3api','get-bucket-encryption'), ('s3api','get-bucket-policy-status'), ('s3api','get-bucket-cors'),
 ('iam','get-role'), ('iam','list-attached-role-policies'), ('iam','list-role-policies'), ('iam','get-role-policy'),
 ('ecr','get-repository-policy'), ('apigatewayv2','get-api'), ('apigatewayv2','get-stage'),
 ('cognito-idp','describe-user-pool'),('dynamodb','scan'),('sqs','get-queue-attributes')})
MUTATIONS = frozenset({('events','disable-rule'), ('s3api','put-bucket-notification-configuration'),
 ('s3api','put-bucket-policy'), ('lambda','update-event-source-mapping'), ('lambda','put-function-concurrency')})
# Lambda GetFunction otherwise emits a bearer-like presigned download Location.
# This fixed projection retains the authoritative image URI and full configuration
# while ensuring that download URL never leaves the CLI process.
IMAGE_QUERY = '{Configuration:Configuration,Code:{ResolvedImageUri:Code.ResolvedImageUri,ImageUri:Code.ImageUri},Tags:Tags}'
BLOCKED_ENV = {'AWS_PROFILE','AWS_DEFAULT_PROFILE','AWS_CONFIG_FILE','AWS_SHARED_CREDENTIALS_FILE',
 'AWS_ROLE_ARN','AWS_ROLE_SESSION_NAME','AWS_WEB_IDENTITY_TOKEN_FILE','AWS_CA_BUNDLE','AWS_DATA_PATH',
 'AWS_ENDPOINT_DISCOVERY_ENABLED','AWS_ACCOUNT_ID','AWS_ACCOUNT_ID_ENDPOINT_MODE',
 'HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy',
 'CURL_CA_BUNDLE','REQUESTS_CA_BUNDLE','SSL_CERT_FILE','SSL_CERT_DIR','BOTO_CONFIG',
 'PYTHONPATH','PYTHONHOME','LD_PRELOAD','LD_LIBRARY_PATH','DYLD_INSERT_LIBRARIES','DYLD_LIBRARY_PATH'}
# Only credential material already supplied to this process by CloudShell may
# transit unchanged in memory to the pinned CLI. Nothing reads ~/.aws or exports it.
CREDENTIAL_ROUTE_GUARD_SHA256 = 'c742bd1cb2a2cc28989fcc606c540c6a8bd0e2cce574678c95cc1f675e094d35'
CREDENTIAL_ENV = {'AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY','AWS_SESSION_TOKEN','AWS_SECURITY_TOKEN',
 'AWS_CONTAINER_CREDENTIALS_RELATIVE_URI','AWS_CONTAINER_CREDENTIALS_FULL_URI',
 'AWS_CONTAINER_AUTHORIZATION_TOKEN','AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def regular(path, expected, *, private=False):
    path=Path(path)
    require(path.is_absolute() and not any(x.is_symlink() for x in (path,*path.parents)), 'Unreviewed file path/link')
    st=path.stat()
    require(stat.S_ISREG(st.st_mode) and st.st_uid in (0,os.getuid()), 'Unreviewed file type/owner')
    require(not st.st_mode & 0o022, 'Group/world writable file')
    if private: require(st.st_uid==os.getuid() and not st.st_mode & 0o077, 'Private file owner/permissions differ')
    require(isinstance(expected,str) and re.fullmatch('[0-9a-f]{64}',expected) and file_sha(path)==expected,'File SHA differs')
    return path


def credential_guard():
    path=Path(__file__).with_name('credential_route.py')
    regular(path,CREDENTIAL_ROUTE_GUARD_SHA256)
    spec=importlib.util.spec_from_file_location('pinned_cloudshell_route_guard',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def reviewed_environment(ambient, *, home='/home/cloudshell-user', credential_route=None):
    fixed_child_guards={'AWS_CONFIG_FILE':'/dev/null','AWS_SHARED_CREDENTIALS_FILE':'/dev/null','BOTO_CONFIG':'/dev/null'}
    for key,value in ambient.items():
        if key in fixed_child_guards and value==fixed_child_guards[key]:continue
        require(not (value and (key in BLOCKED_ENV or key.startswith(('AWS_ENDPOINT_URL','TF_CLI_ARGS','TF_VAR_','GIT_CONFIG_')))), 'Unreviewed environment override')
    require(home=='/home/cloudshell-user', 'AWS CloudShell HOME differs')
    # Never let default shared files select credentials, endpoints, plugins,
    # credential_process, or a profile. Ambient AWS credentials remain memory-only.
    credentials=credential_guard().reviewed_credentials(dict(ambient),credential_route)
    result={'PATH':os.defpath,'HOME':home,'LANG':'C.UTF-8','LC_ALL':'C.UTF-8',
      'AWS_CONFIG_FILE':'/dev/null','AWS_SHARED_CREDENTIALS_FILE':'/dev/null',
      'BOTO_CONFIG':'/dev/null','AWS_REGION':REGION,'AWS_DEFAULT_REGION':REGION,
      'AWS_PAGER':'','AWS_CLI_AUTO_PROMPT':'off','AWS_IGNORE_CONFIGURED_ENDPOINT_URLS':'true',
      'AWS_MAX_ATTEMPTS':'1','AWS_RETRY_MODE':'standard','AWS_EC2_METADATA_DISABLED':'true',
      'PYTHONDONTWRITEBYTECODE':'1','PYTHONNOUSERSITE':'1'}
    # Selector and token transit only in memory to the official pinned CLI.
    result.update(credentials)
    return result


class CallFailure(RuntimeError):
    """Category only. Raw CLI stderr never propagates to a receipt or console."""


class FixedCLI:
    def __init__(self, tool, env, store, scope, *, credential_route=None, run=subprocess.run, monotonic=time.monotonic):
        self.tool=copy.deepcopy(tool);self.env=dict(env);self.store=store;self.scope=copy.deepcopy(scope);self.run=run;self.now=monotonic;self.identity_verified=False
        self.credential_route=copy.deepcopy(credential_route)
        self._initial_env=dict(env)  # memory-only; never serialized, hashed, or logged
        require(self.env==reviewed_environment(self.env,credential_route=self.credential_route),'CLI credential/environment isolation differs')
        regular(tool['path'],tool['sha256'])
        require(env.get('AWS_MAX_ATTEMPTS')=='1' and env.get('AWS_IGNORE_CONFIGURED_ENDPOINT_URLS')=='true', 'CLI retry/endpoint guard differs')

    def verify_identity(self,deadline):
        if not self.identity_verified:
            identity=self.call('sts','get-caller-identity',{},deadline)
            require(identity.get('Account')==ACCOUNT and identity.get('Arn')=='arn:aws:iam::'+ACCOUNT+':root', 'Fresh root identity differs')
            self.identity_verified=True

    def request_is_exact(self,service,operation,parameters,mutation):
        context,ids=self.scope['context'],self.scope['readonly']
        if mutation:
            catalog={
              ('events','disable-rule'): [('outbox-rule',{'Name':PREFIX+'-outbox','EventBusName':'default'})],
              ('s3api','put-bucket-notification-configuration'): [('bucket-notifications',{'Bucket':BUCKET,'ExpectedBucketOwner':ACCOUNT,'NotificationConfiguration':{}})],
              ('s3api','put-bucket-policy'): [('bucket-policy',{'Bucket':BUCKET,'ExpectedBucketOwner':ACCOUNT,'Policy':json.dumps(context['targets']['bucket-policy']['safeValue'],separators=(',',':'),allow_nan=False)})],
              ('lambda','update-event-source-mapping'): [(name+'-mapping',{'UUID':context['mappingUUIDs'][name],'Enabled':False}) for name in ('ingest','infer')],
              ('lambda','put-function-concurrency'): [(name+'-concurrency',{'FunctionName':f'arn:aws:lambda:{REGION}:{ACCOUNT}:function:{PREFIX}-{name}','ReservedConcurrentExecutions':0}) for name in ('ingest','infer','outbox')]}
            return any(digest(parameters)==digest(expected) and self.store.has_intent('external-call:'+target)
                for target,expected in catalog.get((service,operation),[]))
        if service=='dynamodb':
            return operation=='scan' and any(digest(parameters)==digest({'TableName':PREFIX+'-'+name,'ConsistentRead':True,'Select':'COUNT','Limit':100}) for name in ('media','operations','outbox','search','subscriptions'))
        if service=='sqs':
            return operation=='get-queue-attributes' and any(parameters=={'QueueUrl':f'https://sqs.{REGION}.amazonaws.com/{ACCOUNT}/{PREFIX}-{name}{suffix}',
                'AttributeNames':['QueueArn','ApproximateNumberOfMessages','ApproximateNumberOfMessagesNotVisible','ApproximateNumberOfMessagesDelayed']}
                for name in ('ingest','infer','delete','notify') for suffix in ('','-dlq'))
        if service=='sts': return operation=='get-caller-identity' and parameters=={}
        if service=='s3api': return (service,operation) in READS and parameters=={'Bucket':BUCKET,'ExpectedBucketOwner':ACCOUNT}
        if service=='iam':
            expected={'RoleName':ROLE}
            if operation=='get-role-policy': expected['PolicyName']=PREFIX+'-runtime'
            return (service,operation) in READS and parameters==expected
        if service=='ecr': return operation=='get-repository-policy' and parameters=={'RegistryId':ACCOUNT,'RepositoryName':PREFIX+'-worker'}
        if service=='apigatewayv2':
            expected={'ApiId':ids['apiId']}
            if operation=='get-stage': expected['StageName']='$default'
            return operation in ('get-api','get-stage') and parameters==expected
        if service=='cognito-idp': return operation=='describe-user-pool' and parameters=={'UserPoolId':ids['userPoolId']}
        if service=='events':
            key='Name' if operation=='describe-rule' else 'Rule'
            return operation in ('describe-rule','list-targets-by-rule') and any(parameters=={key:PREFIX+'-'+name,'EventBusName':'default'} for name in ('cleanup','outbox'))
        if service=='lambda':
            if operation=='get-account-settings':return parameters=={}
            if operation=='get-event-source-mapping':
                uuids=list(context['mappingUUIDs'].values())+[ids['deleteMappingUUID'],ids['notifyMappingUUID']]
                return parameters in [{'UUID':uuid} for uuid in uuids]
            names=('ingest',) if operation=='get-function' else ('api','cleanup','outbox') if operation=='get-policy' else FUNCTIONS
            return operation in ('get-function','get-function-configuration','get-function-concurrency','get-policy') and parameters in [{'FunctionName':PREFIX+'-'+name} for name in names]
        return False

    def call(self,service,operation,parameters,deadline,*,mutation=False,query=None):
        require((service,operation) in (MUTATIONS if mutation else READS),'Operation outside fixed port')
        require(not mutation or self.identity_verified, 'Exact fresh root identity not verified')
        require(query is None or (service,operation,query)==('lambda','get-function',IMAGE_QUERY),'Unreviewed CLI query')
        require(type(parameters) is dict and all(type(k) is str for k in parameters),'Malformed API parameters')
        require(self.request_is_exact(service,operation,parameters,mutation),'API selector/value outside exact project capability')
        remaining=deadline-self.now()
        require(math.isfinite(remaining) and 0<remaining<=10.01,'Expired/unbounded metadata call deadline')
        require(self.env==self._initial_env,'Memory-only CLI environment changed; no fallback')
        require(self.env==reviewed_environment(self.env,credential_route=self.credential_route),'CLI environment/route changed; no fallback')
        regular(self.tool['path'],self.tool['sha256'])
        remaining=deadline-self.now()
        require(0<remaining<=10.01,'File verification exhausted logical call deadline')
        # ECR's SDK/CLI input model uses lower-camel members. The canonical
        # request has already passed the exact capability check above; retain
        # it unchanged in intents/outcomes and translate only these wire keys.
        wire_parameters = ({'registryId': parameters['RegistryId'],
                            'repositoryName': parameters['RepositoryName']}
                           if (service,operation)==('ecr','get-repository-policy') else parameters)
        # Inputs are fixed by RawReader/reduction_intent, not exposed through a
        # public caller-controlled command-line interface. No shell or file://.
        argv=[self.tool['path'],service,operation,'--cli-input-json',json.dumps(wire_parameters,separators=(',',':'),allow_nan=False),
              '--region',REGION,'--output','json','--no-cli-pager','--no-cli-auto-prompt','--no-paginate',
              '--cli-connect-timeout',str(max(1,math.ceil(remaining))), '--cli-read-timeout',str(max(1,math.ceil(remaining)))]
        if query: argv += ['--query',query]
        request={'service':service,'operation':operation,'parameters':parameters,'query':query,'mutation':mutation}
        outcome={'request':request,'requestSHA256':digest(request),'startedMonotonic':self.now(),
                 'outerProcessMaximum':1,'AWS_MAX_ATTEMPTS':1}
        try:
            result=self.run(argv,env=self.env,stdin=subprocess.DEVNULL,capture_output=True,timeout=remaining,shell=False)
            outcome['exitCode']=result.returncode
            require(len(result.stdout)<=4*1024*1024, 'CLI stdout bound exceeded')
            if result.returncode:
                # No blanket NotFound->safe conversion. Every missing target,
                # 403, timeout, or error is unverified and will block success.
                raise CallFailure('aws-command-failed-no-retry')
            data=json.loads(result.stdout) if result.stdout.strip() else {}
            require(type(data) is dict, 'Metadata JSON must be object')
            outcome['response']=data
            outcome['responseSHA256']=digest(data)
        except Exception as error:
            outcome['category']='timeout-or-unverified-aws-failure' if not isinstance(error,CallFailure) else str(error)
            outcome['endedMonotonic']=self.now()
            self.store.append_json('aws-outcome',outcome)
            raise CallFailure(outcome['category']) from None
        outcome['endedMonotonic']=self.now()
        self.store.append_json('aws-outcome',outcome)
        return data


def quota_profile(raw):
    require(type(raw) is dict and type(raw.get('AccountLimit')) is dict and type(raw.get('AccountUsage')) is dict,'Quota metadata incomplete')
    values={key:raw['AccountLimit'].get(key) for key in ('ConcurrentExecutions','UnreservedConcurrentExecutions')}
    values['FunctionCount']=raw['AccountUsage'].get('FunctionCount')
    require(all(type(v) is int for v in values.values()) and values=={'ConcurrentExecutions':10,'UnreservedConcurrentExecutions':10,'FunctionCount':8},'Shared quota/functions differ; pause required')
    return values


def eligible_backlog(value):
    """Existing fixture helper's full-project read-only eligibility schema.

    SQS counters remain approximate. Empty scans are not a concurrent snapshot;
    this is used only while all project producers are freshly proved paused.
    """
    require(type(value) is dict and set(value)=={'complete','allFiveTablesAndEightQueuesObserved','freshProjectEligible','tables','queues','queueCountsAreApproximate'},'Backlog proof shape differs')
    require(all(value[k] is True for k in ('complete','allFiveTablesAndEightQueuesObserved','freshProjectEligible','queueCountsAreApproximate')),'Backlog not complete/eligible')
    require(set(value['tables'])=={'media','operations','search','subscriptions','outbox'} and set(value['queues'])=={n+s for n in ('ingest','infer','delete','notify') for s in ('','-dlq')},'Backlog project inventory differs')
    for table in value['tables'].values():
        require(type(table) is dict and set(table)=={'items','complete','observedItemsSHA256'} and type(table['items']) is int and table['items']==0
          and table['complete'] is True and table['observedItemsSHA256']==hashlib.sha256(b'[]').hexdigest(),'Table nonempty/incomplete')
    for queue in value['queues'].values():
        require(type(queue) is dict and set(queue)=={'ApproximateNumberOfMessages','ApproximateNumberOfMessagesNotVisible','ApproximateNumberOfMessagesDelayed'}
          and all(type(v) is int and v==0 for v in queue.values()),'Queue approximate backlog nonzero/untyped')
    return True


def immutable_function_profile(name, raw):
    """Project only the three owned concurrency controls' computed revision."""
    require(name in ('ingest','infer','outbox') and type(raw) is dict
      and type(raw.get('Configuration')) is dict,'Exact owned function profile required')
    cfg=raw['Configuration'];function=PREFIX+'-'+name
    require(cfg.get('FunctionName')==function
      and cfg.get('FunctionArn')==f'arn:aws:lambda:{REGION}:{ACCOUNT}:function:{function}'
      and type(cfg.get('RevisionId')) is str
      and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',cfg['RevisionId']),
      'Owned computed function RevisionId malformed')
    result=copy.deepcopy(raw)
    del result['Configuration']['RevisionId']
    return result


def notification_value(raw):
    """Bridge the sole observed S3 API Prefix spelling; preserve the raw input."""
    if type(raw) is dict and raw=={}:
        return {}
    expected={'QueueConfigurations':[{'Id':PREFIX+'-incoming-ingest',
      'QueueArn':f'arn:aws:sqs:{REGION}:{ACCOUNT}:{PREFIX}-ingest',
      'Events':['s3:ObjectCreated:*'],
      'Filter':{'Key':{'FilterRules':[{'Name':'Prefix','Value':'incoming/'}]}}}]}
    require(type(raw) is dict and raw==expected,'Exact sole owned API notification required')
    result=copy.deepcopy(raw)
    result['QueueConfigurations'][0]['Filter']['Key']['FilterRules'][0]['Name']='prefix'
    return result


class RawReader:
    """Exact, narrow representation bridge from full CLI JSON to core profiles.

    Each profile is hashed from retained raw metadata. Only mapping operational
    state/timestamp/status and its separately modelled ScalingConfig are removed.
    The three concurrency profiles use the exact computed RevisionId projection.
    No generic metadata stripping, no absent-resource acceptance, no sorting.
    """
    def __init__(self,cli,context,readonly,expected_boundaries,core,*,monotonic=time.monotonic):
        self.cli=cli;self.context=context;self.ids=readonly;self.expected=expected_boundaries;self.core=core;self.now=monotonic

    def call(self,service,operation,params,deadline,query=None):
        return self.cli.call(service,operation,params,deadline,query=query)

    def bucket_privacy(self,deadline,observed=None):
        params={'Bucket':BUCKET,'ExpectedBucketOwner':ACCOUNT}
        result={}
        commands={'publicAccess':'get-public-access-block','ownership':'get-bucket-ownership-controls',
          'encryption':'get-bucket-encryption','publicStatus':'get-bucket-policy-status','cors':'get-bucket-cors'}
        if observed is None:
            for key,op in commands.items(): result[key]=self.call('s3api',op,params,deadline)
        else:
            require(type(observed) is dict and set(observed)==set(commands),'Exact five privacy readings required')
            result=copy.deepcopy(observed)
        require(result['publicAccess'].get('PublicAccessBlockConfiguration')=={k:True for k in
          ('BlockPublicAcls','IgnorePublicAcls','BlockPublicPolicy','RestrictPublicBuckets')},'S3 public access differs')
        require(result['ownership'].get('OwnershipControls')=={'Rules':[{'ObjectOwnership':'BucketOwnerEnforced'}]},'S3 ownership differs')
        require(result['publicStatus'].get('PolicyStatus')=={'IsPublic':False},'S3 public policy detected')
        rules=result['encryption'].get('ServerSideEncryptionConfiguration',{}).get('Rules')
        require(type(rules) is list and len(rules)==1 and rules[0].get('ApplyServerSideEncryptionByDefault')=={'SSEAlgorithm':'AES256'},'S3 encryption differs')
        return result

    def function_configuration(self,name,deadline):
        require(name in FUNCTIONS,'Function outside project')
        function=PREFIX+'-'+name
        if name=='ingest':
            raw=self.call('lambda','get-function',{'FunctionName':function},deadline,IMAGE_QUERY)
            cfg=raw.get('Configuration',{})
            require(raw.get('Code',{}).get('ResolvedImageUri')==self.ids['workerImageUri'],'Ingest resolved image digest differs')
        else:
            cfg=self.call('lambda','get-function-configuration',{'FunctionName':function},deadline)
            raw={'Configuration':cfg}
        require(cfg.get('FunctionName')==function and cfg.get('FunctionArn')==f'arn:aws:lambda:{REGION}:{ACCOUNT}:function:{function}'
          and cfg.get('Role')==ROLE_ARN and cfg.get('State')=='Active' and cfg.get('LastUpdateStatus')=='Successful','Function identity/code readiness differs')
        if name in ('ingest','infer','outbox'):
            require(cfg.get('Timeout')=={'ingest':120,'infer':480,'outbox':60}[name],'Function timeout differs')
        return raw

    def observe(self,target,timeout_seconds):
        require(target in self.core.TARGETS and type(timeout_seconds) is int and 1<=timeout_seconds<=10,'Target/time bound differs')
        deadline=self.now()+timeout_seconds
        spec=self.context['targets'][target]
        if target=='outbox-rule':
            rule=self.call('events','describe-rule',{'Name':PREFIX+'-outbox','EventBusName':'default'},deadline)
            targets=self.call('events','list-targets-by-rule',{'Rule':PREFIX+'-outbox','EventBusName':'default'},deadline)
            require(not targets.get('NextToken') and type(targets.get('Targets')) is list and len(targets['Targets'])==1
              and targets['Targets'][0].get('Arn')==f'arn:aws:lambda:{REGION}:{ACCOUNT}:function:{PREFIX}-outbox','Rule target differs')
            require(rule.get('Name')==spec['identity']['Name'] and rule.get('Arn')==spec['identity']['Arn']
              and rule.get('EventBusName')=='default' and rule.get('ScheduleExpression')=='rate(1 minute)','Rule identity/schedule differs')
            value=rule.get('State'); profile={'rule':{k:v for k,v in rule.items() if k!='State'},'targets':targets}
        elif target.startswith('bucket-'):
            params={'Bucket':BUCKET,'ExpectedBucketOwner':ACCOUNT}
            commands={'publicAccess':'get-public-access-block','ownership':'get-bucket-ownership-controls',
              'encryption':'get-bucket-encryption','publicStatus':'get-bucket-policy-status','cors':'get-bucket-cors',
              'value':'get-bucket-policy' if target=='bucket-policy' else 'get-bucket-notification-configuration'}
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                futures={key:pool.submit(self.call,'s3api',operation,params,deadline) for key,operation in commands.items()}
                readings={key:future.result(timeout=max(.001,deadline-self.now())) for key,future in futures.items()}
            require(self.now()<=deadline,'Whole six-read bucket group exceeded target deadline')
            profile={'privacy':self.bucket_privacy(deadline,{key:readings[key] for key in commands if key!='value'})}
            if target=='bucket-policy':
                raw=readings['value']
                require(type(raw.get('Policy')) is str and set(raw)=={'Policy'},'Bucket policy envelope differs')
                value=json.loads(raw['Policy'])
            else:
                value=notification_value(readings['value'])
        elif target.endswith('-mapping'):
            name=target.split('-')[0]
            raw=self.call('lambda','get-event-source-mapping',{'UUID':self.context['mappingUUIDs'][name]},deadline)
            require(raw.get('UUID')==spec['identity']['UUID'] and raw.get('FunctionArn')==spec['identity']['FunctionArn']
              and raw.get('EventSourceArn')==spec['identity']['EventSourceArn'] and raw.get('BatchSize')==1
              and raw.get('FunctionResponseTypes')==['ReportBatchItemFailures'],'Mapping identity/batch differs')
            scaling=raw.get('ScalingConfig',{})
            require(scaling=={} or (type(scaling) is dict and set(scaling)=={'MaximumConcurrency'}
              and self.core.same(scaling['MaximumConcurrency'],2)),'Mapping scaling scope differs')
            value={'state':raw.get('State'),'maximumConcurrency':scaling.get('MaximumConcurrency')}
            excluded={'State','LastModified','StateTransitionReason','LastProcessingResult','ScalingConfig'}
            profile={k:v for k,v in raw.items() if k not in excluded}
        else:
            name=target.split('-')[0]
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                function=pool.submit(self.function_configuration,name,deadline)
                concurrency=pool.submit(self.call,'lambda','get-function-concurrency',{'FunctionName':PREFIX+'-'+name},deadline)
                raw=function.result(timeout=max(.001,deadline-self.now()))
                result=concurrency.result(timeout=max(.001,deadline-self.now()))
            require(self.now()<=deadline,'Whole two-read function group exceeded target deadline')
            profile=immutable_function_profile(name,raw)
            require(result=={} or (set(result)=={'ReservedConcurrentExecutions'} and type(result['ReservedConcurrentExecutions']) is int and result['ReservedConcurrentExecutions']==0),'Only exact unreserved{} or paused0 is reviewed')
            value=result.get('ReservedConcurrentExecutions')
        observation={'identity':copy.deepcopy(spec['identity']),'immutableProfileSHA256':digest(profile),'value':value}
        self.core.observation_state(self.context,target,observation)
        require(self.now()<=deadline,'Whole control read and projection exceeded target deadline')
        return observation

    def boundary_jobs(self):
        # All selectors come from literal scope or exact pinned AWS IDs.
        api=self.ids['apiId']; pool=self.ids['userPoolId']
        require(re.fullmatch('[a-z0-9]+',api or '') and re.fullmatch(REGION+r'_[A-Za-z0-9]+',pool or ''),'API/pool IDs pending')
        jobs={'quota':('lambda','get-account-settings',{}),'identity':('sts','get-caller-identity',{}),
          'role':('iam','get-role',{'RoleName':ROLE}),
          'attached':('iam','list-attached-role-policies',{'RoleName':ROLE}),
          'inlineNames':('iam','list-role-policies',{'RoleName':ROLE}),
          'runtimePolicy':('iam','get-role-policy',{'RoleName':ROLE,'PolicyName':PREFIX+'-runtime'}),
          'ecrPolicy':('ecr','get-repository-policy',{'RegistryId':ACCOUNT,'RepositoryName':PREFIX+'-worker'}),
          'api':('apigatewayv2','get-api',{'ApiId':api}),
          'stage':('apigatewayv2','get-stage',{'ApiId':api,'StageName':'$default'}),
          'signup':('cognito-idp','describe-user-pool',{'UserPoolId':pool}),
          'cleanupRule':('events','describe-rule',{'Name':PREFIX+'-cleanup','EventBusName':'default'}),
          'cleanupTargets':('events','list-targets-by-rule',{'Rule':PREFIX+'-cleanup','EventBusName':'default'})}
        for name in OTHER_FUNCTIONS:
            jobs['function:'+name]=('lambda','get-function-configuration',{'FunctionName':PREFIX+'-'+name})
            jobs['concurrency:'+name]=('lambda','get-function-concurrency',{'FunctionName':PREFIX+'-'+name})
        for name in ('api','cleanup','outbox'):
            jobs['lambdaPolicy:'+name]=('lambda','get-policy',{'FunctionName':PREFIX+'-'+name})
        for name in ('delete','notify'):
            uuid=self.ids[name+'MappingUUID']
            require(re.fullmatch(r'[0-9a-f-]{36}',uuid or ''),'Other disabled mapping UUID pending')
            jobs['mapping:'+name]=('lambda','get-event-source-mapping',{'UUID':uuid})
        return jobs

    def batch(self,jobs,deadline,kind):
        # Original CLI behavior is the default; the SDK subclass replaces only
        # the two complete read groups, never observe()/mutation operations.
        require(kind in ('boundary','backlog'),'Unknown raw read group')
        with concurrent.futures.ThreadPoolExecutor(max_workers=16 if kind=='boundary' else 13) as executor:
            futures={name:executor.submit(self.call,*args,deadline) for name,args in jobs.items()}
            return {name:f.result(timeout=max(.001,deadline-self.now())) for name,f in futures.items()}

    def verify_empty_backlog(self,timeout_seconds):
        """Fresh bounded fixed reads immediately before activation; no receives.

        COUNT avoids persisting unrelated item content. --no-paginate plus exact
        Count/ScannedCount0 and absent continuation is required; an incomplete or
        nonempty response stops before any activation, not an extra scan/retry.
        """
        deadline=self.now()+timeout_seconds; jobs={}
        for name in ('media','operations','outbox','search','subscriptions'):
            jobs['table:'+name]=('dynamodb','scan',{'TableName':PREFIX+'-'+name,'ConsistentRead':True,'Select':'COUNT','Limit':100})
        for name in ('ingest','infer','delete','notify'):
            for suffix in ('','-dlq'):
                queue=name+suffix
                jobs['queue:'+queue]=('sqs','get-queue-attributes',{'QueueUrl':f'https://sqs.{REGION}.amazonaws.com/{ACCOUNT}/{PREFIX}-{queue}',
                  'AttributeNames':['QueueArn','ApproximateNumberOfMessages','ApproximateNumberOfMessagesNotVisible','ApproximateNumberOfMessagesDelayed']})
        raw=self.batch(jobs,deadline,'backlog')
        tables,queues={},{}
        for key,value in raw.items():
            kind,name=key.split(':',1)
            if kind=='table':
                require(type(value.get('Count')) is int and value['Count']==0 and type(value.get('ScannedCount')) is int
                  and value['ScannedCount']==0 and not value.get('LastEvaluatedKey') and not value.get('NextToken')
                  and not value.get('Items'),'Nonempty/incomplete table scan')
                tables[name]={'items':0,'complete':True,'observedItemsSHA256':hashlib.sha256(b'[]').hexdigest()}
            else:
                attrs=value.get('Attributes',{}); expected_arn=f'arn:aws:sqs:{REGION}:{ACCOUNT}:{PREFIX}-{name}'
                require(attrs.get('QueueArn')==expected_arn,'Queue identity differs')
                counts={k:attrs.get(k) for k in ('ApproximateNumberOfMessages','ApproximateNumberOfMessagesNotVisible','ApproximateNumberOfMessagesDelayed')}
                require(all(type(v) is str and v=='0' for v in counts.values()),'Queue backlog unknown/nonzero')
                queues[name]={k:0 for k in counts}
        result={'complete':True,'allFiveTablesAndEightQueuesObserved':True,'freshProjectEligible':True,'tables':tables,'queues':queues,'queueCountsAreApproximate':True}
        eligible_backlog(result)
        return result

    def unchanged_boundaries(self,timeout_seconds):
        deadline=self.now()+timeout_seconds
        jobs=self.boundary_jobs(); raw={}
        raw=self.batch(jobs,deadline,'boundary')
        # RoleLastUsed is one explicitly reviewed usage timestamp, changed by
        # this very workload; it cannot hide role/trust/policy configuration.
        raw['role'].get('Role',{}).pop('RoleLastUsed',None)
        # JSON-string policies are decoded, without changing fields/list order.
        for name,key in (('runtimePolicy','PolicyDocument'),('ecrPolicy','policyText')):
            if type(raw[name].get(key)) is str: raw[name][key]=json.loads(raw[name][key])
        for name in ('api','cleanup','outbox'):
            row=raw['lambdaPolicy:'+name]
            if type(row.get('Policy')) is str: row['Policy']=json.loads(row['Policy'])
        quota_profile(raw['quota'])
        require(raw['attached'].get('AttachedPolicies')==[] and not raw['attached'].get('IsTruncated')
          and raw['inlineNames'].get('PolicyNames')==[PREFIX+'-runtime'] and not raw['inlineNames'].get('IsTruncated'),'Unexpected project role policies/pagination')
        require(raw['identity'].get('Account')==ACCOUNT and raw['identity'].get('Arn')=='arn:aws:iam::'+ACCOUNT+':root','Root account differs')
        for name in OTHER_FUNCTIONS:
            require(raw['concurrency:'+name]=={'ReservedConcurrentExecutions':0},'Other function enabled')
        require(raw['api'].get('DisableExecuteApiEndpoint') is True and raw['signup'].get('UserPool',{}).get('AdminCreateUserConfig',{}).get('AllowAdminCreateUserOnly') is True
          and raw['cleanupRule'].get('State')=='DISABLED','Other runtime boundary enabled')
        for name in ('delete','notify'):
            require(raw['mapping:'+name].get('State')=='Disabled','Other consumer enabled')
        require(self.core.same(raw,self.expected),'Project IAM or unchanged controls differ from pinned raw baseline')
        # Privacy is separately fresh per both bucket target/final reads. The full
        # raw baseline above is retained without broad read-only metadata removal.
        return copy.deepcopy(self.context['pausedBoundaries'])


class RuntimeAdapter:
    """Existing core RuntimePort; no mutation beyond its eight reduction intents."""
    def __init__(self,core,context,armed,store,reader,quiescer,*,activation=None,role=None,monotonic=time.monotonic):
        require(role in ('writer','watchdog'),'Explicit bounded process role required')
        self.role=role
        self.core=core;self.context=context;self.armed=armed;self.store=store;self.reader=reader
        self.quiescer=quiescer;self.activation=activation;self.now=monotonic

    def check_scope(self,sha,nonce):
        require(sha==self.core.digest(self.context) and nonce==self.context['nonce']
          and self.store.context_sha==sha and self.store.nonce==nonce,'IPC scope differs')
    def close_input(self,sha,nonce): self.check_scope(sha,nonce);return self.store.close_input()
    def input_is_open(self,sha,nonce): self.check_scope(sha,nonce);return self.store.input_is_open()
    def mark_once(self,action,sha,nonce,request_sha=None):
        self.check_scope(sha,nonce)
        require(action in {'activation','fixture:seed','fixture:source-put'}|{'reduce:'+target for target in self.core.TARGETS},'Intent outside exact scope')
        if action.startswith('fixture:'): require(request_sha==self.context['fixtureRequestSHA256'][action.split(':',1)[1]],'Fixture request differs')
        return self.store.mark_once(action,sha,nonce,request_sha)
    def quiesce_writer(self,expected,timeout_seconds): return self.quiescer.quiesce_writer(expected,timeout_seconds)
    def observe(self,target,timeout_seconds): return self.reader.observe(target,timeout_seconds)
    def unchanged_boundaries(self,timeout_seconds): return self.reader.unchanged_boundaries(timeout_seconds)
    def append_receipt(self,receipt): self.store.append_json('controller-receipt',receipt)
    def watchdog_ack(self,sha,nonce):
        self.check_scope(sha,nonce)
        receipt=self.store.latest_heartbeat('watchdog')
        require(receipt is not None,'Watchdog ACK missing')
        full=receipt['identity']
        require(self.core.same(self.store.identity('watchdog'),full) and self.quiescer is not None
          and self.core.same(self.quiescer.proc.identity(full['pid'],self.armed['nonce']),full), 'Registered watchdog is no longer alive on exact PID/start/boot/command')
        identity={'pid':full['pid'],'pgid':full['pgid'],'uid':full['uid'],'startTime':full['startTicks'],'nonce':full['nonce']}
        require(self.core.same(identity,self.armed['watchdogIdentity']),'Watchdog ACK identity differs')
        return {'identity':identity,'contextSHA256':self.armed['contextSHA256'],'at':receipt['at']}
    def request_stop(self,reason,sha,nonce): self.check_scope(sha,nonce);self.store.request_stop(reason)
    def mutate(self,intent,timeout_seconds):
        self.check_scope(self.armed['contextSHA256'],self.armed['nonce'])
        require(self.role=='watchdog','Only independent watchdog may reduce controls')
        require(intent.target in self.core.TARGETS and self.core.same(intent.__dict__,self.core.reduction_intent(self.context,intent.target).__dict__),'Unreviewed mutation intent')
        # A direct caller cannot skip durable intent or mutate another target.
        require(self.store.has_intent('reduce:'+intent.target),'Reduction lacks durable prior intent')
        require(self.store.mark_once('external-call:'+intent.target,self.armed['contextSHA256'],self.armed['nonce']),'External mutation already attempted')
        target=intent.target; identity=intent.identity; parameters=copy.deepcopy(intent.parameters)
        if target=='outbox-rule': service,op='events','disable-rule';parameters['Name']=identity['Name']
        elif target=='bucket-notifications': service,op='s3api','put-bucket-notification-configuration';parameters['Bucket']=identity['Bucket']
        elif target.endswith('-mapping'): service,op='lambda','update-event-source-mapping';parameters['UUID']=identity['UUID']
        elif target.endswith('-concurrency'): service,op='lambda','put-function-concurrency';parameters['FunctionName']=identity['FunctionArn']
        else:
            service,op='s3api','put-bucket-policy';parameters['Bucket']=identity['Bucket'];parameters['Policy']=json.dumps(parameters['Policy'],separators=(',',':'),allow_nan=False)
        deadline=self.now()+timeout_seconds
        self.reader.cli.verify_identity(deadline)
        self.reader.cli.call(service,op,parameters,deadline,mutation=True)
        return 'outer-command-returned-success-readback-required'
    def apply_saved_plan_once(self,plan_sha):
        self.check_scope(self.armed['contextSHA256'],self.armed['nonce'])
        require(self.role=='writer','Only isolated writer may apply saved activation')
        ack=self.watchdog_ack(self.armed['contextSHA256'],self.armed['nonce'])
        require(0<=self.now()-ack['at']<=self.context['heartbeatSeconds'] and self.store.input_is_open(),'Live watchdog ACK/input window expired before saved apply')
        require(self.activation is not None,'Pinned activation capability unavailable')
        require(plan_sha==self.context['activationSavedPlanSHA256'],'Activation plan differs')
        require(self.store.has_intent('activation') and self.store.mark_once('external-call:activation',self.armed['contextSHA256'],self.armed['nonce']),'Activation missing or already attempted')
        return self.activation.apply_once()
    def verify_exact_active_profile(self):
        require(self.activation is not None and self.activation.verify_post_state() is True,'Exact activation60 raw state not verified')
        for target in self.core.TARGETS:
            observed=self.observe(target,self.context['callTimeoutSeconds'])
            expected=self.context['targets'][target]['activeValue']
            require(self.core.same(observed['value'],expected),'Active control value differs')
        self.unchanged_boundaries(self.context['callTimeoutSeconds'])
        return True


class SavedActivation:
    """One saved binary, fixed Terraform cwd/data/config; no plan/retry/refresh flag."""
    def __init__(self,spec,context,armed,store,env,*,run=subprocess.run,monotonic=time.monotonic):
        self.spec=spec;self.context=context;self.armed=armed;self.store=store;self.env=dict(env);self.run=run;self.now=monotonic
    def verify_post_state(self):
        state=json.loads(Path(self.spec['state']['path']).read_text())
        require(state.get('lineage')==self.spec['stateLineage'] and type(state.get('serial')) is int
          and state['serial']>self.spec['stateSerial'],'Activation poststate lineage/serial differs')
        found=set()
        for resource in state.get('resources',[]):
            if resource.get('mode')=='data':continue
            require(resource.get('module')=='module.ecoguard' and resource.get('mode')=='managed'
              and resource.get('provider')=='module.ecoguard.provider["registry.terraform.io/hashicorp/aws"]','Activation poststate scope/provider differs')
            for instance in resource.get('instances',[]):
                require(not instance.get('deposed') and not instance.get('status'),'Activation poststate tainted/deposed')
                index=instance.get('index_key')
                suffix='' if index is None else '['+json.dumps(index,separators=(',',':'))+']'
                address='module.ecoguard.'+resource['type']+'.'+resource['name']+suffix
                require(address not in found,'Duplicate poststate instance');found.add(address)
        require(len(found)==60 and found==set(self.spec['plannedManagedAddresses']),'Activation exact60 address inventory differs')
        # Compare the exact native planned descriptors, including the two
        # observed dynamic-set to string-set type resolutions. Do not derive
        # active output types from the old physical outputs or mutate either.
        expected=self.spec['plannedOutputs'];actual=state.get('outputs')
        require(type(expected) is dict and len(expected)==11 and type(actual) is dict
          and set(actual)==set(expected),'Activation exact11 output inventory differs')
        for name,planned in expected.items():
            raw=actual[name]
            require(type(planned) is dict and set(planned)=={'type','value','sensitive'}
              and planned['sensitive'] is False and type(raw) is dict
              and set(raw) in ({'type','value'},{'type','value','sensitive'})
              and ('sensitive' not in raw or raw['sensitive'] is False)
              and digest(raw['type'])==digest(planned['type'])
              and digest(raw['value'])==digest(planned['value']),
              'Activation output descriptor differs beyond absent raw sensitive:false: '+name)
        return True

    def apply_once(self):
        spec=self.spec
        for key in ('terraform','provider','plan','cliConfig','backendMetadata','state'):
            regular(spec[key]['path'],spec[key]['sha256'])
        require(spec['plan']['sha256']==self.context['activationSavedPlanSHA256'],'Saved plan SHA differs')
        remaining=self.armed['stopNewWorkBy']-self.context['stopReserveSeconds']-self.now()
        require(remaining>0,'No activation time before stop reserve')
        env={**self.env,'TF_DATA_DIR':spec['data'],'TF_CLI_CONFIG_FILE':spec['cliConfig']['path'],'TF_IN_AUTOMATION':'1','CHECKPOINT_DISABLE':'1'}
        outcome={'kind':'saved-activation','savedPlanSHA256':spec['plan']['sha256'],'maximumCommands':1,'replanInvoked':False,'retryPermitted':False}
        try:
            # Terraform output may contain internal IDs; keep it only in the
            # private fsynced outcome. Never forward stdout/stderr to the terminal.
            result=self.run([spec['terraform']['path'],'-chdir='+spec['root'],'apply','-input=false','-no-color','-lock-timeout=1s',spec['plan']['path']],
              env=env,stdin=subprocess.DEVNULL,capture_output=True,timeout=remaining,shell=False)
            require(len(result.stdout)+len(result.stderr)<=16*1024*1024,'Activation log bound exceeded')
            outcome['exitCode']=result.returncode
            outcome['stdoutSHA256']=hashlib.sha256(result.stdout).hexdigest()
            outcome['stderrSHA256']=hashlib.sha256(result.stderr).hexdigest()
        except Exception:
            outcome['exitCode']=None;outcome['category']='uncertain-or-failed-no-retry'
        self.store.append_json('activation-outcome',outcome)
        return {'exitCode':outcome['exitCode']}
