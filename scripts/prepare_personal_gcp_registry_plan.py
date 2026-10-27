"""Frozen read-only cloud plan; never applies or changes IAM/resources."""
from pathlib import Path
import datetime, hashlib, json, os, re, subprocess, zipfile
os.umask(0o077)
BASE=Path.home()/'ecoguard-c-personal-20261023'
SOURCE=BASE/'source'
ROOT=SOURCE/'infra/gcp/environments/personal'
PRIVATE=ROOT/'private'
STATE=ROOT/'state/terraform.tfstate'
OLD='fdfaf23b7d888c9579668d5c12c06ec649660191'
NEW='00d58e0e8c65321cc759d575eafaba801c1e8253'
PROJECT='ecoguard-fit3184-a2-2026'
TF=Path('/tmp/ecoguard-c-personal-20261023/tools/terraform')
ATTEMPT=PRIVATE/'registry-plan-20261024-1'
for key,value in os.environ.items():
    assert not (value and (key.startswith('TF_CLI_ARGS') or key in ('TF_WORKSPACE','TF_LOG','TF_LOG_PATH','TF_CLI_CONFIG_FILE'))), 'Unexpected Terraform environment override'
for key in ('GOOGLE_CREDENTIALS','GOOGLE_APPLICATION_CREDENTIALS','GOOGLE_OAUTH_ACCESS_TOKEN','GOOGLE_IMPERSONATE_SERVICE_ACCOUNT','GOOGLE_CLOUD_KEYFILE_JSON','GCLOUD_KEYFILE_JSON','CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT'):
    assert not os.environ.get(key), 'Unreviewed provider credential override'
assert not (Path.home()/'.terraformrc').exists(), 'Unreviewed Terraform CLI configuration'
ENV={**os.environ,'TF_DATA_DIR':'/tmp/ecoguard-c-personal-20261023/terraform-data-gcp','CHECKPOINT_DISABLE':'1','TF_IN_AUTOMATION':'1'}
def run(args,timeout=60):
    result=subprocess.run([str(a) for a in args],env=ENV,capture_output=True,text=True,timeout=timeout)
    if result.returncode: raise RuntimeError('Read/preparation failed: '+str(args[0]))
    return result.stdout.strip()
def save(name,value):
    with (ATTEMPT/name).open('x') as output: json.dump(value,output,indent=2);output.write('\n')
def digest(data): return hashlib.sha256(data).hexdigest()
def cloud(args):return json.loads(run(['gcloud',*args,'--format=json']))
assert run(['gcloud','auth','list','--filter=status:ACTIVE','--format=value(account)'])=='hoshigahoshii@163.com'
assert run(['gcloud','config','get-value','project'])==PROJECT
assert run(['gcloud','config','get-value','auth/impersonate_service_account']) in ('','(unset)'), 'Unreviewed account impersonation'
project=cloud(['projects','describe',PROJECT]);assert project['projectId']==PROJECT and str(project['projectNumber'])=='995070689587' and project['lifecycleState']=='ACTIVE'
assert run(['git','-C',SOURCE,'rev-parse','HEAD'])==OLD
assert not run(['git','-C',SOURCE,'status','--porcelain','--untracked-files=no'])
original=STATE.read_bytes();raw=json.loads(original)
instances=[item for resource in raw['resources'] if resource.get('mode')=='managed' for item in resource.get('instances',[])]
assert len(instances)==7 and all(item.get('status') in (None,'ready') and not item.get('deposed') for item in instances)
assert original==(PRIVATE/'postapply-state-private-backup.json').read_bytes()
assert not any(list(ROOT.glob(pattern)) for pattern in ('*.auto.tfvars','*.auto.tfvars.json','terraform.tfvars','terraform.tfvars.json')), 'Unexpected root input file'
ATTEMPT.mkdir(mode=0o700)
(ATTEMPT/'state-before-private-backup.json').write_bytes(original)
save('preflight.json',{'project':PROJECT,'projectNumber':'995070689587','oldSource':OLD,'newSource':NEW,'stateSHA256':digest(original),'lineage':raw['lineage'],'serial':raw['serial'],'managedResources':7,'observedAtUtc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
run(['git','-C',SOURCE,'fetch','--no-tags','--depth=1','https://github.com/xihan-u/aussie-ecoguard-fit3184-a2.git',NEW],120)
assert run(['git','-C',SOURCE,'rev-parse','FETCH_HEAD'])==NEW
run(['git','-C',SOURCE,'checkout','--detach',NEW])
assert run(['git','-C',SOURCE,'rev-parse','HEAD'])==NEW and not run(['git','-C',SOURCE,'status','--porcelain','--untracked-files=no'])
assert STATE.read_bytes()==original
assert run(['git','-C',SOURCE,'hash-object',ROOT/'.terraform.lock.hcl'])==run(['git','-C',SOURCE,'rev-parse',NEW+':infra/gcp/environments/personal/.terraform.lock.hcl'])
lock_before=(ROOT/'.terraform.lock.hcl').read_bytes()
if not TF.is_file():
    TF.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    archive=ATTEMPT/'terraform_1.17.0_linux_amd64.zip'
    run(['curl','--disable','--fail','--silent','--show-error','--proto','=https','--proto-redir','=https','--location','--max-time','120','--output',archive,'https://releases.hashicorp.com/terraform/1.17.0/terraform_1.17.0_linux_amd64.zip'],150)
    assert digest(archive.read_bytes())=='c168cab7c637a8769fdb90089ddd19de701bc6ff8aca64dc2e2185fe46f59f67'
    with zipfile.ZipFile(archive) as zipped: TF.write_bytes(zipped.read('terraform'))
    TF.chmod(0o700)
assert json.loads(run([TF,'version','-json']))['terraform_version']=='1.17.0'
with (ATTEMPT/'init.log').open('x') as log:
    init=subprocess.run([str(TF),'-chdir='+str(ROOT),'init','-input=false','-lockfile=readonly','-no-color'],env=ENV,stdout=log,stderr=subprocess.STDOUT,timeout=240)
assert init.returncode==0, 'Initialization failed; inspect private log'
assert (ROOT/'.terraform.lock.hcl').read_bytes()==lock_before
backend=json.loads((Path(ENV['TF_DATA_DIR'])/'terraform.tfstate').read_text())['backend']
assert backend['type']=='local' and backend['config']['path']=='state/terraform.tfstate'
assert run([TF,'-chdir='+str(ROOT),'workspace','show'])=='default'
version=json.loads(run([TF,'-chdir='+str(ROOT),'version','-json']))
assert version['provider_selections']=={'registry.terraform.io/hashicorp/google':'7.46.1'}
validation=json.loads(run([TF,'-chdir='+str(ROOT),'validate','-json']));save('validate.json',validation)
assert validation['valid'] and validation['error_count']==0 and validation['warning_count']==0
assert STATE.read_bytes()==original and not run(['git','-C',SOURCE,'status','--porcelain','--untracked-files=no'])
print('REGISTRY_PLAN_STARTED: exact project/state/source/provider checked; no apply.',flush=True)
plan=ATTEMPT/'registry.tfplan'
with (ATTEMPT/'plan.log').open('x') as log:
    result=subprocess.run([str(TF),'-chdir='+str(ROOT),'plan','-input=false','-no-color','-lock-timeout=60s','-var=deployment_stage=registry','-var=inference_image=','-out='+str(plan)],env=ENV,stdout=log,stderr=subprocess.STDOUT,timeout=360)
save('plan-exit.json',{'returnCode':result.returncode,'stateFileUnchanged':STATE.read_bytes()==original})
assert result.returncode==0, 'Plan failed; inspect private log'
assert STATE.read_bytes()==original
text=run([TF,'-chdir='+str(ROOT),'show','-no-color',plan]);(ATTEMPT/'registry-show.txt').write_text(text+'\n')
document=json.loads(run([TF,'-chdir='+str(ROOT),'show','-json',plan]));save('registry.json',document)
gate=subprocess.run(['python3',str(ROOT/'check_runtime_plan.py'),'--stage','registry','--plan-json',str(ATTEMPT/'registry.json')],env=ENV,capture_output=True,text=True,timeout=60)
report=json.loads(gate.stdout);save('gate-report.json',report)
changes=[item for item in document.get('resource_changes',[]) if item.get('mode')=='managed']
headers=re.findall(r'^  # (.+) will be created$',text,re.MULTILINE)
summary={'status':report['status'],'project':PROJECT,'projectNumber':'995070689587','sourceRevision':NEW,'savedPlanSHA256':digest(plan.read_bytes()),'creates':sum(item['change']['actions']==['create'] for item in changes),'noops':sum(item['change']['actions']==['no-op'] for item in changes),'otherChanges':[{'address':item['address'],'actions':item['change']['actions']} for item in changes if item['change']['actions'] not in (['create'],['no-op'])],'gateChecksPassed':sum(c['passed'] for c in report['checks']),'gateChecksTotal':len(report['checks']),'failedChecks':[c['name'] for c in report['checks'] if not c['passed']],'textCreateHeaders':headers,'textWarnings':'Warning:' in text or 'Warning:' in (ATTEMPT/'plan.log').read_text(),'stateFileUnchanged':STATE.read_bytes()==original,'resourceDriftEntries':len(document.get('resource_drift',[])),'observedAtUtc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'applyExecuted':False}
save('review-summary.json',summary)
print(json.dumps(summary),flush=True)
assert gate.returncode==0 and summary['creates']==2 and summary['noops']==7 and not summary['otherChanges'] and len(headers)==2 and not summary['textWarnings'] and summary['stateFileUnchanged']
