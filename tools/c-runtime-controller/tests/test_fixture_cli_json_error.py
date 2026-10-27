"""Injected runner/store/clock only: no real processes, credentials, threads or cloud."""
import ast
import copy
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent.parent
BASE = HERE


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


R = load('json_head_fixture_candidate', HERE / 'fixture_runtime.py')
H = load('json_head_frozen_fixture', HERE / 'reference/automatic_fixture_DRAFT.py')
C = load('json_head_core', HERE / 'bounded_controller_lowquota.py')
EXAMPLES = json.loads((HERE / 'tests/fixtures/cli2381-head-error-examples.json').read_text())
BASELINE = json.loads((HERE / 'tests/fixtures/fixture-runtime-before-json-error-fix.json').read_text())

def official_error(kind, code='404', message='Not Found'):
    if kind == 'legacy':
        return 254, EXAMPLES['legacy404'].encode()
    if code == '404' and message == 'Not Found':
        return 254, EXAMPLES['json404'].encode()
    return 254, (json.dumps({'Code': code, 'Message': message}, indent=4) + '\n').encode()
FIXTURE = {'ownerSub': '00000000-0000-4000-8000-000000000001', 'jobId': '1' * 32,
           'mediaId': '2' * 32, 'createdAtUtc': '2026-10-25T08:00:00.000000Z'}


def ast_fingerprint(node):
    # Python 3.14 ast.dump omits optional empty fields; retain all real structure.
    def canonical(value):
        if isinstance(value, ast.AST):
            return [type(value).__name__, [[name, canonical(item)] for name, item in ast.iter_fields(value)
                                          if (item is not None and item != []) or (isinstance(value, ast.Constant) and name == 'value')]]
        if isinstance(value, list):
            return [canonical(item) for item in value]
        if isinstance(value, bytes):
            return ['bytes-literal', value.hex()]
        return value
    return hashlib.sha256(json.dumps(canonical(node), separators=(',', ':'), allow_nan=False).encode()).hexdigest()


class Store:
    def __init__(self, context, identity, path):
        self.context_sha = C.digest(context)
        self.nonce = context['nonce']
        self.full = identity
        self.path = path
        self.records = {}
        self.rows = []
        self.open = True
        self.stop = None

    def identity(self, role): return copy.deepcopy(self.full[role])
    def input_is_open(self): return self.open
    def read_stop(self): return self.stop
    def read_json(self, name): return copy.deepcopy(self.records[name])
    def read_singleton(self, name): return self.read_json(name)
    def write_once(self, name, value):
        if name in self.records: return False
        self.records[name] = copy.deepcopy(value)
        return True
    def mark_once(self, action, context_sha, nonce, request=None):
        assert context_sha == self.context_sha and nonce == self.nonce
        return self.write_once('intent-' + hashlib.sha256(action.encode()).hexdigest() + '.json',
                               {'action': action, 'requestSHA256': request})
    def append_json(self, kind, row): self.rows.append((kind, copy.deepcopy(row)))


class JSONHeadTransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        path = Path(self.tmp.name).resolve()
        tool = path / 'never-executed-aws'
        tool.write_bytes(b'SYNTHETIC TOOL; NEVER EXECUTED')
        self.tool = {'path': str(tool), 'sha256': R.sha(tool)}
        self.context = {'nonce': 'a' * 64, 'fixture': copy.deepcopy(FIXTURE),
                        'fixtureRequestSHA256': H.request_hashes(FIXTURE), 'callTimeoutSeconds': 10}
        self.armed = {'contextSHA256': C.digest(self.context), 'nonce': self.context['nonce'], 'stopNewWorkBy': 600}
        self.identities = {role: {'pid': pid, 'pgid': pid, 'sid': pid, 'uid': 1000, 'startTicks': 100,
                                  'bootID': '00000000-0000-0000-0000-000000000001',
                                  'cmdlineSHA256': 'b' * 64, 'nonce': self.context['nonce']}
                           for role, pid in [('writer', 2000), ('watchdog', 3000)]}
        self.store = Store(self.context, self.identities, path)
        self.proc = SimpleNamespace(identity=lambda pid, nonce: copy.deepcopy(self.identities['writer' if pid == 2000 else 'watchdog']))
        self.env = {'AWS_MAX_ATTEMPTS': '1', 'AWS_REGION': H.REGION, 'AWS_DEFAULT_REGION': H.REGION,
                    'AWS_IGNORE_CONFIGURED_ENDPOINT_URLS': 'true', 'AWS_CONFIG_FILE': '/dev/null',
                    'AWS_SHARED_CREDENTIALS_FILE': '/dev/null', 'AWS_SECRET_ACCESS_KEY': 'SYNTHETIC_NEVER_EXPORT'}
        self.head = H.Request('s3', 'HeadObject', {'Bucket': H.BUCKET, 'Key': 'incoming/library/' + FIXTURE['jobId'],
                                                 'ExpectedBucketOwner': H.ACCOUNT, 'ChecksumMode': 'ENABLED'})
        self.calls = []

    def transport(self, response=None, *, role='writer', fresh=True, raises=None):
        def run(argv, **kwargs):
            self.calls.append((copy.deepcopy(argv), kwargs))
            if raises is not None: raise raises
            return response or SimpleNamespace(returncode=0, stdout=b'{}', stderr=b'')
        return R.FixtureTransport(H, C, self.context, self.armed, self.store, self.proc, self.tool, self.env,
                    role=role, before_external_write=lambda *args: None, freshness_guard=lambda: fresh,
                    run=run, monotonic=lambda: 100.0,
                    utc_now=lambda: datetime(2026, 10, 25, 8, 1, tzinfo=timezone.utc),
                    self_pid=2000 if role == 'writer' else 3000)

    def expected_argv(self, request, sample=None):
        # Frozen CLI wire contract, including original one-call bounds.
        service = 's3api' if request.service == 's3' else request.service
        operation = {'Scan': 'scan', 'GetQueueAttributes': 'get-queue-attributes',
                     'TransactWriteItems': 'transact-write-items', 'PutObject': 'put-object'}[request.operation]
        argv = [self.tool['path'], service, operation, '--cli-input-json',
                json.dumps(request.params, separators=(',', ':'), allow_nan=False),
                '--region', H.REGION, '--output', 'json', '--no-cli-pager', '--no-cli-auto-prompt',
                '--no-paginate', '--cli-connect-timeout', '10', '--cli-read-timeout', '10']
        return argv + (['--body', str(sample)] if sample else [])

    def permit(self, request, phase):
        self.store.mark_once('fixture:' + phase, self.armed['contextSHA256'], self.armed['nonce'], request.fingerprint())

    def test_original_official_json_404_and_exact_head_argv(self):
        rc, stderr = official_error('json')
        self.assertEqual(self.transport(SimpleNamespace(returncode=rc, stdout=b'', stderr=stderr))(self.head),
                         {'ok': True, 'data': {'exists': False, 'verifiedHTTPStatus': 404}})
        argv, kwargs = self.calls[0]
        self.assertEqual(argv[-2:], ['--cli-error-format', 'json'])
        self.assertEqual(json.loads(argv[argv.index('--cli-input-json') + 1]), self.head.params)
        self.assertFalse(kwargs['shell'])
        self.assertEqual(kwargs['timeout'], 10.0)
        self.assertEqual(self.store.records, {})

    def test_403_auth_nosuchbucket_and_mismatch_fail_closed_with_safe_diagnostics(self):
        for code, message in [('403', 'Forbidden'), ('NoSuchBucket', 'The specified bucket does not exist'),
                              ('AuthFailure', 'SYNTHETIC_NEVER_EXPORT'), ('404', 'Different message')]:
            with self.subTest(code=code):
                rc, stderr = official_error('json', code, message)
                answer = self.transport(SimpleNamespace(returncode=rc, stdout=b'', stderr=stderr))(self.head)
                self.assertFalse(answer['ok'])
                row = self.store.rows[-1][1]
                self.assertEqual(row['diagnosticCategory'], 'head-service-error-not-absence')
                self.assertEqual(row['stderrBytes'], len(stderr))
                self.assertEqual(row['stderrSHA256'], hashlib.sha256(stderr).hexdigest())
                self.assertNotIn('SYNTHETIC_NEVER_EXPORT', json.dumps(self.store.rows))
        self.assertEqual(self.store.records, {})

    def test_duplicate_nonfinite_extra_warning_utf8_oversize_and_missing_body_rejected(self):
        for stderr in [b'{"Code":"403","Code":"404","Message":"Not Found"}',
                       b'{"Code":"404","Message":"Not Found","extra":NaN}',
                       b'{"Code":"404","Message":"Not Found","extra":1}',
                       b'{"Code":404,"Message":"Not Found"}', b'{"Code":"404","Message":false}',
                       b'warning\n{"Code":"404","Message":"Not Found"}',
                       b'{"Code":"404","Message":"Not Found"} trailing', b'\xff', b'NaN',
                       b'null', b'[]', b'', None, b' ' * 16385]:
            with self.subTest(kind=type(stderr).__name__, size=len(stderr) if type(stderr) is bytes else None):
                self.assertFalse(self.transport(SimpleNamespace(returncode=254, stdout=b'', stderr=stderr))(self.head)['ok'])
                self.assertIn('diagnosticCategory', self.store.rows[-1][1])
        rc, stderr = official_error('legacy')
        self.assertFalse(self.transport(SimpleNamespace(returncode=rc, stdout=b'', stderr=stderr))(self.head)['ok'])
        for stdout in (b'{}', b' ', None):
            self.assertFalse(self.transport(SimpleNamespace(returncode=254, stdout=stdout, stderr=b'{"Code":"404","Message":"Not Found"}'))(self.head)['ok'])
        for rc in (1, 253, 255, True):
            self.assertFalse(self.transport(SimpleNamespace(returncode=rc, stdout=b'', stderr=b'{"Code":"404","Message":"Not Found"}'))(self.head)['ok'])

    def test_successful_source_and_derived_metadata_unchanged(self):
        data = {'ContentLength': 10, 'ChecksumSHA256': 'SYNTHETIC', 'Metadata': {}}
        for key in ('incoming/library/' + FIXTURE['jobId'], 'derived/' + FIXTURE['mediaId'] + '/1/1/frame-0.jpg'):
            request = H.Request('s3', 'HeadObject', {**self.head.params, 'Key': key})
            result = SimpleNamespace(returncode=0, stdout=json.dumps(data).encode(), stderr=b'')
            self.assertEqual(self.transport(result)(request), {'ok': True, 'data': {'exists': True, **data}})
        self.assertEqual(self.store.records, {})

    def test_non_head_scan_and_queue_argv_unchanged(self):
        requests = [H.Request('dynamodb', 'Scan', {'TableName': H.TABLES['operations'], 'ConsistentRead': True, 'Limit': 100}),
                    H.Request('sqs', 'GetQueueAttributes', {'QueueUrl': f'https://sqs.{H.REGION}.amazonaws.com/{H.ACCOUNT}/{H.PREFIX}-ingest',
                       'AttributeNames': ['QueueArn', 'ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesNotVisible', 'ApproximateNumberOfMessagesDelayed']})]
        for request in requests:
            self.transport()(request)
            new = self.calls[-1][0]
            self.assertEqual(new, self.expected_argv(request))
            self.assertNotIn('--cli-error-format', new)

    def test_exact_seed_and_conditional_put_unchanged_and_once(self):
        # Explicit synthetic bytes keep actual image payloads out of Git.
        sample = self.store.path / 'synthetic-fixture.jpg'
        body = b'SYNTHETIC FIXTURE BODY; NO PRODUCT IMAGE'
        sample.write_bytes(body)
        with patch.object(H, 'SAMPLE_SHA', hashlib.sha256(body).hexdigest()), patch.object(H, 'SAMPLE_BYTES', len(body)):
            self.context['samplePath'] = str(sample)
            self.context['fixtureRequestSHA256'] = H.request_hashes(FIXTURE)
            self.armed['contextSHA256'] = self.store.context_sha = C.digest(self.context)
            seed = H.seed_request(FIXTURE)
            put = H.Request('s3', 'PutObject', H.source_params(FIXTURE), body)
            for phase, request in [('seed', seed), ('source-put', put)]:
                self.permit(request, phase)
                transport = self.transport()
                self.assertTrue(transport(request)['ok'])
                new_argv = self.calls[-1][0]
                self.assertEqual(new_argv, self.expected_argv(request, sample if phase == 'source-put' else None))
                self.assertNotIn('--cli-error-format', new_argv)
                with self.assertRaises(ValueError): transport(request)
            self.assertEqual(len(self.calls), 2)
            params = json.loads(self.calls[-1][0][self.calls[-1][0].index('--cli-input-json') + 1])
            self.assertEqual(params, H.source_params(FIXTURE))
            self.assertEqual(params['IfNoneMatch'], '*')
            self.assertEqual(len(seed.params['TransactItems']), 3)

    def test_request_identity_stop_role_and_funding_guards_preserved(self):
        seed = H.seed_request(FIXTURE)
        self.permit(seed, 'seed')
        with self.assertRaises(ValueError): self.transport(role='watchdog')(seed)
        with self.assertRaises(ValueError): self.transport(fresh=False)(seed)
        self.store.stop = {'reason': 'synthetic-stop'}
        with self.assertRaises(ValueError): self.transport()(self.head)
        self.store.stop = None
        self.proc.identity = lambda *args: None
        with self.assertRaises(ValueError): self.transport()(self.head)
        self.assertEqual(self.calls, [])
        new = ast.parse((HERE / 'fixture_runtime.py').read_text())
        new_class = next(n for n in new.body if isinstance(n, ast.ClassDef) and n.name == 'FixtureTransport')
        new_methods = {n.name: ast_fingerprint(n)
                       for n in new_class.body if isinstance(n, ast.FunctionDef)}
        self.assertEqual(set(new_methods), set(BASELINE['transportMethodASTSHA256']))
        self.assertEqual([n for n, sha in BASELINE['transportMethodASTSHA256'].items() if sha != new_methods[n]], ['__call__'])
        functions = {n.name: ast_fingerprint(n)
                     for n in new.body if isinstance(n, ast.FunctionDef)}
        self.assertEqual(set(functions) - set(BASELINE['functionASTSHA256']), {'verified_head_json_absence'})
        for name, expected in BASELINE['functionASTSHA256'].items():
            self.assertEqual(functions[name], expected)

    def test_runner_exception_has_no_raw_error_or_credential_output_and_no_retry(self):
        result = self.transport(raises=TimeoutError('SYNTHETIC_NEVER_EXPORT'))(self.head)
        self.assertFalse(result['ok'])
        self.assertEqual(len(self.calls), 1)
        row = self.store.rows[-1][1]
        self.assertEqual(row['diagnosticCategory'], 'fixture-command-did-not-return')
        self.assertIsNone(row['stdoutBytes'])
        self.assertIsNone(row['stderrSHA256'])
        self.assertNotIn('SYNTHETIC_NEVER_EXPORT', json.dumps(self.store.rows))
        self.assertEqual(self.store.records, {})


if __name__ == '__main__':
    unittest.main()
