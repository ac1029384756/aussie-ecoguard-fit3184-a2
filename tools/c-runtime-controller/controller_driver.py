"""DEFAULT INERT: reviewed adapter for the existing bounded controller.

--inspect/import never execute a command, arm, launch, signal, or contact AWS.
The explicit launch remains blocked by ARM_REVIEWED=False and pending actual
binding. It cannot be enabled by filling JSON alone. A reviewed release copy,
actual adopted60 pause proof, a NEW activation plan, new human authority and evidence
are required. This v2 can submit only the one reviewed fixture from its owned writer after
all future guards pass. It never invokes Lambda/models directly or cleans data.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import threading
from datetime import datetime, timezone, timedelta

ARM_REVIEWED = False
CORE_SHA256 = 'bb203938157d1fc2a2a8965f4e3e8b29e6c2371496912086b22c279ad06f1af5'
PRIVATE_RUNTIME_SHA256 = '31168c5ad1871250f1e0fa45abd1170561344d74302e5792108427c1f01094e6'
AWS_RUNTIME_SHA256 = '88bd456dce12d44f6a1724a7c6831f0324e0b999aa31adbaf150f57e6e66ef53'
SDK_BRIDGE_SHA256 = 'aaedd932c2870fcb3031f1749b5f2e9b72dd4d5abfd47a173eb2dd6d2a78eec0'
SDK_WORKER_SHA256 = '92647337b7cec2a9a27e57100b6a15e93c488e735a3ee25966110b0b52efcb0d'
SDK_MANIFEST_SHA256 = '38a63a55f3410cea5fbc2dc547a222103d6679e8677350e7e2f3560f7e58d1a3'
ACTIVATION_REVIEWER_SHA256 = '880f42268fa66c90285d03a89d8cc10c549a248abb3b9351a2290573bb13f9ba'
ACTIVATION_PREPARER_SHA256 = None  # Bound only after the new prepare-only source is reviewed.
STARTUP_READINESS_SECONDS = 120  # Consumes the original window; never resets T0 or the stop reserve.
FIXTURE_RUNTIME_SHA256 = '8aa156b52a5a0979a08544d770809d7e069dc1d82aba8f283118cc566329ccf1'
DRAIN_RUNTIME_SHA256 = '9e7552b16e31a69ba407ef0559a8c9582703e4e5dddf2381f0bb77da4ae45f76'
FIXTURE_HELPER_SHA256 = '9c7dd4d4772456b5fb62d5385bdde5b5a626f90e0c2d6c37a233eee067c5b966'
FIXTURE_HELPER_FILE = Path(__file__).resolve().parent.parent/'automatic-fixture-helper-20261024-1/automatic_fixture_DRAFT.py'
CORE_FILE = Path(__file__).with_name('bounded_controller_lowquota.py')
BINDING_TEMPLATE = Path(__file__).with_name('BINDING-PENDING.json')
ACCOUNT, REGION, PREFIX = '011154879765', 'us-east-1', 'ecoguard3184-personal'
BASE = Path('/home/cloudshell-user/ecoguard-c-personal-20261023')
MODULE = 'module.ecoguard.'
UPDATES = {MODULE+'aws_lambda_function.ingest[0]', MODULE+'aws_lambda_function.zip["infer"]',
 MODULE+'aws_lambda_function.zip["outbox"]', MODULE+'aws_lambda_event_source_mapping.ingest[0]',
 MODULE+'aws_lambda_event_source_mapping.zip_queues["infer"]', MODULE+'aws_cloudwatch_event_rule.maintenance["outbox"]',
 MODULE+'aws_s3_bucket_policy.media_tls'}
NEW_NOTIFICATION = MODULE+'aws_s3_bucket_notification.uploads[0]'
SOURCE_GATE_SHAS = {'check_processing_plan.py': '8aa53c59a0f0fd56e70f42e08ec2f2f2960784bf8ec7aba7e9e6ee85f7e1dfbe', 'check_staged_increment_plan.py': '59d7977be2a008e6faf707ec30bf9e13d587ed4067f629b875320df86757857a', 'check_ecr_policy_plan.py': 'a871ad36b2c55d808adaf28a5d637cd544f7e4750d20545094a3019b5daba0fb', 'check_plan.py': '36bce117903730ffbd86a927209cf7f642a104a622b52e2545a58fe9935e898d'}
CURRENT_RAW_STATE_SHA256 = '5de33593233eed3023b35a6f359238f17a3b56cfd349ea64291581b939cf7fc5'
CURRENT_PAUSED_AUDIT_SHA256 = None  # Actual current C14 API proof has not run; never infer success.

CURRENT_STATE_SERIAL = 95
CURRENT_PAUSED_COLLECTOR_SHA256 = 'd730135c020ff2b5777be338e9c6c61170c0ce878fb30020af0a5033c94b7424'
CURRENT_IDENTIFIERS_SHA256 = 'cb7979805898ef73280107d3c6bfec8839c2270af7be5249f71a040a3fcfbbef'
CURRENT_PREVIOUS_ACTIVATION_SHA256 = 'd4535797e7a1ee316f5ff779c4358dabf6c5af6542c421d8de961a3bf86265b6'
REVIEWED_PREPARER_SHA256 = '623aebcf730f640295b252cca057d4c2e17eb2a12a82a12644e00a4462797554'
CURRENT_RECONCILIATION_SHA256 = '7de373531995b42d7da65b7882eedc21afb41eac1600cede6a963b61aafb8855'
ACTIVATION_NATIVE_FILES = {'fresh-function-inventory-outcome.json': '464279cfe3d878e859e02e75c09f88703e56237f8c948e2b16af4f7f2bee8206',
 'fresh-function-inventory-started.json': 'f3837401d6b2214bf6b45a84af25bddcf9ebfe864a35f5070674d9aeaaeabc68',
 'fresh-function-inventory-stderr-private.bin': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
 'fresh-function-inventory-stdout-private.bin': 'd5ff4f210fcc78ce59c4ab99b9f3ef42bebb50405da715ccf890de75c6c0214e',
 'fresh-quota-settings-outcome.json': 'a4bb16fe73a5a5c7c397215d883d83180bf88bba46c2d163b4ff9245feab5781',
 'fresh-quota-settings-started.json': '4185b6654eb7207e7b7f4319cd4b2e6ecabf3ee9976db304e57fbd05d319a94d',
 'fresh-quota-settings-stderr-private.bin': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
 'fresh-quota-settings-stdout-private.bin': '39f2ba2a69c4575bd5863107645ae203688a31c4fbc4f6cc7bfcd3676f444295',
 'fresh-root-identity-outcome.json': '99ee5d651fad309542d227ca2624a85ce0242058f56c7d8cce66010fe3f87092',
 'fresh-root-identity-started.json': '96e6c6a9cc4392f928ae9d9a686c4c5e95e14ea8a32d291a0bea8e47aa63fbdb',
 'fresh-root-identity-stderr-private.bin': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
 'fresh-root-identity-stdout-private.bin': '62e5a00ca75bf7e8104d15a1dbf63b50599d47822e0098c2d9818adb8c577299',
 'input-evidence-sha256-private.json': '3f3dd234b8e1c29ef44ff5e5f3a3ae5822512803ddfdcd21d248301721d0c9f4',
 'normal-refresh-plan-outcome.json': 'ec861a9a1cb2e45e183addda9fe0b0bae51ef741b17b849bd0b453ddbc554d7f',
 'normal-refresh-plan-started.json': '8e88cb3754e7804443bb88e405e905a0b061a9005c7462845939eb3a29238476',
 'normal-refresh-plan-stderr-private.bin': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
 'normal-refresh-plan-stdout-private.bin': '57ef596c640d559fca2f8ec8ef085c0016f0ff30088d3293ef4b61ec9a4a3c62',
 'physical60-values-private.json': 'cdb5e236fb118386f6af2f7b8d89e1fcd1ddba9d796e40c7a0074508d3d5ae01',
 'physical95-show-outcome.json': '65298798a2f012ef1668c5169a7ebf06ce28938d66dd3c0c236528f560895590',
 'physical95-show-started.json': '0af929bf7772f043ed7d6094811bce7beca1dfbfd5da0d57c82fdcfd19ba9f5f',
 'physical95-show-stderr-private.bin': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
 'physical95-show-stdout-private.bin': 'cdb5e236fb118386f6af2f7b8d89e1fcd1ddba9d796e40c7a0074508d3d5ae01',
 'plan-started-private.json': 'd977f486d181415ffddd6f3d1d464a80c97e4a41eca95442ddb8b3647cc85d5d',
 'processing-plan-private.json': 'bbe0b54d3f36b54c1e20bfe3576c367826aa6f61a661b5c9f9f3e58f60d3b8e8',
 'processing.tfplan': 'a9271f1599a57f618e57ec1456bc56e4f01cac263a544afb10d7d26b59a77504',
 'quota-private.json': 'd9b00c9e9f8fb5e0f54682712773a6bf353dc46bea6af218da0e628aadde2e1e',
 'saved-plan-show-outcome.json': '15261e750d1718377c20b2730e86f046f84d100870c8eef19186b749d8899a2f',
 'saved-plan-show-started.json': 'b702b1e446ff942824394f6404881f68ea5ed7eed83bf1aa464c1e15f7b30259',
 'saved-plan-show-stderr-private.bin': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
 'saved-plan-show-stdout-private.bin': 'bbe0b54d3f36b54c1e20bfe3576c367826aa6f61a661b5c9f9f3e58f60d3b8e8',
 'state-before-private.tfstate': '5de33593233eed3023b35a6f359238f17a3b56cfd349ea64291581b939cf7fc5',
 'strict-gate-review-private.json': '689321401f207a8c95a080911e4884aca2f554b0c3d2de9626459ef8b9e60066',
 'summary-private.json': 'ae048a8fdb229fd984dc3e90049a3e7a9c3b62466e12a70b70c82a74cad65114',
 'terraform-version-outcome.json': '6dff7a6b07fb13c58742dd7821448c521a58625d462b0a8e8e649a863f22ed72',
 'terraform-version-started.json': '540d166eac3c67a85760a6e235ab36d793e06cdc011176715f5f609c089c433c',
 'terraform-version-stderr-private.bin': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
 'terraform-version-stdout-private.bin': 'c23815916318063e87e0a030bc98e8eda3c873c361981bc150356e9aed60bf40'}


def require(ok, message):
    if not ok: raise ValueError(message)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def pinned(path, expected):
    path=Path(path)
    require(path.is_absolute() and not any(p.is_symlink() for p in (path,*path.parents)) and path.is_file(), 'Pinned regular path required')
    require(type(expected) is str and re.fullmatch('[0-9a-f]{64}',expected) and sha(path)==expected,'Pinned file SHA differs')
    return path


def load(path, expected, name):
    path=pinned(path,expected)
    spec=importlib.util.spec_from_file_location(name,path)
    obj=importlib.util.module_from_spec(spec)
    sys.modules[name]=obj
    spec.loader.exec_module(obj)
    return obj


def inspect():
    return {'status':'live-adapter-draft-inert','armReviewed':ARM_REVIEWED,
      'actualPinsPending':True,'processStarted':False,'subprocessInvoked':False,'cloudInvoked':False,
      'activationApplied':False,'fixtureSubmitted':False,'actual60Assumed':False}


def modules():
    # Does not use sys.path/site packages (driver is launched with -I -B).
    core=load(CORE_FILE,CORE_SHA256,'reviewed_bounded_core')
    private=load(Path(__file__).with_name('private_runtime.py'),PRIVATE_RUNTIME_SHA256,'reviewed_private_runtime')
    aws=load(Path(__file__).with_name('aws_runtime.py'),AWS_RUNTIME_SHA256,'reviewed_aws_runtime')
    return core,private,aws


def stamp(value):
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    require(dt.tzinfo is not None,'UTC-aware observation time required')
    return dt


def managed(root):
    values={}
    def visit(module):
        for row in module.get('resources',[]):
            if row.get('mode')=='managed':
                address=row['address'];require(address not in values,'Duplicate managed address')
                values[address]=row['values']
        for child in module.get('child_modules',[]):visit(child)
    visit(root)
    return values


def raw_addresses(state):
    found=set()
    for resource in state.get('resources',[]):
        if resource.get('mode')=='data':continue
        require(resource.get('mode')=='managed' and resource.get('module')=='module.ecoguard'
          and resource.get('provider')=='module.ecoguard.provider["registry.terraform.io/hashicorp/aws"]','State provider/scope differs')
        for instance in resource.get('instances',[]):
            require(not instance.get('deposed') and not instance.get('status'),'Deposed/tainted state not accepted')
            index=instance.get('index_key')
            suffix='' if index is None else '['+json.dumps(index,separators=(',',':'))+']'
            address=MODULE+resource['type']+'.'+resource['name']+suffix
            require(address not in found,'Duplicate state instance');found.add(address)
    return found


def review_plan_shape(document, state_addresses, reviewer):
    # Full joins/typed field changes are independently reviewed below. No row is removed.
    rows=document.get('resource_drift',[])
    updates=UPDATES|{NEW_NOTIFICATION}
    require(type(rows) is list and rows==[],
      'Only the new drift-free physical95 normal plan is reviewed')
    require(document.get('complete') is True and document.get('errored') is False
      and not document.get('deferred_changes') and not document.get('action_invocations'),'Incomplete/deferred/error blocks arming')
    prior=managed(document['prior_state']['values']['root_module'])
    planned=managed(document['planned_values']['root_module'])
    require(set(prior)==set(planned)==state_addresses and len(prior)==60,'Exact existing adopted60 inventory required')
    changes=document.get('resource_changes')
    require(type(changes) is list and len(changes)==60 and len({r.get('address') for r in changes})==60,'Exactly sixty native managed changes required')
    for row in changes:
        c=row.get('change',{})
        require(row.get('mode')=='managed' and row.get('address') in state_addresses
          and c.get('actions')==(['update'] if row['address'] in updates else ['no-op'])
          and not row.get('previous_address') and not c.get('importing') and not c.get('replace_paths'),
          'Only eight existing controls may update; no create/delete/move/import/replacement')
    return prior,planned


def verify_funding(binding, aws, *, now=None):
    now=now or datetime.now(timezone.utc)
    pins=binding['actualPins']; obj=json.loads(pinned(binding['artifacts']['fundingEvidenceSHA256']['path'],pins['fundingEvidenceSHA256']).read_text())
    expected={'provider':'AWS','account':ACCOUNT,'region':REGION,'eligibleExistingCreditsPositive':True,
      'additionalOutOfPocketLimitAUD':0,'source':'official AWS Billing console'}
    require(set(obj)==set(expected)|{'observedAtUtc'} and all(type(obj.get(k)) is type(v) and obj[k]==v for k,v in expected.items()),'Funding proof schema differs')
    observed=stamp(obj['observedAtUtc']); expires=stamp(pins['fundingValidUntil'])
    require(expires==observed.replace() + timedelta(seconds=3600),'Funding TTL must be exact one hour')
    age=(now-observed).total_seconds()
    return 0<=age<=3600 and now<=expires


def validate_authority(binding, core):
    pins=binding['actualPins']; ctx=binding['context']
    obj=json.loads(pinned(binding['artifacts']['actionTimeApprovalRecordSHA256']['path'],pins['actionTimeApprovalRecordSHA256']).read_text())
    expected={'recordType':'explicit-human-action-time-approval-for-bounded-processing-and-emergency-pause',
      'approved':True,'approvalSource':'user message at action time','standingConsentUsedAsApproval':False,
      'account':ACCOUNT,'region':REGION,'contextSHA256':core.digest(ctx),'nonce':ctx['nonce'],
      'sourceRevision':pins['sourceRevision'],'paused60StateSHA256':pins['paused60RawStateSHA256'],
      'activationSavedPlanSHA256':pins['activationSavedPlanSHA256'],'activationPlanJSONSHA256':pins['activationPlanJSONSHA256'],
      'activationGateReceiptSHA256':pins['activationGateReceiptSHA256'],'reviewedEmergencyPausePlanSHA256':pins['reviewedEmergencyPausePlanSHA256'],
      'fundingEvidenceSHA256':pins['fundingEvidenceSHA256'],'gcpFreshObservationSHA256':binding['gcpFreshness']['observation']['sha256'],
      'gcpFreshFundingSHA256':binding['gcpFreshness']['funding']['sha256'],
      'gcpPrivateBaselineSHA256':binding['gcpFreshness']['privateBaseline']['sha256'],
      'fixtureSeedRequestSHA256':ctx['fixtureRequestSHA256']['seed'],'fixtureSourcePutRequestSHA256':ctx['fixtureRequestSHA256']['source-put'],
      'maximumSeedTransactions':1,'maximumSourcePutCalls':1,'manualLambdaInvocations':0,'operatorModelRequests':0,
      'productionIncomingDeletionAuthorized':True,'rekognitionImageEntryAuthorized':True,'retainedFixtureCleanupAuthorized':False,
      'maximumIndependentDrainTailSeconds':max(ctx['actualFunctionTimeouts'].values())+ctx['propagationReadAllowanceSeconds'],
      'maximumWindowSeconds':ctx['windowSeconds'],
      'maximumSavedPlanApplyCommands':1,'maximumFixtureSubmissions':1,'maximumReductionCallsPerTarget':1,
      'reducers':[core.reduction_intent(ctx,target).__dict__ for target in core.TARGETS],
      'writerProcessTerminationApproved':True,'automaticPauseApproved':True,
      'activeReservedConcurrency':{'ingest':None,'infer':None,'outbox':None},
      'activationDeletesOnlyTheseThreeReservations':True,'individualFunctionCapsClaimed':False,
      'accountConcurrencyProfile':{'ConcurrentExecutions':10,'UnreservedConcurrentExecutions':10,'FunctionCount':8},
      'soleSQSMaximumConcurrency':{'ingest':2,'infer':2},'outboxGuaranteedFunctionCap':None,
      'apiAndSignupRemainPaused':True,'notifyDeleteCleanupLexRemainPaused':True,
      'IAMChangesApproved':False,'newCloudServiceApproved':False,'eventOrObjectCleanupApproved':False,
      'replanApproved':False,'retryApproved':False,'additionalOutOfPocketLimitAUD':0}
    require(set(obj)==set(expected)|{'approvedAtUtc','actualUserReplySHA256'}
      and all(core.same(obj.get(k),v) for k,v in expected.items()),'Exact new per-action human authority required')
    require(re.fullmatch('[0-9a-f]{64}',obj['actualUserReplySHA256']) is not None,'Actual human reply evidence SHA pending')
    reply=binding['actualHumanReply']
    pinned(reply['path'],obj['actualUserReplySHA256'])
    require(Path(reply['path']).stat().st_size>0,'Actual reply must be retained')
    now=datetime.now(timezone.utc); approved=stamp(obj['approvedAtUtc'])
    require(0<=(now-approved).total_seconds()<=3600,'Action-time approval future/expired')


def review_paused59_chain(core, pins, original, verification):
    """Pure review of the actual apply0/blocked + independent after-only success.

    validate_binding SHA-checks both retained raw files before calling this.
    These exact historical hashes do not arm, grant approval or rewrite a result.
    """
    expected_pins={
      'paused59ApplyReceiptSHA256':'68a4a71df5f47c4b70962d5f78f107cada5e1dd0de52d960f90bf7f76aabe4c1',
      'paused59ReadOnlyVerificationReceiptSHA256':'8d9f5f19097c84d87c896a37b0b38a25072f39273629261daa5980d25e8925d0',
      'paused59RawStateSHA256':'20d4a207723e6f766940c87bf1cb319c9165f16464dae26ee24669340969c64f',
      'paused59StateSerial':76,'paused59StateLineage':'58808681-d69a-1fe0-b562-796a24a58fdc'}
    require(type(pins) is dict and all(core.same(pins.get(k),v) for k,v in expected_pins.items()),
      'Exact actual paused59 dual-evidence pins required')
    expected_original={'status':'blocked','applyExecuted':True,'applyExitCode':0,
      'savedPlanSHA256':'c9c02a9b2c2c922c7bfa63c4ee373219ea128bca224a9299d3f51090c8575cd6',
      'stateWritten':True,'finalStateSHA256':expected_pins['paused59RawStateSHA256'],
      'errorType':'ValueError','error':'Actual new-resource tags must be present and exactly empty',
      'runtimeActivated':False,'applicationInvoked':False,'automaticRetry':False}
    require(type(original) is dict and all(core.same(original.get(k),v) for k,v in expected_original.items()),
      'Preserve the exact once-successful command and original blocked postcheck')
    expected_verification={'status':'paused-wiring59-readonly-verification-passed',
      'originalApplyExitCode':0,'originalPostcheckBlockedSummaryPreserved':True,
      'applyExecuted':False,'planExecuted':False,'stateWritten':False,
      'runtimeActivated':False,'applicationInvoked':False,
      'originalStateSHA256':expected_pins['paused59RawStateSHA256'],
      'stateSHA256':expected_pins['paused59RawStateSHA256'],'managedResources':59,
      'serial':expected_pins['paused59StateSerial'],'lineage':expected_pins['paused59StateLineage'],
      'old56MatchReviewedRefreshedPrior':True,'fullPhysicalPriorEqual':False,
      'reviewedExactProviderObservations':2,'allOtherPhysical56ValuesExact':True,
      'new3ConfiguredValuesAndUnknownMasksVerified':True,'existingPausedChecksPassed':34,
      'allEightFunctionsReservedZero':True,'newIngestMappingDisabled':True,
      'sourceAndOriginalEvidenceUnchanged':True,'cloudInferenceVerified':False,'crossCloudVerified':False}
    require(type(verification) is dict and all(core.same(verification.get(k),v) for k,v in expected_verification.items()),
      'Independent after-only paused59 success is required alongside original apply0/blocked')
    return True



def review_paused60_chain(binding,core):
    pins=binding['actualPins'];artifacts=binding['artifacts'];ctx=binding['context']
    require(type(CURRENT_PAUSED_AUDIT_SHA256) is str and re.fullmatch('[0-9a-f]{64}',CURRENT_PAUSED_AUDIT_SHA256),
      'Actual current C14 paused API receipt is pending; state-only reconciliation is not API proof')
    require(pins['paused60RawStateSHA256']==CURRENT_RAW_STATE_SHA256
      and type(pins['paused60StateSerial']) is int and pins['paused60StateSerial']==CURRENT_STATE_SERIAL
      and pins['paused60StateLineage']=='58808681-d69a-1fe0-b562-796a24a58fdc'
      and pins['paused60ReadOnlyVerificationReceiptSHA256']==CURRENT_PAUSED_AUDIT_SHA256
      and pins['paused60PreviousActivationReceiptSHA256']==CURRENT_PREVIOUS_ACTIVATION_SHA256,
      'Exact current95 and separate actual paused API proof required')
    # This is the third consumed activation's original result, never the new
    # plan's authorization or a claim that the image completed.
    activation=json.loads(pinned(artifacts['paused60PreviousActivationReceiptSHA256']['path'],CURRENT_PREVIOUS_ACTIVATION_SHA256).read_text())
    require(core.same(activation,{'contextSHA256':'f1d7860c620e9b830b50e6f74ae0e4a83747665cdcd2b6901448be89f74d9938',
      'nonce':'e94d47afa93d473c4ece8d647e21f09c9a382447c74c460a29c541a18649240f',
      'payload':{'activationAttempted':True,'activeVerified':True,'fixtureSubmitted':False,'inputClosureVerified':False,
      'retryPermitted':False,'status':'active-profile-verified','stopRequestRecorded':False,'watchdogMustRemainArmed':True}}),
      'Preserve the exact consumed third activation result without upgrading its fixture outcome')
    result=BASE/'processing-binding-readonly-inputs-20261025-14-paused95'
    producer=BASE/'processing-binding-readonly-collector-20261025-14-paused95/collector.py'
    require(artifacts['paused60ReadOnlyVerificationReceiptSHA256']['path']==str(result/'summary-private.json'),
      'Current paused API receipt canonical path differs')
    audit=json.loads(pinned(result/'summary-private.json',CURRENT_PAUSED_AUDIT_SHA256).read_text())
    expected={'status':'readonly-binding-inputs-collected','identifiersSHA256':CURRENT_IDENTIFIERS_SHA256,
      'criticalPausedChecksPassed':34,'allEightReservedZero':True,'fourMappingsSoleAndDisabled':True,
      'allEightControlProfilesMeasured':True,'fullBoundariesMeasured':True,'allFiveTablesEightQueuesObserved':True,
      'sourceAndStateUnchanged':True,'managedResources':60,'rawStateSerial':CURRENT_STATE_SERIAL,
      'rawStateSHA256':CURRENT_RAW_STATE_SHA256,'actualControlsPaused':True,
      'candidateActivationPlanSHA256':ACTIVATION_NATIVE_FILES['processing.tfplan'],'nativePlanHistoricalProofOnly':True,
      'terraformConfigurationConverged':False,'previousRuntimeNoncesNotReused':True,
      'threeComputedRevisionIdsProjectedOnlyForImmutableProfile':True,'allRawControlProfilesRetained':True,
      'seedRequestCreated':False,'createdAtStillPending':True,'cloudMutationInvoked':False,'terraformInvoked':False,
      'controllerArmed':False,'contextComplete':False,'newApprovalClaimed':False,'activationAuthorized':False,
      'runtimeActivated':False,'fixtureSubmitted':False,'createdAtUtc':None,'retryPermitted':False,'maximumCollectionSeconds':240}
    require(all(core.same(audit.get(k),v) for k,v in expected.items()),'Actual full fresh C14 paused/control/boundary/backlog receipt differs')
    require(type(audit.get('elapsedSeconds')) in (int,float) and math.isfinite(audit['elapsedSeconds'])
      and 0<=audit['elapsedSeconds']<=240 and 0<=(datetime.now(timezone.utc)-stamp(audit['observedAtUtc'])).total_seconds()<=3600,
      'Current paused baseline elapsed/time differs')
    proof=binding['currentPauseProof']
    require(type(proof) is dict and set(proof)=={'producer','inputs','identifiers'}
      and proof['producer']=={'path':str(producer),'sha256':CURRENT_PAUSED_COLLECTOR_SHA256}
      and proof['inputs']['path']==str(result/'input-evidence-sha256-private.json')
      and proof['identifiers']=={'path':str(BASE/'future-processing-attempt-identifiers-20261025-4.json'),
      'sha256':CURRENT_IDENTIFIERS_SHA256},'Exact current readonly collector source/input/identifier references required')
    pinned(producer,CURRENT_PAUSED_COLLECTOR_SHA256)
    inputs=json.loads(pinned(proof['inputs']['path'],proof['inputs']['sha256']).read_text())
    require(type(inputs) is dict and inputs.get(str(producer))==CURRENT_PAUSED_COLLECTOR_SHA256
      and inputs.get(str(BASE/'source/infra/aws/environments/personal/state/terraform.tfstate'))==CURRENT_RAW_STATE_SHA256
      and inputs.get(proof['identifiers']['path'])==CURRENT_IDENTIFIERS_SHA256,'Collector retained input anchors differ')
    for name,digest in inputs.items():
        path=Path(name)
        require(path.is_absolute() and '..' not in path.parts and (path.is_relative_to(BASE)
          or path.is_relative_to(Path('/tmp/ecoguard-aws-tool-restore-20261024-1/terraform-data'))
          or path in {Path('/tmp/ecoguard-c-personal-20261023/tools/terraform'),Path('/usr/local/aws-cli/v2/2.38.1/dist/aws'),
                      Path('/usr/bin/python3.13'),Path('/usr/local/python3.13/bin/python3')})
          and not any(v.lower() in {'.aws','credentials','token.json','application_default_credentials.json'} or v.startswith('.env') for v in path.parts),
          'Collector input escaped fixed evidence/tool scope')
        pinned(path,digest)
    identifiers=json.loads(pinned(proof['identifiers']['path'],CURRENT_IDENTIFIERS_SHA256).read_text())
    require(identifiers['nonce']==ctx['nonce'] and identifiers['fixture']['createdAtUtc'] is None
      and all(core.same(identifiers['fixture'][k],ctx['fixture'][k]) for k in ('ownerSub','jobId','mediaId')),
      'New context must use the genuine unconsumed C14 identifier set')
    history=binding['historicalPaused59']
    require(set(history)=={'pins','artifacts','role'} and history['role']=='historical-only-not-current-checkpoint'
      and set(history['artifacts'])=={'paused59RawStateSHA256','paused59ApplyReceiptSHA256','paused59ReadOnlyVerificationReceiptSHA256'},
      'Separate complete historical59 provenance required')
    for key,record in history['artifacts'].items():pinned(record['path'],history['pins'][key])
    review_paused59_chain(core,history['pins'],json.loads(Path(history['artifacts']['paused59ApplyReceiptSHA256']['path']).read_text()),
      json.loads(Path(history['artifacts']['paused59ReadOnlyVerificationReceiptSHA256']['path']).read_text()))
    require(core.same(binding['context'].get('currentCheckpoint'),{'rawStateSHA256':CURRENT_RAW_STATE_SHA256,'serial':CURRENT_STATE_SERIAL,'managedResources':60,
      'independentPausedProofSHA256':CURRENT_PAUSED_AUDIT_SHA256}),'Immutable shared context must explicitly bind the current60 checkpoint')
    return True

def review_independent_receipt(core, reviewer, checked, receipt, document, quota):
    require(core.same(receipt,checked),'Strict paused95 review receipt differs from fresh pure review')
    expected={'status':'offline-paused95-processing-plan-passed','mode':'reactivate-paused-adopted',
      'creates':0,'updates':8,'noops':52,'deletes':0,'fullPhysicalPriorEqual':True,
      'physicalPriorFullyEqual':True,'fullReviewedRefreshedPriorEqual':True,'resourceDriftResources':0,
      'allOther52PhysicalValuesExact':True,'allElevenNativeOutputDescriptorsUnchanged':True,
      'securityUnknownsAllowed':False,'noNewIAMOrService':True,'applyAuthorized':False}
    require(all(core.same(checked.get(k),v) for k,v in expected.items()),'Exact honest new paused95 gate result required')
    return True


def review_native_activation(binding, core, document, physical):
    """Re-review the genuine unused normal-plan PASS, without an adopter role."""
    pins,artifacts=binding['actualPins'],binding['artifacts']
    require(ACTIVATION_PREPARER_SHA256==REVIEWED_PREPARER_SHA256
      and pins['activationIndependentReviewerSHA256']==ACTIVATION_REVIEWER_SHA256,
      'Exact reviewed normal-plan preparer/reviewer code pins required')
    roles={'activationSavedPlanSHA256':'processing.tfplan','activationPlanJSONSHA256':'processing-plan-private.json',
      'paused60PhysicalExportSHA256':'physical60-values-private.json','activationPreparationReceiptSHA256':'summary-private.json',
      'activationGateReceiptSHA256':'summary-private.json','activationPlanStartedSHA256':'plan-started-private.json',
      'activationInputManifestSHA256':'input-evidence-sha256-private.json',
      'activationReviewInputManifestSHA256':'input-evidence-sha256-private.json',
      'activationStrictReviewSHA256':'strict-gate-review-private.json','activationHistoricalQuotaEvidenceSHA256':'quota-private.json'}
    root=BASE/'source/infra/aws/environments/personal'
    plan=root/'private/processing-paused95-saved-plan-20261025-1'
    for key,name in roles.items():
        require(pins[key]==ACTIVATION_NATIVE_FILES[name]
          and artifacts[key]=={'path':str(plan/name),'sha256':ACTIVATION_NATIVE_FILES[name]},
          'Exact unused normal-plan artifact role differs: '+key)
    # These aliases name the same genuine producer files. No separate adoption
    # record or original blocked status is manufactured.
    require(core.same(artifacts['activationPreparationReceiptSHA256'],artifacts['activationGateReceiptSHA256'])
      and core.same(artifacts['activationInputManifestSHA256'],artifacts['activationReviewInputManifestSHA256']),
      'Normal preparation/review shared-file roles must be byte/path identical')
    provenance=binding['activationReview']
    require(type(provenance) is dict and set(provenance)=={'preparer','reviewer'}
      and provenance['preparer']=={'path':str(BASE/'frozen-prepare-paused95-processing-plan-20261025-1.py'),
                                  'sha256':REVIEWED_PREPARER_SHA256}
      and provenance['reviewer']=={'path':str(BASE/'frozen-review-paused95-processing-plan-20261025-1.py'),
                                  'sha256':ACTIVATION_REVIEWER_SHA256}
      and artifacts['activationIndependentReviewerSHA256']==provenance['reviewer'],
      'Only the genuine normal preparer and pure reviewer are current provenance')
    prepmod=load(provenance['preparer']['path'],REVIEWED_PREPARER_SHA256,'reviewed_paused95_preparer_constants')
    reviewer=load(provenance['reviewer']['path'],ACTIVATION_REVIEWER_SHA256,'reviewed_paused95_pure_gate')
    require(prepmod.HEAD==pins['sourceRevision'] and prepmod.STATE_SHA==CURRENT_RAW_STATE_SHA256
      and prepmod.SERIAL==CURRENT_STATE_SERIAL and str(prepmod.STATE)==str(root/'state/terraform.tfstate')
      and prepmod.REVIEWER_SHA==ACTIVATION_REVIEWER_SHA256 and str(prepmod.REVIEWER)==provenance['reviewer']['path']
      and str(prepmod.PLAN)==str(plan),'Current95 preparer constants differ')
    for name,digest in SOURCE_GATE_SHAS.items():pinned(root/name,digest)
    for name,digest in ACTIVATION_NATIVE_FILES.items():pinned(plan/name,digest)
    manifest=json.loads(Path(artifacts['activationInputManifestSHA256']['path']).read_text())
    require(type(manifest) is dict and len(manifest)==57
      and manifest.get(str(root/'state/terraform.tfstate'))==CURRENT_RAW_STATE_SHA256
      and manifest.get(provenance['preparer']['path'])==REVIEWED_PREPARER_SHA256
      and manifest.get(provenance['reviewer']['path'])==ACTIVATION_REVIEWER_SHA256
      and manifest.get(str(plan/'quota-private.json'))==pins['activationHistoricalQuotaEvidenceSHA256'],
      'Complete genuine normal-plan input anchors differ')
    for name,digest in manifest.items():
        path=Path(name)
        require(path.is_absolute() and '..' not in path.parts and (path.is_relative_to(BASE)
          or path.is_relative_to(Path('/tmp/ecoguard-aws-tool-restore-20261024-1/terraform-data'))
          or path==Path('/tmp/ecoguard-c-personal-20261023/tools/terraform')
          or path==Path('/usr/local/aws-cli/v2/2.38.1/dist/aws'))
          and not any(v.lower() in {'.aws','credentials','token.json','application_default_credentials.json'} or v.startswith('.env') for v in path.parts),
          'Plan input escaped fixed evidence scope')
        pinned(path,digest)
    gate=load(root/'check_processing_plan.py',SOURCE_GATE_SHAS['check_processing_plan.py'],'unchanged_source47_paused95_gate')
    require(gate.LIVE_QUOTA_EVIDENCE_SHA256 is None,'Source quota default must remain inert')
    gate.LIVE_QUOTA_EVIDENCE_SHA256=pins['activationHistoricalQuotaEvidenceSHA256']
    quota=json.loads(Path(artifacts['activationHistoricalQuotaEvidenceSHA256']['path']).read_text())
    require(document.get('format_version')=='1.2' and document.get('terraform_version')=='1.17.0'
      and document.get('applyable') is True,'Native saved plan format differs')
    raw_path=Path(artifacts['paused60RawStateSHA256']['path']);raw_bytes=raw_path.read_bytes();raw=json.loads(raw_bytes)
    review_plan_shape(document,raw_addresses(raw),reviewer)
    checked=reviewer.inspect_plan(gate,document,physical,image=binding['readonly']['workerImageUri'],
      zip_filename=str(BASE/'artifacts/aws-personal-lambda-20261023-1.zip'),window_seconds=binding['context']['windowSeconds'],
      quota_evidence=quota,quota_evidence_sha256=pins['activationHistoricalQuotaEvidenceSHA256'],review_time=stamp(document['timestamp']))
    receipt=json.loads(Path(artifacts['activationStrictReviewSHA256']['path']).read_text())
    review_independent_receipt(core,reviewer,checked,receipt,document,quota)
    summary=json.loads(Path(artifacts['activationPreparationReceiptSHA256']['path']).read_text())
    expected_summary={'status':'paused95-processing60-normal-saved-plan-review-passed','sourceRevision':pins['sourceRevision'],
      'stateSHA256':CURRENT_RAW_STATE_SHA256,'serial':CURRENT_STATE_SERIAL,'lineage':pins['paused60StateLineage'],
      'planExecuted':True,'planExitCode':0,'applyExecuted':False,'stateWritten':False,'initExecuted':False,'iamModified':False,
      'cloudMutationCommandsInvoked':False,'fixtureSubmitted':False,'runtimeActivated':False,'applyAuthorized':False,
      'maximumPlanCommands':1,'automaticRetryPermitted':False,'normalRefresh':True,'refreshOnly':False,'targetUsed':False,
      'consumedPlanReplayed':False,'previousBindingUsedOnlyForImmutableSourceToolsAndTargets':True,
      'currentCheckpointReconciliationSHA256':CURRENT_RECONCILIATION_SHA256,
      'bootID':'ef7bbcb6-4608-4850-96b1-c4c002135397',
      'credentialRouteProofSHA256':pins['cloudshellCredentialRouteObservationSHA256'],
      'reviewerSHA256':ACTIVATION_REVIEWER_SHA256,'quotaReceiptSHA256':pins['activationHistoricalQuotaEvidenceSHA256'],
      'physicalExportSHA256':pins['paused60PhysicalExportSHA256'],'inputManifestSHA256':pins['activationInputManifestSHA256'],
      'startedSHA256':pins['activationPlanStartedSHA256'],'savedPlanSHA256':pins['activationSavedPlanSHA256'],
      'planJSONSHA256':pins['activationPlanJSONSHA256'],'strictReviewSHA256':pins['activationStrictReviewSHA256'],
      'managedResources':60,'creates':0,'updates':8,'noops':52,'deletes':0,'fullPhysicalPriorEqual':True,
      'fullReviewedRefreshedPriorEqual':True,'stateSourceAndEvidenceUnchanged':True,'helperSHA256':REVIEWED_PREPARER_SHA256}
    require(all(core.same(summary.get(k),v) for k,v in expected_summary.items()),'Genuine normal-plan PASS summary differs')
    expected_argv=prepmod.expected_plan_argv(str(BASE/'artifacts/aws-personal-lambda-20261023-1.zip'))
    require(expected_argv==[binding['tools']['terraform']['path'],'-chdir='+str(root),'plan','-input=false','-no-color',
      '-refresh=true','-lock-timeout=60s','-var=deployment_stage=processing-bounded','-var=adopt_upload_notifications=true',
      '-var=lambda_zip='+str(BASE/'artifacts/aws-personal-lambda-20261023-1.zip'),
      '-var=worker_image='+binding['readonly']['workerImageUri'],'-var=inference_url='+prepmod.RUN,
      '-out='+str(plan/'processing.tfplan')],'Only one exact new untargeted normal-refresh plan is reviewed')
    started=json.loads(Path(artifacts['activationPlanStartedSHA256']['path']).read_text())
    expected_started={'argv':expected_argv,'helperSHA256':REVIEWED_PREPARER_SHA256,'sourceRevision':pins['sourceRevision'],
      'stateSHA256':CURRENT_RAW_STATE_SHA256,'serial':CURRENT_STATE_SERIAL,'quotaReceiptSHA256':pins['activationHistoricalQuotaEvidenceSHA256'],
      'normalRefresh':True,'refreshOnly':False,'targetUsed':False,'maximumPlanCommands':1,'retryPermitted':False,
      'consumedPlanSHAs':sorted(prepmod.CONSUMED_PLAN_SHAS)}
    require(set(started)==set(expected_started)|{'startedAtUtc'} and all(core.same(started.get(k),v) for k,v in expected_started.items())
      and stamp(started['startedAtUtc']).replace(microsecond=0)<=stamp(document['timestamp'])
      <=stamp(summary['preparedAtUtc'])<=stamp(summary['observedAtUtc']), 'Normal invocation and success receipt time chain differ')
    invoked=json.loads((plan/'normal-refresh-plan-started.json').read_text())
    outcome=json.loads((plan/'normal-refresh-plan-outcome.json').read_text())
    require(core.same(invoked,{'argv':expected_argv,'maximumCommands':1,'retryPermitted':False}) and outcome.get('exitCode')==0
      and outcome.get('stdoutSHA256')==sha(plan/'normal-refresh-plan-stdout-private.bin')
      and outcome.get('stderrSHA256')==sha(plan/'normal-refresh-plan-stderr-private.bin'), 'Actual native normal-plan outer command/outcome differs')
    # Independently repeat the real state95 transition check from the already
    # pinned producer, without running its main or state-apply entry point.
    lib=load(prepmod.LIBRARY,prepmod.LIBRARY_SHA,'reviewed_completed_state95_library')
    recon=Path(str(prepmod.RECON));old_plan=Path(str(lib.PLAN));restore=Path(str(prepmod.RESTORE))
    prepmod.review_checkpoint_chain(lib,json.loads((recon/'summary-private.json').read_text()),raw_bytes,physical,
      json.loads((old_plan/'refresh-only-plan-private.json').read_text()),json.loads((old_plan/'physical94-values-private.json').read_text()),
      list(managed(physical['values']['root_module'])),binding['context']['targets'],
      json.loads((restore/'summary.json').read_text()),json.loads((restore/'preflight-private.json').read_text()),
      datetime.now(timezone.utc))
    return checked


def validate_binding(path, raw_sha, core, aws):
    require(ARM_REVIEWED is True,'Live arm release not independently reviewed; default blocked')
    binding=json.loads(pinned(path,raw_sha).read_text())
    template=json.loads(BINDING_TEMPLATE.read_text())
    require(set(binding['actualPins'])==set(template['actualPins']) and all(v is not None for v in binding['actualPins'].values()),'Actual pins pending')
    pins=binding['actualPins']; ctx=binding['context']; core.validate_context(ctx)
    require(ctx['activationSavedPlanSHA256']==pins['activationSavedPlanSHA256'] and ctx['windowSeconds']==pins['maximumWindowSeconds']
      and ctx['operatorUID']==os.getuid() and type(ctx['nonce']) is str and re.fullmatch('[0-9a-f]{64}',ctx['nonce']),'Context/pins/UID differ')
    require(type(pins['paused60StateSerial']) is int and type(pins['paused60StateLineage']) is str,'Current60 serial/lineage pending')
    # Every SHA named in the existing51-pin contract must bind an actual retained
    # file, including all original source/cloud/approval evidence. No invented
    # success record can be substituted without changing the reviewed binding.
    for key,value in pins.items():
        if key.endswith('SHA256'):
            artifact=binding['artifacts'][key]
            pinned(artifact['path'],value)
    require(set(binding['tools'])=={'aws','python','terraform','provider'},'Exact reviewed tool set required')
    for name,tool in binding['tools'].items():
        pinned(tool['path'],tool['sha256'])
    require(binding['tools']['aws']=={'path':'/usr/local/aws-cli/v2/2.38.1/dist/aws','sha256':'b95378674f18a78594c62334b2cca9363f4d5c71bd160f578a88b35d28335e09'}
      and binding['tools']['terraform']=={'path':'/tmp/ecoguard-c-personal-20261023/tools/terraform','sha256':'664b66cc0bcd7ed28fd27569719ccaa8a40c230b8be45060ce4d65e2852e1bcc'}
      and binding['tools']['provider']['sha256']=='9d8b78e2faf9ede57d4c146692358ebc4b6de7aeac2058ad69e971103ef4e401','Existing frozen official tool bytes differ')
    require(pins['awsCliPath']==binding['tools']['aws']['path'] and pins['awsCliSHA256']==binding['tools']['aws']['sha256'],'Pinned AWS CLI differs')
    require(pins['orchestratorHelperSHA256']==sha(Path(__file__).resolve()) and pins['watchdogHelperSHA256']==pins['orchestratorHelperSHA256'],'Driver release/helper pins differ')
    state=json.loads(Path(binding['artifacts']['paused60RawStateSHA256']['path']).read_text())
    require(state.get('lineage')==pins['paused60StateLineage'] and state.get('serial')==pins['paused60StateSerial'],'Current60 raw checkpoint differs')
    addresses=raw_addresses(state);require(len(addresses)==60,'Current adopted60 has not been established')
    document=json.loads(Path(binding['artifacts']['activationPlanJSONSHA256']['path']).read_text())
    physical=json.loads(Path(binding['artifacts']['paused60PhysicalExportSHA256']['path']).read_text())
    review_paused60_chain(binding,core)
    review_native_activation(binding,core,document,physical)
    backlog=json.loads(Path(binding['artifacts']['queueTableBacklogEvidenceSHA256']['path']).read_text())
    require(set(backlog)=={'account','region','sourceRevision','paused60StateSHA256','nonce','observedAtUtc','snapshot'}
      and backlog['account']==ACCOUNT and backlog['region']==REGION and backlog['sourceRevision']==pins['sourceRevision']
      and backlog['paused60StateSHA256']==pins['paused60RawStateSHA256'] and backlog['nonce']==ctx['nonce'],'Pinned backlog proof scope differs')
    require(0<=(datetime.now(timezone.utc)-stamp(backlog['observedAtUtc'])).total_seconds()<=3600,'Pinned backlog proof stale/future')
    aws.eligible_backlog(backlog['snapshot'])
    validate_authority(binding,core)
    fixture=load(FIXTURE_HELPER_FILE,FIXTURE_HELPER_SHA256,'reviewed_single_automatic_fixture')
    runtime=load(Path(__file__).with_name('fixture_runtime.py'),FIXTURE_RUNTIME_SHA256,'reviewed_fixture_runtime_preflight')
    bind_fixture(binding,core,fixture)
    require(type(ctx['drainPollSeconds']) in (int,float) and 1<=ctx['drainPollSeconds']<=30
      and type(ctx['propagationReadAllowanceSeconds']) in (int,float) and 0<=ctx['propagationReadAllowanceSeconds']<=120,'Drain bounds invalid')
    require(runtime.gcp_fresh(binding['gcpFreshness'],ctx),'Fresh actual GCP Run/WIF/credits guard failed')
    require(verify_funding(binding,aws),'Funding proof expired')
    sdk_support()  # validate immutable read-worker artifacts before any launch
    require((stamp(pins['fundingValidUntil'])-datetime.now(timezone.utc)).total_seconds()>=ctx['windowSeconds']+max(ctx['actualFunctionTimeouts'].values())+ctx['propagationReadAllowanceSeconds']+30,'Funding cannot cover fixed window plus launch margin')
    source=binding['source'];inventory=json.loads(Path(binding['artifacts']['sourceTreeInventorySHA256']['path']).read_text())
    root=Path(source['root'])
    require(root==BASE/'source' and inventory['sourceRevision']==pins['sourceRevision'] and type(inventory['files']) is dict,'Source inventory scope differs')
    for relative,expected in inventory['files'].items():
        rel=Path(relative); require(not rel.is_absolute() and '..' not in rel.parts and '.git' not in rel.parts,'Source inventory escaped')
        pinned(root/rel,expected)
    gitdir=root/'.git';require(gitdir.is_dir() and not gitdir.is_symlink(),'Normal detached Git source required')
    require((gitdir/'HEAD').read_text().strip()==pins['sourceRevision'],'Actual source HEAD differs (no Git command invoked)')
    tf=binding['terraform']
    root=BASE/'source/infra/aws/environments/personal'
    data=Path('/tmp/ecoguard-aws-tool-restore-20261024-1/terraform-data')
    require(tf['root']==str(root) and tf['data']==str(data) and tf['terraform']==binding['tools']['terraform']
      and tf['provider']==binding['tools']['provider'] and Path(tf['provider']['path']).parent==data/'providers/registry.terraform.io/hashicorp/aws/6.67.0/linux_amd64'
      and tf['state']==binding['artifacts']['paused60RawStateSHA256'] and tf['state']['path']==str(root/'state/terraform.tfstate')
      and tf['plan']==binding['artifacts']['activationSavedPlanSHA256']
      and tf['cliConfig']=={'path':str(BASE/'empty-terraform-cli-20261024-1.tfrc'),'sha256':hashlib.sha256(b'').hexdigest()}
      and tf['backendMetadata']['path']==str(data/'terraform.tfstate'),'Frozen Terraform state/data/config binding differs')
    pinned(tf['backendMetadata']['path'],tf['backendMetadata']['sha256'])
    backend=json.loads(Path(tf['backendMetadata']['path']).read_text()).get('backend',{})
    require(backend.get('type')=='local' and backend.get('config',{}).get('path')=='state/terraform.tfstate','Actual local backend differs')
    ids=binding['readonly']
    require(ids['workerImageUri'].startswith(f'{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/{PREFIX}-worker@sha256:')
      and re.fullmatch('[0-9a-f]{64}',ids['workerImageUri'].rsplit(':',1)[1]),'Exact private ECR digest pending')
    require(pins['ingestMappingUUID']==ctx['mappingUUIDs']['ingest'] and pins['inferMappingUUID']==ctx['mappingUUIDs']['infer'],'Mapping pins differ')
    # Full expected raw profiles are retained and hashed, not caller True flags.
    profiles=json.loads(Path(binding['artifacts']['livePreflightSnapshotSHA256']['path']).read_text())
    require(set(profiles)=={'controlProfiles','boundaries'} and set(profiles['controlProfiles'])==set(core.TARGETS),'Exact raw profile baseline required')
    raw_profiles=json.loads(Path(binding['artifacts']['functionConfigurationEvidenceSHA256']['path']).read_text())
    require(type(raw_profiles) is dict and set(raw_profiles)==set(core.TARGETS),'Full raw eight-profile evidence required')
    for target,raw in raw_profiles.items():
        immutable=aws.immutable_function_profile(target.split('-',1)[0],raw) if target.endswith('-concurrency') else raw
        require(core.same(immutable,profiles['controlProfiles'][target])
          and aws.digest(immutable)==ctx['targets'][target]['immutableProfileSHA256'],'Raw-to-reviewed immutable profile differs')
    require(sys.platform=='linux' and Path.home()==Path('/home/cloudshell-user'),'Actual AWS CloudShell Linux required')
    # Runtime environment/provider identity is still freshly checked via STS in
    # boundaries BEFORE any mutation. No credential values are written to IPC.
    return binding,profiles


def bind_fixture(binding,core,helper):
    """Same immutable shared context; never edit the original frozen helper.

    approval pin is the actual RAW HUMAN REPLY SHA, not the authority JSON SHA:
    the latter contains contextSHA and would introduce a hash cycle. The full
    action-time authority is independently checked outside this context.
    """
    ctx=binding['context'];pins=binding['actualPins']
    authority=json.loads(Path(binding['artifacts']['actionTimeApprovalRecordSHA256']['path']).read_text())
    expected={'context':core.digest(ctx),'state59':binding['historicalPaused59']['pins']['paused59RawStateSHA256'],'activation':pins['activationSavedPlanSHA256'],
      'watchdog':pins['watchdogHelperSHA256'],'funding':pins['fundingEvidenceSHA256'],
      'approval':authority['actualUserReplySHA256'],'backlog':pins['queueTableBacklogEvidenceSHA256'],
      'roleRun':pins['gcpRunMetadataEvidenceSHA256'],'source':pins['sourceTreeInventorySHA256'],'sampleProvenance':pins['fixtureLicenseEvidenceSHA256']}
    require(core.same(binding['fixturePins'],expected),'Fixture pins differ or pending; no postactivation self-hash cycle')
    require(binding['gcpFreshness']['observation']['sha256']==pins['gcpRunMetadataEvidenceSHA256'],'GCP role/Run proof differs')
    helper.PINS=copy_dict(expected)
    helper.checked(ctx)
    created=stamp(ctx['fixture']['createdAtUtc']);now=datetime.now(timezone.utc)
    require(created<=now and created+timedelta(seconds=600)>=now+timedelta(seconds=ctx['windowSeconds']-ctx['stopReserveSeconds']+30),'Fixture creation time cannot cover fixed submission window')
    return helper


def copy_dict(value):
    return json.loads(json.dumps(value,allow_nan=False))


def fixture_objects(binding,core,private,aws,store,armed,env,port,role):
    helper=bind_fixture(binding,core,load(FIXTURE_HELPER_FILE,FIXTURE_HELPER_SHA256,'reviewed_owned_fixture_'+role))
    runtime=load(Path(__file__).with_name('fixture_runtime.py'),FIXTURE_RUNTIME_SHA256,'reviewed_fixture_runtime_'+role)
    def fresh(*,required_until=None):
        remaining=max(0,armed['stopNewWorkBy']-time.monotonic())+max(binding['context']['actualFunctionTimeouts'].values())+binding['context']['propagationReadAllowanceSeconds']
        return verify_funding(binding,aws) and runtime.gcp_fresh(binding['gcpFreshness'],binding['context'],
          required_until=required_until or datetime.now(timezone.utc)+timedelta(seconds=remaining))
    def guard(action,request_sha):
        require(role=='writer','Only registered writer may submit')
        full=store.identity('writer');require(private.same(port.quiescer.proc.identity(os.getpid(),armed['nonce']),full),'Writer process changed')
        hb=store.latest_heartbeat('writer');require(hb is not None,'Writer heartbeat absent')
        heartbeat={'nonce':armed['nonce'],'contextSHA256':armed['contextSHA256'],'at':hb['at']}
        core.assert_submission_open(binding['context'],armed,port,time.monotonic,True,verify_funding(binding,aws),heartbeat)
        require(fresh() is True,'GCP freshness expired before production model path')
    transport=runtime.FixtureTransport(helper,core,binding['context'],armed,store,port.quiescer.proc,binding['tools']['aws'],env,
      role=role,before_external_write=guard,freshness_guard=fresh)
    def permit(action,request_sha):
        guard(action,request_sha)
        hb=store.latest_heartbeat('writer')
        heartbeat={'nonce':armed['nonce'],'contextSHA256':armed['contextSHA256'],'at':hb['at']}
        return core.before_fixture_write(binding['context'],armed,port,time.monotonic,True,verify_funding(binding,aws),heartbeat,action,request_sha)
    return helper,transport,permit



class SDKReadJournal:
    """Narrow append-only bridge to the existing shared-context intent store."""
    def __init__(self,store,core,context):
        self.store,self.core,self.context=store,core,context
        self.path=store.path
    def check(self):
        require(self.store.context_sha==self.core.digest(self.context) and self.store.nonce==self.context['nonce'],'SDK read journal context changed')
    def intent(self,group,request):
        self.check()
        require(type(group) is str and re.fullmatch(r'sdk:(boundary|backlog):[0-9]+-[0-9]{6}',group),'SDK group slot differs')
        require(self.store.mark_once('sdk-read:'+group,self.store.context_sha,self.store.nonce,self.core.digest(request)) is True,'SDK read group already consumed; no retry')
    def append_json(self,kind,value):
        self.check()
        require(kind in ('sdk-raw-outcome','sdk-batch-outcome'),'SDK evidence kind outside read port')
        return self.store.append_json(kind,value)


def sdk_support():
    # These are frozen read-only code/package artifacts, not caller capabilities.
    sibling=Path(__file__).resolve().parent
    bridge=load(sibling/'sdk_batch.py',SDK_BRIDGE_SHA256,'reviewed_owned_sdk_read_bridge')
    pins={'python':{'path':'/usr/local/python3.13/bin/python3','sha256':'33a0bf50d1e98dfaf4b15f342c9187cb6af4787d86c8708f846cfd8ea8498f24'},
      'worker':{'path':str(sibling/'sdk_worker.py'),'sha256':SDK_WORKER_SHA256},
      'bridge':{'path':str(sibling/'sdk_batch.py'),'sha256':SDK_BRIDGE_SHA256},
      'runtime':{'path':str(sibling/'aws_runtime.py'),'sha256':AWS_RUNTIME_SHA256},
      'sdkManifest':{'path':str(BASE/'official-cloudshell-sdk-packages-readonly-20261024-1.json'),'sha256':SDK_MANIFEST_SHA256}}
    bridge.python_tool(pins['python']['path'],pins['python']['sha256'])
    for name in ('worker','bridge','runtime','sdkManifest'):pinned(pins[name]['path'],pins[name]['sha256'])
    return bridge,pins


def objects(binding,profiles,core,private,aws,store,armed,env,role):
    proc=private.LinuxProc()
    full_watchdog=store.identity('watchdog')
    quiescer=private.Quiescer(proc,store=store,watchdog_identity=full_watchdog)
    cli=aws.FixedCLI(binding['tools']['aws'],env,store,{'context':binding['context'],'readonly':binding['readonly']},credential_route=credential_route_reference(binding))
    bridge,pins=sdk_support()
    journal=SDKReadJournal(store,core,binding['context'])
    batch=bridge.BatchTransport(aws,cli,journal,pins,proc,binding['context']['nonce'])
    reader=bridge.reader_class(aws)(cli,binding['context'],binding['readonly'],profiles['boundaries'],core,batch_transport=batch)
    activation_spec=dict(binding['terraform'])
    activation_spec.update(stateLineage=binding['actualPins']['paused60StateLineage'],stateSerial=binding['actualPins']['paused60StateSerial'],
      plannedManagedAddresses=sorted(managed(json.loads(Path(binding['artifacts']['activationPlanJSONSHA256']['path']).read_text())['planned_values']['root_module'])),
      plannedOutputs=json.loads(Path(binding['artifacts']['activationPlanJSONSHA256']['path']).read_text())['planned_values']['outputs'])
    activation=aws.SavedActivation(activation_spec,binding['context'],armed,store,env)
    port=aws.RuntimeAdapter(core,binding['context'],armed,store,reader,quiescer,activation=activation,role=role)
    return proc,reader,port


def driver_loop(context,armed,port,store,core,private,*,funding_valid,policies_valid=lambda:True,drain_supervisor=None,clock=time.monotonic,sleep=time.sleep,max_ticks=4000):
    """Explicit detached watchdog loop; tests inject every port, clock and sleep."""
    core.validate_arm(context,armed)
    require(all(type(armed[k]) in (int,float) and math.isfinite(armed[k]) and armed[k]>=0 for k in ('t0','stopNewWorkBy'))
      and clock()>=armed['t0'],'Invalid/orphaned monotonic armed times')
    previous=None
    for _ in range(max_ticks):
        full=store.identity('watchdog')
        ipc_failed=False
        try:store.publish_heartbeat('watchdog',full,clock())
        except Exception:ipc_failed=True
        try:heartbeat=store.latest_heartbeat('writer')
        except Exception:heartbeat=None;ipc_failed=True
        if heartbeat and private.core_identity(heartbeat['identity'])==armed['writerIdentity']:
            hb={'contextSHA256':armed['contextSHA256'],'nonce':armed['nonce'],'at':heartbeat['at']}
        else:hb={}
        try:stop=store.read_stop()
        except Exception:stop='verification'
        if ipc_failed:stop='verification'
        try:
            if policies_valid() is not True:stop='verification'
        except Exception:stop='verification'
        try:funds=funding_valid() is True
        except Exception:funds=False
        reason=core.watchdog_reason(context,armed,clock,hb,funds,stop)
        if previous is not None:reason=previous
        if reason:
            try:store.request_stop(reason)
            except Exception:pass  # Reducer still attempts independently owned controls.
            previous=reason
            report=core.pause_and_observe(context,armed,port,clock,reason)
            store.write_once('watchdog-pause-result.json',report)
            require(drain_supervisor is not None,'Independent full drain supervisor not bound')
            return drain_supervisor(report)
        sleep(min(1.0,context['heartbeatSeconds']/3,max(0.0,armed['stopNewWorkBy']-context['stopReserveSeconds']-clock())))
    # Hitting a finite driver safety bound is a failure, never an extension.
    store.request_stop('verification')
    report=core.pause_and_observe(context,armed,port,clock,'verification')
    store.write_once('watchdog-pause-result.json',report)
    require(drain_supervisor is not None,'Independent full drain supervisor not bound')
    return drain_supervisor(report)


def launch_spec(binding,path,raw_sha,private):
    return private.LaunchSpec(python=Path(binding['tools']['python']['path']),python_sha256=binding['tools']['python']['sha256'],
      driver=Path(__file__).resolve(),driver_sha256=sha(Path(__file__).resolve()),context_file=Path(path),context_file_sha256=raw_sha)


def actual_drain_funding(context,transport,pause,*,clock=time.monotonic,utc_now=lambda:datetime.now(timezone.utc)):
    at=pause['controlReadbackAt'];now=clock()
    require(type(at) in (int,float) and math.isfinite(at) and type(now) in (int,float) and math.isfinite(now) and now>=at,'Actual pause clock invalid')
    actual_end=at+max(context['actualFunctionTimeouts'].values())+context['propagationReadAllowanceSeconds']
    return transport.fresh(required_until=utc_now()+timedelta(seconds=max(0,actual_end-now)))


def credential_route_reference(binding):
    key='cloudshellCredentialRouteObservationSHA256'
    ref=binding['artifacts'][key]
    require(ref=={'path':str(BASE/'cloudshell-existing-container-route-metadata-20261025-7.json'),'sha256':binding['actualPins'][key]},'Exact current-VM route artifact required')
    return ref


def await_watchdog_ready(ctx,armed,store,proc,watchdog,core,private,funding_valid,heartbeat_failed,
                         *,clock=time.monotonic,sleep=time.sleep):
    # Ownership registration alone is not readiness. The watchdog publishes its
    # first heartbeat only after its existing complete initialization succeeds.
    until=min(armed['t0']+STARTUP_READINESS_SECONDS,
      armed['stopNewWorkBy']-ctx['stopReserveSeconds'])
    previous=armed['t0']
    while True:
        now=clock()
        require(type(now) in (int,float) and math.isfinite(now) and now>=previous and now<until,
          'Watchdog readiness exceeded original bounded startup window')
        require(not heartbeat_failed.is_set(),'Writer heartbeat publication failed')
        require(store.read_stop() is None and store.input_is_open(),'STOP/closed input before watchdog readiness')
        require(funding_valid() is True,'Funding invalid before watchdog readiness')
        require(core.same(store.identity('watchdog'),watchdog)
          and core.same(proc.identity(watchdog['pid'],ctx['nonce']),watchdog),
          'Registered watchdog identity is no longer alive')
        receipt=store.latest_heartbeat('watchdog')
        after=clock()
        require(type(after) in (int,float) and math.isfinite(after) and now<=after<until,
          'Watchdog readiness clock invalid or deadline passed')
        if receipt is not None:
            require(type(receipt) is dict and set(receipt)=={'identity','at'}
              and private.same(receipt['identity'],watchdog)
              and core.same(private.core_identity(receipt['identity']),armed['watchdogIdentity']),
              'Watchdog readiness ACK identity differs')
            at=receipt['at']
            require(type(at) in (int,float) and math.isfinite(at) and armed['t0']<=at<=after
              and after-at<=ctx['heartbeatSeconds'],'Watchdog readiness ACK time invalid/stale')
            return receipt
        previous=after
        sleep(min(.02,until-after))


def run_mode(args,core,private,aws,binding,profiles):
    ctx=binding['context'];logical_sha=core.digest(ctx)
    require(args.nonce==ctx['nonce'],'Process nonce differs')
    route=credential_route_reference(binding)
    env=aws.reviewed_environment(os.environ,credential_route=route)
    attempt=Path(args.attempt)
    require(attempt.is_absolute() and attempt.parent==BASE/'processing-bounded-private' and re.fullmatch(r'run-[0-9a-f]{64}',attempt.name)
      and attempt.name=='run-'+ctx['nonce'],'Attempt path differs from exact private nonce')
    parent=attempt.parent.stat()
    require(parent.st_uid==os.getuid() and parent.st_mode & 0o777==0o700,'Private attempt parent owner/mode differs')
    if args.launch:
        # pidfd signal capability must exist BEFORE any writer/activation starts.
        require(hasattr(os,'pidfd_open') and hasattr(__import__('signal'),'pidfd_send_signal'),'Linux pidfd signalling unavailable; no arm')
        store=private.PrivateStore.create(attempt,logical_sha,ctx['nonce'])
        supervisor=private.DetachedSupervisor(credential_route=route)
        full=supervisor.spawn_writer(launch_spec(binding,args.context,args.context_sha256,private),store,env)
        return {'status':'isolated-writer-started-awaiting-watchdog-ack','writerIdentity':private.core_identity(full),'activationReadinessClaimed':False}
    store=private.PrivateStore.open(attempt,logical_sha,ctx['nonce'])
    proc=private.LinuxProc()
    full=proc.identity(os.getpid(),ctx['nonce'])
    role='writer' if args.writer else 'watchdog'
    require(full is not None and full['pid']==full['pgid']==full['sid'] and full['uid']==os.getuid(),'Dedicated process session required')
    # Parent verifies/registers exact command bytes. Child waits for that fsynced
    # identity; it must not infer authorization merely from its PID/arguments.
    until=time.monotonic()+5
    while True:
        try:
            require(private.same(store.identity(role),full),'Registered process identity differs');break
        except FileNotFoundError:
            require(time.monotonic()<until,'Parent process registration not found');time.sleep(0.02)
    if args.writer:
        t0=time.monotonic()
        heartbeat_stop=threading.Event()
        heartbeat_failed=threading.Event()
        thread=None
        # Continuous heartbeats cover spawn, registration, readiness and object
        # construction as well as TF. They cannot extend T0 or authorize work.
        def heartbeat_worker():
            try:
                while not heartbeat_stop.is_set():
                    store.publish_heartbeat('writer',full,time.monotonic())
                    heartbeat_stop.wait(min(1.0,ctx['heartbeatSeconds']/3))
            except Exception:
                heartbeat_failed.set()
        try:
            store.publish_heartbeat('writer',full,t0)
            thread=threading.Thread(target=heartbeat_worker,daemon=True,name='bounded-writer-heartbeat')
            thread.start()
            wd=private.DetachedSupervisor(credential_route=route).spawn_watchdog(launch_spec(binding,args.context,args.context_sha256,private),store,env)
            armed={'contextSHA256':logical_sha,'nonce':ctx['nonce'],'t0':t0,'stopNewWorkBy':t0+ctx['windowSeconds'],
              'writerIdentity':private.core_identity(full),'watchdogIdentity':private.core_identity(wd)}
            core.validate_arm(ctx,armed);store.write_once('armed.json',armed)
            await_watchdog_ready(ctx,armed,store,proc,wd,core,private,
              lambda:verify_funding(binding,aws),heartbeat_failed,clock=time.monotonic,sleep=time.sleep)
            _proc,reader,port=objects(binding,profiles,core,private,aws,store,armed,env,'writer')
            # Fresh paused controls and all project IAM/boundaries must pass.
            for target in core.TARGETS:
                require(core.observation_state(ctx,target,reader.observe(target,ctx['callTimeoutSeconds']))=='safe','Actual adopted60 controls not paused')
            reader.unchanged_boundaries(ctx['callTimeoutSeconds'])
            backlog=reader.verify_empty_backlog(ctx['callTimeoutSeconds'])
            store.append_json('preactivation-backlog',{'observedMonotonic':time.monotonic(),'snapshot':backlog,'immediatelyBeforeActivation':True,'queueCountsAreApproximate':True})
            hb={'nonce':ctx['nonce'],'contextSHA256':logical_sha,'at':time.monotonic()}
            require(not heartbeat_failed.is_set(),'Writer heartbeat publication failed before activation')
            result=core.activate_once(ctx,armed,port,time.monotonic,verify_funding(binding,aws),hb)
            store.write_once('activation-result.json',result)
            if not result['activeVerified']:store.request_stop('partial-apply')
            if result['activeVerified']:
                helper,transport,permit=fixture_objects(binding,core,private,aws,store,armed,env,port,'writer')
                submitted=helper.submit(ctx,transport,permit)
                store.write_once('fixture-submission.json',{'writerIdentity':full,'result':submitted})
                if submitted['status']!='fixture-submitted-awaiting-production-events':
                    store.request_stop('verification')
                else:
                    # Read-only production observation. No direct Lambda/HTTP
                    # calls, secondseed/sourcePut or manualWIF test is possible.
                    while store.read_stop() is None:
                        if time.monotonic()>=armed['stopNewWorkBy']-ctx['stopReserveSeconds']:store.request_stop('deadline');break
                        observed=helper.observe_ready(ctx,transport)
                        store.append_json('fixture-observation',{'writerIdentity':full,'observedAt':time.monotonic(),'result':observed})
                        if observed['status']=='production-ready-fixture-observed':
                            store.write_once('fixture-ready.json',{'writerIdentity':full,'result':observed})
                            store.request_stop('success' if observed.get('expectedDogObserved') is True else 'verification');break
                        if not verify_funding(binding,aws):store.request_stop('funding');break
                        time.sleep(min(ctx['drainPollSeconds'],max(0,armed['stopNewWorkBy']-ctx['stopReserveSeconds']-time.monotonic())))
            writer_result={'status':'fixture-not-proven-stop-requested','activeVerified':result['activeVerified'],'automaticResubmit':False,'fullAssignmentAcceptanceVerified':False}
            try:
                ready=store.read_singleton('fixture-ready.json')['result']
                writer_result.update(status='fixture-production-ready-observed',expectedDogObserved=ready['expectedDogObserved'],realRoleToGCPPathSupportedByExecutionAndPinnedConfiguration=ready['realRoleToGCPPathSupportedByExecutionAndPinnedConfiguration'])
            except FileNotFoundError:pass
            store.write_once('fixture-writer-result.json',writer_result)
            return writer_result
        except BaseException:
            # Bootstrap failures also close the input and request STOP. Attempt
            # both independently, while preserving the original failure.
            for close in (store.close_input,lambda:store.request_stop('verification')):
                try:close()
                except Exception:pass
            raise
        finally:
            heartbeat_stop.set()
            if thread is not None and thread.ident is not None:thread.join(timeout=1)
    until=time.monotonic()+5
    while True:
        try:armed=store.read_singleton('armed.json');break
        except FileNotFoundError:
            require(time.monotonic()<until,'Armed receipt not found');time.sleep(0.02)
    _proc,reader,port=objects(binding,profiles,core,private,aws,store,armed,env,'watchdog')
    next_quota_read=[0.0]
    def quota_valid():
        now=time.monotonic()
        if now>=next_quota_read[0]:
            raw=reader.call('lambda','get-account-settings',{},now+ctx['callTimeoutSeconds'])
            aws.quota_profile(raw)
            next_quota_read[0]=time.monotonic()+ctx['quotaReadMaximumAgeSeconds']
        return True
    helper,transport,_permit=fixture_objects(binding,core,private,aws,store,armed,env,port,'watchdog')
    drain=load(Path(__file__).with_name('drain_session.py'),DRAIN_RUNTIME_SHA256,'reviewed_independent_drain_session')
    def through_drain(pause):
        # A delayed pause cannot reuse nominal stop+tail TTL; recheck the same
        # pinned raw GCP files through its actual end, never a model request.
        return drain.supervise(ctx,armed,port,store,core,helper,transport,pause,
          quota_valid=quota_valid,funding_valid=lambda:actual_drain_funding(ctx,transport,pause))
    return driver_loop(ctx,armed,port,store,core,private,funding_valid=lambda:verify_funding(binding,aws),policies_valid=quota_valid,drain_supervisor=through_drain)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--inspect',action='store_true');modes.add_argument('--launch',action='store_true')
    modes.add_argument('--writer',action='store_true');modes.add_argument('--watchdog',action='store_true')
    for flag in ('attempt','context','context-sha256','nonce'):parser.add_argument('--'+flag)
    args=parser.parse_args()
    if args.inspect or not (args.launch or args.writer or args.watchdog):
        print(json.dumps(inspect(),separators=(',',':')));return 0
    require(ARM_REVIEWED is True,'Live arm release not independently reviewed; no process/API')
    require(all(getattr(args,k) for k in ('attempt','context','context_sha256','nonce')),'Exact explicit launch fields required')
    core,private,aws=modules()
    binding,profiles=validate_binding(args.context,args.context_sha256,core,aws)
    result=run_mode(args,core,private,aws,binding,profiles)
    print(json.dumps({'status':result['status'],'contextSHA256':core.digest(binding['context']),'rawEvidencePrivate':True},separators=(',',':')))
    return 0 if result['status'] in ('isolated-writer-started-awaiting-watchdog-ack','active-profile-verified','emergency-controls-paused','application-drained-with-reviewed-evidence','fixture-production-ready-observed') else 1


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        # No raw stderr/credential-bearing exception message is exposed.
        print(json.dumps({'status':'blocked','errorType':type(error).__name__,'automaticRetryPermitted':False,'inspectPrivateEvidence':True}))
        raise SystemExit(1)
