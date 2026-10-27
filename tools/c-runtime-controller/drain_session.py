"""Independent bounded read-only drain supervision after emergency pause.

Elapsed time alone never proves drainage. No Lambda/object/model invocation,
cleanup, or second target mutation is introduced. Pure injected ports in tests.
"""
import copy
import hashlib
import json
import math
import re
import time


def require(ok,reason):
    if not ok:raise ValueError(reason)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def producer_snapshot(helper,context,transport,*,utc_epoch):
    """One complete scoped project read; count/hash only retained in receipt.

    A fresh project started empty; only this fixture's UPLOAD/DEDUP rows and
    transient ARTIFACTS ledger can exist. Unknown records, leases, in-progress
    statuses or a continuation are unresolved rather than normalized/deleted.
    """
    fixtures=context['fixture'];tables={}
    for name in ('operations','media','outbox','search','subscriptions'):
        result=helper.read(transport,helper.Request('dynamodb','Scan',{'TableName':helper.TABLES[name],'ConsistentRead':True,'Limit':100}))
        rows=result.get('Items')
        require(type(rows) is list and type(result.get('Count')) is int and result['Count']==len(rows)
          and type(result.get('ScannedCount')) is int and result['ScannedCount']==len(rows)
          and not result.get('LastEvaluatedKey') and not result.get('NextToken'),'Drain scan incomplete')
        tables[name]=[{k:helper.unwire(v) for k,v in row.items()} for row in rows]
    job,media,owner=fixtures['jobId'],fixtures['mediaId'],fixtures['ownerSub']
    op=next((row for row in tables['operations'] if row.get('operationId')==job),None)
    uploaded=next((row for row in tables['media'] if row.get('mediaId')==media),None)
    allowed_ops={job,'DEDUP#'+owner+'#'+helper.SAMPLE_SHA}
    no_unknown=not tables['subscriptions'] and all(row.get('operationId') in allowed_ops and row.get('ownerSub')==owner
      for row in tables['operations']) and all(row.get('mediaId')==media and row.get('ownerSub')==owner for row in tables['media'])
    no_unknown=no_unknown and all(row.get('mediaId')==media for row in tables['search']) and all(
      row.get('eventId') in ('INGEST:'+job+':1','NOTIFY:'+media+':2') or (type(row.get('eventId')) is str and re.fullmatch('INFER:'+job+':1:[1-9][0-9]*',row['eventId'])) for row in tables['outbox'])
    terminal=bool(op and uploaded and op.get('type')=='UPLOAD' and op.get('jobId')==job and op.get('mediaId')==media and op.get('ownerSub')==uploaded.get('ownerSub')==owner
      and type(op.get('generation')) is int and type(uploaded.get('generation')) is int
      and op.get('generation')==uploaded.get('generation')==1 and op.get('status')==uploaded.get('status') and op.get('status') in {'READY','FAILED','CANCELLED','DELETED'}
      and uploaded.get('status') in {'READY','FAILED','CANCELLED','DELETED'})
    leases=bool(op and 'leaseUntil' in op)  # Terminal producer must explicitly clear its lease; DEDUP has none.
    for row in tables['operations']:
        value=row.get('leaseUntil',0)
        leases=leases and type(value) in (int,float) and math.isfinite(value) and value==0
    return {'knownJobsTerminal':terminal,'producerLeasesExpired':bool(leases),'noUnresolvedInFlightEvidence':bool(no_unknown and terminal and leases),
      'projectDataSHA256':digest(tables),'tableCounts':{k:len(v) for k,v in tables.items()},
      'notificationBacklogMayRemainDisabled':True,'allAWSOrGCPRequestsCancelledClaimed':False,'rawRowsPersisted':False}


def supervise(context,armed,port,store,core,helper,transport,pause_receipt,*,
              monotonic=time.monotonic,utc_epoch=time.time,sleep=time.sleep,quota_valid=lambda:True,funding_valid=lambda:True):
    """Stay independent through max actual480s + pinned read allowance.

    Horizon is fixed from FIRST pause readback, never reset by drift/failures.
    Repeated core reductions consume only previously unused per-target intents;
    an already attempted target cannot be re-mutated, even if later re-enabled.
    Any observation gap/drift/unknown outcome makes final drainage unproved.
    """
    core.validate_arm(context,armed)
    start=pause_receipt['controlReadbackAt'];allowance=context['propagationReadAllowanceSeconds']
    require(type(allowance) in (int,float) and math.isfinite(allowance) and 0<=allowance<=120,'Drain read allowance outside reviewed0..120')
    require(type(context['drainPollSeconds']) in (int,float) and 1<=context['drainPollSeconds']<=30,'Drain poll bound differs')
    tail=max(context['actualFunctionTimeouts'].values())+allowance
    end=start+tail
    continuous=pause_receipt.get('status')=='emergency-controls-paused'
    latest_pause=copy.deepcopy(pause_receipt);rows=[];latest=None;previous=None
    timeout=context['callTimeoutSeconds'];previous_end=start;timing_gaps=[]
    # Each round has at most8 target reads,1 shared-deadline boundary read,
    # 5 table reads and1 quota read. A process suspension must not be counted
    # as continuous supervision merely because its two snapshots happen to match.
    read_budget=(8+1+5+1)*timeout
    for _ in range(2048):
        before=monotonic();finite_before=type(before) in (int,float) and math.isfinite(before)
        row={'at':before if finite_before else None,'controlsStillPaused':False,'producerEvidenceVerified':False}
        try:
            require(finite_before and before>=previous_end>=start,'Drain clock regressed or became invalid')
            gap=before-previous_end
            limit=timeout if not rows else context['drainPollSeconds']+timeout
            row['sincePreviousReadEndSeconds']=gap
            if gap>limit:
                continuous=False;row['supervisionGapExceeded']=True
                timing_gaps.append({'phase':'first-read-lag' if not rows else 'between-rounds','seconds':gap,'maximum':limit})
            store.publish_heartbeat('watchdog',store.identity('watchdog'),monotonic())
            require(store.input_is_open() is False and store.read_stop() is not None,'Input/STOP latch lost')
            try:guards_ok=quota_valid() is True and funding_valid() is True
            except Exception:guards_ok=False
            row['quotaAndFundingValid']=guards_ok
            if not guards_ok:continuous=False
            control_states={target:core.observation_state(context,target,port.observe(target,context['callTimeoutSeconds'])) for target in core.TARGETS}
            boundary_ok=core.same(port.unchanged_boundaries(context['callTimeoutSeconds']),context['pausedBoundaries'])
            safe=all(value=='safe' for value in control_states.values()) and boundary_ok
            row['controlsStillPaused']=safe
            if not safe:
                continuous=False
                # No automatic retry: durable intent ledger allows at most the
                # FIRST reduction of a target that became active only later.
                latest_pause=core.pause_and_observe(context,armed,port,monotonic,'verification')
                row['lateControlDriftObserved']=True
            snapshot=producer_snapshot(helper,context,transport,utc_epoch=utc_epoch())
            row.update(snapshot);row['producerEvidenceVerified']=True
            previous,latest=latest,snapshot
        except Exception as error:
            continuous=False;row['category']='unverified-drain-read';row['errorType']=type(error).__name__
            try:latest_pause=core.pause_and_observe(context,armed,port,monotonic,'verification')
            except Exception:row['lateReductionUnverified']=True
        observed=monotonic()
        valid_end=type(observed) in (int,float) and math.isfinite(observed) and finite_before and observed>=before>=previous_end
        if not valid_end:
            continuous=False;row['invalidOrRegressedReadEnd']=True
            timing_gaps.append({'phase':'invalid-or-regressed-clock'})
        else:
            row['readEndedAt']=observed;row['readRoundSeconds']=observed-before
            if observed-before>read_budget:
                continuous=False;row['readRoundBudgetExceeded']=True
                timing_gaps.append({'phase':'read-round','seconds':observed-before,'maximum':read_budget})
            previous_end=observed
        rows.append(row);store.append_json('drain-observation',row)
        if not valid_end:break  # Safe reductions were attempted above; no clock-based success.
        if observed>=end:break
        sleep(min(context['drainPollSeconds'],max(0,end-observed)))
    else:continuous=False
    # Two actual complete final snapshots must agree; no fabricated booleans
    # from elapsed time or a delayed metric. Failure/uncertainty is retained.
    stable=bool(latest and previous and latest['projectDataSHA256']==previous['projectDataSHA256'])
    evidence={'controlsStillPaused':bool(continuous and rows and rows[-1]['controlsStillPaused']),
      'knownJobsTerminal':bool(latest and latest['knownJobsTerminal']),
      'producerLeasesExpired':bool(latest and latest['producerLeasesExpired']),
      'noUnresolvedInFlightEvidence':bool(continuous and stable and latest and latest['noUnresolvedInFlightEvidence']),
      'boundedObservationWindowCovered':bool(continuous and rows and monotonic()>=end)}
    try:result=core.observe_drain(context,pause_receipt,monotonic,evidence)
    except Exception:result={'status':'drain-not-proven','inFlightCancellationClaimed':False,'cleanupInvoked':False}
    final=monotonic();valid_final=type(final) in (int,float) and math.isfinite(final) and final>=previous_end
    if not valid_final:
        continuous=False;result={'status':'drain-not-proven','inFlightCancellationClaimed':False,'cleanupInvoked':False}
    report={'status':result['status'],'contextSHA256':armed['contextSHA256'],'nonce':armed['nonce'],
      'firstPauseReadbackAt':start,'fixedDrainObservationEndsAt':end,'finalObservedAt':final if valid_final else None,
      'watchdogIndependentlyRemainedThroughTail':bool(continuous and valid_final and final>=end and stable and rows[-1]['producerEvidenceVerified']),
      'continuousSafeObservations':continuous,'supervisionTimingGaps':timing_gaps,'maximumReadRoundSeconds':read_budget,
      'drainEvidence':evidence,'coreDrainResult':result,'observations':len(rows),
      'lastPauseStatus':latest_pause.get('status'),'fixtureReadyAcceptanceProvedHere':False,
      'inFlightAWSOrGCPRequestsKilledClaimed':False,'GCPIdleProved':False,'declarativeTerraformStateReconciled':False,
      'dataOrEventCleanupInvoked':False,'mutationRetriesPermitted':False}
    store.write_once('drain-result.json',report)
    return report
