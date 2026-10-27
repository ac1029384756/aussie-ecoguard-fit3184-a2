"""Inert automatic one-image fixture port; no SDK, subprocess, timer or cloud adapter.

A future reviewed controller owns identity/source/state/funding/authority,
watchdog/deadlines, atomic intent ledger, transport and all pause operations.
This module never invokes Lambda, sends SQS messages or contacts Google.
"""
import argparse
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

ACCOUNT, REGION, PREFIX = '011154879765', 'us-east-1', 'ecoguard3184-personal'
BUCKET = PREFIX + '-' + ACCOUNT + '-media'
ROLE = 'arn:aws:iam::' + ACCOUNT + ':role/' + PREFIX + '-lambda'
RUN = 'https://ecoguard-inference-adlnb7yumq-uc.a.run.app'
INVOKER = 'ecoguard-aws-invoker@ecoguard-fit3184-a2-2026.iam.gserviceaccount.com'
MANIFEST = 'ecoguard-models-2026-10-08-v3'
ZIP_SHA = 'fafb94bf948312f1fef8998b5619567ad3c3471381a34e9e816cec87b034d9f6'
WIF_SHA = 'c8747dc930080ba76b9fede868e9a4fe0d3c165c779c6f7145913f9eb08b7815'
FEATURE = 'siglip2-base-256-animal-crop-v3:3f9f96cb90da5dbc758b01813f2f6f1aee24c1ab:rgb-exif-animal-crop-text64-lowercase-v3'
SAMPLE_SHA = '5cf614d2863ca8f86b6162c7b477fd2690adbc101816206c9e675bf36d9962d0'
SAMPLE_BYTES = 143120
SAMPLE_PATH = Path('/home/cloudshell-user/ecoguard-c-personal-20261023/artifacts/commons-cc0-dog-original.jpg')
TABLES = {n: PREFIX + '-' + n for n in ('media', 'operations', 'search', 'subscriptions', 'outbox')}
# These are future actual evidence hashes, not the historical55/ECR checkpoint.
PINS = {k: None for k in ('context', 'state59', 'activation', 'watchdog', 'funding', 'approval', 'backlog', 'roleRun', 'source', 'sampleProvenance')}


def require(value, reason):
    if not value:
        raise ValueError(reason)


def exact(a, b):
    if type(a) is not type(b): return False
    if isinstance(a, dict): return a.keys() == b.keys() and all(exact(a[k], b[k]) for k in a)
    if isinstance(a, list): return len(a) == len(b) and all(exact(x, y) for x, y in zip(a, b))
    return a == b


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class Request:
    service: str
    operation: str
    params: dict
    body: bytes | None = None
    max_response_bytes: int = 2 * 1024**2

    def fingerprint(self):
        return digest({'service': self.service, 'operation': self.operation, 'params': self.params,
            'bodySHA256': hashlib.sha256(self.body).hexdigest() if self.body is not None else None,
            'maxResponseBytes': self.max_response_bytes})


def wire(value):
    if value is None: return {'NULL': True}
    if type(value) is bool: return {'BOOL': value}
    if type(value) is int: return {'N': str(value)}
    if type(value) is str: return {'S': value}
    if isinstance(value, list): return {'L': [wire(v) for v in value]}
    if isinstance(value, dict): return {'M': {k: wire(v) for k, v in value.items()}}
    raise ValueError('Unsupported seed value type')


def document(value): return {k: wire(v) for k, v in value.items()}


def unwire(value):
    require(isinstance(value, dict) and len(value) == 1, 'Malformed DynamoDB value')
    kind, v = next(iter(value.items()))
    if kind == 'M': return {k: unwire(x) for k, x in v.items()}
    if kind == 'L': return [unwire(x) for x in v]
    if kind == 'N':
        n = float(v); require(math.isfinite(n), 'Nonfinite number'); return int(n) if n.is_integer() else n
    if kind == 'S': require(type(v) is str, 'Malformed string'); return v
    if kind == 'BOOL': require(type(v) is bool, 'Malformed boolean'); return v
    require(kind == 'NULL' and v is True, 'Unreviewed DynamoDB type'); return None


def rows(fixture):
    """Exact Service.create_upload + repository.transact initial rows, _rev1.

    Offline regression compares these to the real production Service with its
    clock/identifier fixed, using only MemoryRepository/MemoryStorage.
    """
    owner, job, media, created = (fixture[k] for k in ('ownerSub', 'jobId', 'mediaId', 'createdAtUtc'))
    parsed = datetime.fromisoformat(created.replace('Z', '+00:00'))
    require(parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0, 'Fixture time must be UTC')
    require(created == parsed.isoformat(timespec='microseconds').replace('+00:00', 'Z'), 'Use production UTC timestamp spelling')
    require(re.fullmatch(r'[0-9a-f]{32}', job) and re.fullmatch(r'[0-9a-f]{32}', media) and job != media, 'Use distinct production-format IDs')
    require(re.fullmatch(r'[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}', owner), 'Explicit synthetic owner UUID required')
    source = 'incoming/library/' + job
    meta = {'filename': 'commons-cc0-dog-original.jpg', 'contentType': 'image/jpeg', 'sizeBytes': SAMPLE_BYTES, 'sha256': SAMPLE_SHA, 'fileType': 'image'}
    common = {'generation': 1, '_rev': 1}
    return {'media': {**meta, **common, 'mediaId': media, 'ownerSub': owner, 'visibility': 'private', 'status': 'UPLOADING', 'uploadedAt': created, 'observedAt': created,
        'originalKey': source, 'jobId': job, 'recordVersion': 1, 'autoTags': [], 'autoCounts': {}, 'manualAdded': [], 'manualRemoved': [], 'tags': [], 'counts': {}, 'objectKeys': [source]},
        'operation': {**meta, **common, 'operationId': job, 'jobId': job, 'type': 'UPLOAD', 'ownerSub': owner, 'mediaId': media, 'sourceKey': source,
        'status': 'UPLOADING', 'attemptId': 0, 'createdAt': created, 'uploadExpiresAt': int(parsed.timestamp()) + 600, 'manifestVersion': MANIFEST},
        'dedup': {'operationId': 'DEDUP#' + owner + '#' + SAMPLE_SHA, 'type': 'DEDUP', 'mediaId': media, 'ownerSub': owner, '_rev': 1}}


def seed_request(fixture):
    values = rows(fixture)
    return Request('dynamodb', 'TransactWriteItems', {'ClientRequestToken': fixture['jobId'], 'TransactItems': [
        {'Put': {'TableName': TABLES[table], 'Item': document(values[name]), 'ConditionExpression': 'attribute_not_exists(#pk)', 'ExpressionAttributeNames': {'#pk': pk}}}
        for name, table, pk in (('media', 'media', 'mediaId'), ('operation', 'operations', 'operationId'), ('dedup', 'operations', 'operationId'))]})


def source_params(fixture):
    return {'Bucket': BUCKET, 'Key': 'incoming/library/' + fixture['jobId'], 'ExpectedBucketOwner': ACCOUNT,
        'ContentType': 'image/jpeg', 'ContentLength': SAMPLE_BYTES,
        'ChecksumSHA256': base64.b64encode(bytes.fromhex(SAMPLE_SHA)).decode(), 'IfNoneMatch': '*'}


def request_hashes(fixture):
    # The source fingerprint is known without reading the future remote file.
    return {'seed': seed_request(fixture).fingerprint(), 'source-put': digest({'service': 's3', 'operation': 'PutObject',
        'params': source_params(fixture), 'bodySHA256': SAMPLE_SHA, 'maxResponseBytes': 2 * 1024**2})}


def checked(context):
    require(all(isinstance(v, str) and re.fullmatch(r'[0-9a-f]{64}', v) for v in PINS.values()), 'Actual future pins pending')
    require(digest(context) == PINS['context'] and isinstance(context.get('pins'), dict)
        and all(context['pins'].get(k) == v for k, v in PINS.items() if k != 'context'), 'Immutable reviewed context differs')
    require(context.get('recordType') == 'reviewed-production-automatic-fixture-v1', 'Wrong context type')
    required = {'status': 'active-processing-context-verified', 'stage': 'processing-bounded', 'runtimeEnabled': False,
        'executionRoleARN': ROLE, 'zipSHA256': ZIP_SHA, 'publicWIFSHA256': WIF_SHA, 'runURL': RUN, 'soleInvoker': INVOKER,
        'restrictedAWSRoleTrustVerified': True, 'privateRunIAMVerified': True, 'ingestImageAndSourceVerified': True,
        'allOtherEntryPointsOff': True, 'syntheticOwnerNotCognitoLogin': True}
    require(exact(context.get('proof'), required), 'Controller real-role/Run/source/active-profile proof absent')
    approval = {'status': 'explicit-action-time-automatic-test-approved', 'maximumSeedTransactions': 1, 'maximumSourcePutCalls': 1,
        'manualLambdaInvocations': 0, 'operatorModelRequests': 0, 'productionIncomingDeletionAuthorized': True,
        'rekognitionImageEntryAuthorized': True, 'retainedFixtureCleanupAuthorized': False, 'emailAuthorized': False}
    require(exact(context.get('authority'), approval), 'Exact future test scope not approved')
    require(context.get('samplePath') == str(SAMPLE_PATH), 'Future sample path differs')
    require(context.get('fixtureSourceSHA256') == SAMPLE_SHA and context.get('fixtureBytes') == SAMPLE_BYTES, 'Reviewed fixture input differs')
    rows(context['fixture'])
    require(isinstance(context.get('nonce'), str) and re.fullmatch(r'[0-9a-f]{64}', context['nonce']), 'Missing unique controller nonce')
    require(exact(context.get('fixtureRequestSHA256'), request_hashes(context['fixture'])), 'Fixture request fingerprints differ')
    return context['fixture']


def read(transport, request):
    response = transport(request)
    require(response.get('ok') is True and isinstance(response.get('data'), dict), 'Read failed/uncertain; do not retry mutation')
    return response['data']


def read_backlog(transport):
    """Whole five project tables and8 queue/DLQ attributes; never ReceiveMessage.

    Count/hash only in returned report; do not persist raw unrelated records.
    SQS counts are approximate, so this is evidence, not a queue-emptiness proof.
    """
    tables, queues = {}, {}
    complete = True
    for name, table in TABLES.items():
        cursor, count, h = None, 0, hashlib.sha256()
        for _ in range(8):
            params = {'TableName': table, 'ConsistentRead': True, 'Limit': 100}
            if cursor: params['ExclusiveStartKey'] = cursor
            value = read(transport, Request('dynamodb', 'Scan', params))
            items = value.get('Items')
            require(isinstance(items, list) and type(value.get('Count')) is int and value['Count'] == len(items)
                and type(value.get('ScannedCount')) is int and value['ScannedCount'] == len(items), 'Incomplete/malformed table scan')
            count += len(items); h.update(json.dumps(items, sort_keys=True, separators=(',', ':')).encode())
            cursor = value.get('LastEvaluatedKey')
            require(cursor is None or isinstance(cursor, dict), 'Malformed table continuation key')
            if not cursor: break
        else: complete = False
        tables[name] = {'items': count, 'complete': not bool(cursor), 'observedItemsSHA256': h.hexdigest()}
    for name in ('ingest', 'infer', 'delete', 'notify'):
        for suffix in ('', '-dlq'):
            queue = PREFIX + '-' + name + suffix
            attrs = read(transport, Request('sqs', 'GetQueueAttributes', {'QueueUrl': f'https://sqs.{REGION}.amazonaws.com/{ACCOUNT}/{queue}',
                'AttributeNames': ['QueueArn', 'ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesNotVisible', 'ApproximateNumberOfMessagesDelayed']}))['Attributes']
            require(attrs.get('QueueArn') == f'arn:aws:sqs:{REGION}:{ACCOUNT}:{queue}', 'Queue scope differs')
            keys = ['ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesNotVisible', 'ApproximateNumberOfMessagesDelayed']
            require(all(type(attrs.get(k)) is str and re.fullmatch(r'0|[1-9][0-9]*', attrs[k]) for k in keys), 'Queue counts missing/malformed')
            queues[name + suffix] = {k: int(attrs[k]) for k in keys}
    empty = complete and all(v['items'] == 0 and v['complete'] for v in tables.values()) and all(all(n == 0 for n in v.values()) for v in queues.values())
    return {'complete': complete, 'allFiveTablesAndEightQueuesObserved': True, 'freshProjectEligible': empty,
        'tables': tables, 'queues': queues, 'queueCountsAreApproximate': True}


def submit(context, transport, before_write):
    """Exactly2 possible typed writes. Controller owns the durable once ledger.

    before_write(action,fingerprint) must atomically reserve this fixture attempt
    and persist each intent BEFORE returning its strict permit; reentry refuses.
    It also checks same context/nonce, armed ACK, noSTOP, funding and time margin.
    The transport must journal outcome before the next permit can be issued.
    """
    fixture = checked(context)
    require(SAMPLE_PATH.is_absolute() and SAMPLE_PATH.is_file() and not any(p.is_symlink() for p in (SAMPLE_PATH, *SAMPLE_PATH.parents)), 'Missing/unsafe candidate image')
    with SAMPLE_PATH.open('rb') as f: body = f.read(SAMPLE_BYTES + 1)
    require(len(body) == SAMPLE_BYTES and hashlib.sha256(body).hexdigest() == SAMPLE_SHA, 'Actual uploaded fixture bytes differ')
    backlog = read_backlog(transport)
    require(backlog['freshProjectEligible'], 'Project backlog nonempty/incomplete; no seed/upload')
    source = rows(fixture)['operation']['sourceKey']
    head = read(transport, Request('s3', 'HeadObject', {'Bucket': BUCKET, 'Key': source, 'ExpectedBucketOwner': ACCOUNT, 'ChecksumMode': 'ENABLED'}))
    require(exact(head, {'exists': False, 'verifiedHTTPStatus': 404}), 'Source absence not verified; no overwrite')
    requests = [('seed', seed_request(fixture)), ('source-put', Request('s3', 'PutObject', source_params(fixture), body))]
    outcomes = []
    for phase, request in requests:
        require(digest(context) == PINS['context'], 'Reviewed context changed during submission')
        permit = before_write(phase, request.fingerprint())
        require(exact(permit, {'allowed': True, 'contextSHA256': PINS['context'], 'action': phase,
            'requestSHA256': request.fingerprint(), 'nonce': context['nonce']}), 'Missing durable controller permit')
        require(digest(context) == PINS['context'], 'Reviewed context changed during permit')
        try: response = transport(request)
        except Exception as error:
            return {'status': 'fixture-submission-outcome-uncertain', 'phase': phase, 'errorType': type(error).__name__, 'automaticResubmit': False, 'outcomes': outcomes}
        outcomes.append({'phase': phase, 'ok': response.get('ok') is True, 'requestSHA256': request.fingerprint()})
        if response.get('ok') is not True:
            return {'status': 'fixture-submission-not-confirmed', 'phase': phase, 'automaticResubmit': False, 'outcomes': outcomes}
    return {'status': 'fixture-submitted-awaiting-production-events', 'seedTransactions': 1, 'sourcePutCalls': 1, 'automaticResubmit': False,
        'manualLambdaInvocations': 0, 'operatorModelRequests': 0, 'outerCallsAreNotGlobalNetworkAttemptBounds': True, 'outcomes': outcomes}


def get_item(transport, table, key):
    value = read(transport, Request('dynamodb', 'GetItem', {'TableName': TABLES[table], 'Key': document(key), 'ConsistentRead': True}))
    return {k: unwire(v) for k, v in value['Item'].items()} if 'Item' in value else None


def observe_ready(context, transport):
    """One bounded read snapshot, not a poll loop, pause proof or full acceptance.

    Controller transport bounds each read and stops S3 data reads at STOP. A403
    after emergency data denial cannot be treated as a source404 or lifted here.
    """
    f = checked(context); job, media_id, owner = f['jobId'], f['mediaId'], f['ownerSub']
    op = get_item(transport, 'operations', {'operationId': job}); media = get_item(transport, 'media', {'mediaId': media_id})
    if not op or not media or op.get('status') != 'READY' or media.get('status') != 'READY':
        states = {'UPLOADING', 'QUEUED', 'PREPROCESSING', 'PREPROCESSED', 'INFERRING', 'READY', 'FAILED', 'CANCELLED', 'DELETED', 'DELETING'}
        safe_status = lambda item: item.get('status') if item and item.get('status') in states else 'unreviewed' if item else None
        return {'status': 'not-ready', 'operationStatus': safe_status(op), 'mediaStatus': safe_status(media),
            'automaticRetry': False, 'fullAssignmentAcceptanceVerified': False}
    require(op.get('type') == 'UPLOAD' and op.get('jobId') == job and op.get('mediaId') == media_id and op.get('ownerSub') == media.get('ownerSub') == owner
        and type(op.get('generation')) is int and type(media.get('generation')) is int and op['generation'] == media['generation'] == 1 and media.get('visibility') == 'private' and media.get('jobId') == job
        and op.get('manifestVersion') == media.get('modelVersion') == MANIFEST and type(media.get('recordVersion')) is int and media['recordVersion'] == 2
        and type(op.get('attemptId')) is int and op['attemptId'] >= 2, 'READY identity/generation/model/attempt differs')
    require(type(op.get('_rev')) is int and op['_rev'] >= 6 and type(media.get('_rev')) is int and media['_rev'] >= 4, 'Normal production revisions not observed')
    frames = op.get('frames', []); attempt = op['attemptId']
    require(len(frames) == 1 and frames[0].get('frameId') == '0' and type(frames[0].get('timestampSeconds')) in (int, float) and frames[0]['timestampSeconds'] == 0
        and isinstance(frames[0].get('entryLabels'), list) and type(frames[0].get('entryModelVersion')) is str
        and frames[0]['entryModelVersion'] not in ('', 'unknown'), 'Actual image/Rekognition entry evidence absent')
    prefix = f'derived/{media_id}/1/'
    match = re.fullmatch(re.escape(prefix) + r'([1-9][0-9]*)/frame-0[.]jpg', frames[0].get('key', ''))
    require(match and int(match[1]) < attempt, 'Production ingest-frame attempt path differs')
    require(isinstance(frames[0].get('sha256'), str) and re.fullmatch(r'[0-9a-f]{64}', frames[0]['sha256']), 'Production frame hash missing')
    ingest_attempt = int(match[1]); thumb = prefix + str(ingest_attempt) + '/thumbnail.jpg'
    kind = media.get('classification'); require(kind in ('pet', 'invasive', 'mixed', 'uncertain'), 'Classification differs')
    target = f'library/{kind}/{owner}/{media_id}/1/{attempt}/original'
    feature_key = prefix + f'inference-{attempt}/features.json'
    require(media.get('originalKey') == target and media.get('featureKey') == feature_key and media.get('thumbnailKey') == thumb, 'Produced keys escape the exact fixture')
    require(type(media.get('counts')) is dict and exact(media['counts'], media.get('autoCounts')) and all(type(n) is int and n >= 0 for n in media['counts'].values()), 'Result counts malformed')
    events = {}
    for kind, entity, event_id in [('INGEST', job, f'INGEST:{job}:1'), ('INFER', job, f'INFER:{job}:1:{ingest_attempt}'), ('NOTIFY', media_id, f'NOTIFY:{media_id}:2')]:
        event = get_item(transport, 'outbox', {'eventId': event_id})
        require(event and event.get('kind') == kind and event.get('entityId') == entity and type(event.get('generation')) is int and event['generation'] == 1
            and event.get('status') in ('PENDING', 'SENT') and (kind != 'INFER' or event['status'] == 'SENT'), 'Automatic outbox evidence differs')
        events[kind] = event['status']
    require(get_item(transport, 'operations', {'operationId': f'ARTIFACTS#{job}#1#{attempt}'}) is None, 'Unfinished production artifacts ledger')
    for key in (target, thumb, frames[0]['key']):
        head = read(transport, Request('s3', 'HeadObject', {'Bucket': BUCKET, 'Key': key, 'ExpectedBucketOwner': ACCOUNT, 'ChecksumMode': 'ENABLED'}))
        require(head.get('exists') is True and type(head.get('ContentLength')) is int and 0 < head['ContentLength'] <= 20 * 1024**2, 'Produced object missing/oversized')
        if key == frames[0]['key']:
            require(head.get('ChecksumSHA256') == base64.b64encode(bytes.fromhex(frames[0]['sha256'])).decode(), 'Preprocessed frame checksum differs')
        if key == target:
            require(head['ContentLength'] == SAMPLE_BYTES and head.get('ChecksumSHA256') == base64.b64encode(bytes.fromhex(SAMPLE_SHA)).decode(), 'Archived original bytes/checksum differ')
    value = read(transport, Request('s3', 'GetObject', {'Bucket': BUCKET, 'Key': feature_key, 'ExpectedBucketOwner': ACCOUNT}, max_response_bytes=2 * 1024**2))
    body = value.get('body'); require(type(body) is bytes and len(body) <= 2 * 1024**2, 'Feature body unbounded/missing')
    features = json.loads(body).get('features'); require(isinstance(features, list) and 1 <= len(features) <= 32, 'Feature document empty/oversized')
    require(all(x.get('featureVersion') == FEATURE and x.get('species') in ('cat', 'dog') and len(x.get('vector', [])) == 768
        and all(type(n) in (int, float) and math.isfinite(n) for n in x['vector']) for x in features), 'Locked feature version/vector differs')
    index = get_item(transport, 'search', {'scopeSpecies': 'USER#' + owner + '#_all', 'observedAtMediaId': f['createdAtUtc'] + '#' + media_id})
    require(index and index.get('mediaId') == media_id, 'Exact private result index missing')
    source = read(transport, Request('s3', 'HeadObject', {'Bucket': BUCKET, 'Key': 'incoming/library/' + job, 'ExpectedBucketOwner': ACCOUNT, 'ChecksumMode': 'ENABLED'}))
    require(exact(source, {'exists': False, 'verifiedHTTPStatus': 404}), 'Production incoming cleanup not observed; no cleanup by this helper')
    return {'status': 'production-ready-fixture-observed', 'outboxStates': events, 'attemptId': attempt, 'featureCount': len(features),
        'featureBodySHA256': hashlib.sha256(body).hexdigest(), 'expectedDogObserved': media['counts'].get('dog', 0) >= 1 and any(x['species'] == 'dog' for x in features),
        'realRoleToGCPPathSupportedByExecutionAndPinnedConfiguration': True, 'runtimeSTSArnDirectlyObserved': False,
        'operatorModelRequests': 0, 'manualLambdaInvocations': 0, 'productionIncomingHead404Observed': True,
        'allIncomingVersionsAbsentProven': False, 'finalPauseVerified': False, 'fullAssignmentAcceptanceVerified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--inspect', action='store_true'); parser.parse_args()
    print(json.dumps({'status': 'draft-inert', 'actualPinsPending': all(v is None for v in PINS.values()), 'transportAdapterImplemented': False,
        'cloudCalled': False, 'processStarted': False, 'fixtureWritten': False, 'runtimeActivated': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
