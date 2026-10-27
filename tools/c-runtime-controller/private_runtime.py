"""Private append-only IPC and explicit Linux process supervision. Import is inert.

No cloud/credential operation or process starts here by default. All LaunchSpec
pins default None. The reviewed driver owns evidence verification and authority.
"""
from dataclasses import dataclass
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
import time
import uuid

HEX = re.compile(r'[0-9a-f]{64}')
REASONS = {'success', 'deadline', 'heartbeat', 'funding', 'verification', 'user-pause', 'partial-apply'}
CREDENTIAL_ROUTE_GUARD_SHA256 = 'c742bd1cb2a2cc28989fcc606c540c6a8bd0e2cce574678c95cc1f675e094d35'
IDENTITY_KEYS = {'pid', 'pgid', 'sid', 'startTicks', 'uid', 'bootID', 'cmdlineSHA256', 'nonce'}


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def same(a, b):
    if type(a) is not type(b): return False
    if isinstance(a, dict): return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list): return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def core_identity(full):
    require(identity_valid(full, full.get('nonce') if isinstance(full, dict) else None) and full['nonce'] is not None, 'Full registered root identity required')
    return {'pid': full['pid'], 'pgid': full['pgid'], 'uid': full['uid'], 'startTime': full['startTicks'], 'nonce': full['nonce']}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha_file(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1024 ** 2), b''): h.update(part)
    return h.hexdigest()


def no_links(path):
    require(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)), 'Symlink or relative private path rejected')


def regular(path, uid=None, private=False):
    no_links(path)
    s = path.stat()
    require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'Private regular file required')
    if uid is not None: require(s.st_uid == uid, 'Private file owner differs')
    if private: require(stat.S_IMODE(s.st_mode) == 0o600, 'Private record must be mode0600')
    return path


def identity_valid(value, nonce=None):
    return (type(value) is dict and set(value) == IDENTITY_KEYS
        and all(type(value[k]) is int and value[k] > 0 for k in ('pid', 'pgid', 'sid', 'startTicks'))
        and type(value['uid']) is int and value['uid'] >= 0
        and type(value['bootID']) is str and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', value['bootID'])
        and type(value['cmdlineSHA256']) is str and HEX.fullmatch(value['cmdlineSHA256'])
        and (value['nonce'] is None or type(value['nonce']) is str and HEX.fullmatch(value['nonce']))
        and (nonce is None or value['nonce'] == nonce))


class PrivateStore:
    """Owner-only attempt directory; atomic exclusive publication + file/dir fsync.

    Intent presence consumes an action even if a later API/record operation fails.
    Heartbeats/receipts append immutable records; nothing replaces prior evidence.
    """
    def __init__(self, path, context_sha, nonce, *, uid=None):
        self.path, self.context_sha, self.nonce = Path(path), context_sha, nonce
        self.uid = os.getuid() if uid is None else uid
        require(type(context_sha) is str and HEX.fullmatch(context_sha) and type(nonce) is str and HEX.fullmatch(nonce), 'Context/nonce pins required')
        self._check_directory()

    @classmethod
    def create(cls, path, context_sha, nonce, *, uid=None):
        path = Path(path); no_links(path)
        require(path.parent.is_dir(), 'Existing private attempt parent required')
        os.mkdir(path, 0o700)  # exclusive, never reuse a consumed attempt
        parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: os.fsync(parent_fd)
        finally: os.close(parent_fd)
        obj = cls(path, context_sha, nonce, uid=uid)
        require(obj._publish('binding.json', {'kind': 'binding'}, exclusive=True), 'New binding already exists')
        return obj

    @classmethod
    def open(cls, path, context_sha, nonce, *, uid=None):
        obj = cls(path, context_sha, nonce, uid=uid)
        require(obj.read_json('binding.json') == {'kind': 'binding'}, 'Attempt binding missing')
        return obj

    def _check_directory(self):
        no_links(self.path); s = self.path.stat()
        require(stat.S_ISDIR(s.st_mode) and s.st_uid == self.uid and stat.S_IMODE(s.st_mode) == 0o700, 'Attempt owner/mode differs')

    def _dirfd(self):
        self._check_directory()
        fd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        s = os.fstat(fd); actual = self.path.stat()
        if (s.st_dev, s.st_ino) != (actual.st_dev, actual.st_ino):
            os.close(fd); raise RuntimeError('Attempt directory changed')
        return fd

    @staticmethod
    def _name(name):
        require(type(name) is str and re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,180}', name), 'Invalid private record name')
        return name

    def _publish(self, name, payload, *, exclusive=True):
        require(exclusive is True, 'Mutable record replacement is not supported')
        self._name(name)
        data = encoded({'contextSHA256': self.context_sha, 'nonce': self.nonce, 'payload': payload})
        require(len(data) <= 1024 ** 2, 'Private IPC record too large')
        d = self._dirfd(); temp = '.pending-' + uuid.uuid4().hex; fd = None
        try:
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=d)
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, 'wb') as f:
                fd = None; f.write(data); f.flush(); os.fsync(f.fileno())
            try: os.link(temp, name, src_dir_fd=d, dst_dir_fd=d, follow_symlinks=False)
            except FileExistsError: return False
            os.fsync(d)
            return True
        finally:
            if fd is not None: os.close(fd)
            try: os.unlink(temp, dir_fd=d)
            except FileNotFoundError: pass
            os.fsync(d); os.close(d)

    def _published_record_stat(self, fd, directory_fd):
        value = os.fstat(fd)
        require(stat.S_ISREG(value.st_mode) and value.st_uid == self.uid and stat.S_IMODE(value.st_mode) == 0o600,
            'Unsafe IPC record')
        if value.st_nlink == 1: return
        require(value.st_nlink == 2, 'Unexpected IPC hardlinks')
        # link(temp,final) publishes complete fsynced bytes exclusively. A reader
        # may run before unlink(temp), or the publisher may crash in that window.
        # Admit ONLY that exact private same-directory twin, never an arbitrary
        # outside link. Readers never remove another process's pending evidence.
        twins = []
        for name in os.listdir(directory_fd):
            if not re.fullmatch(r'[.]pending-[0-9a-f]{32}', name): continue
            try: candidate = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            except FileNotFoundError: continue
            if (candidate.st_dev, candidate.st_ino) == (value.st_dev, value.st_ino): twins.append(name)
        current = os.fstat(fd)
        if current.st_nlink == 1: return  # publisher completed its unlink
        require(current.st_nlink == 2 and len(twins) == 1, 'Unmatched private publication twin')
        try: twin = os.stat(twins[0], dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            require(os.fstat(fd).st_nlink == 1, 'Publication twin disappeared unexpectedly')
            return
        require(stat.S_ISREG(twin.st_mode) and twin.st_uid == self.uid and stat.S_IMODE(twin.st_mode) == 0o600
            and (twin.st_dev, twin.st_ino) == (current.st_dev, current.st_ino),
            'Unsafe private publication twin')
        require(os.fstat(fd).st_nlink in (1, 2), 'Publication link count changed unexpectedly')

    def read_json(self, name):
        self._name(name); d = self._dirfd()
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=d)
            with os.fdopen(fd, 'rb') as f:
                self._published_record_stat(f.fileno(), d)
                raw = f.read(1024 ** 2 + 1)
            require(len(raw) <= 1024 ** 2, 'IPC record limit exceeded')
            value = json.loads(raw)
            require(set(value) == {'contextSHA256', 'nonce', 'payload'} and value['contextSHA256'] == self.context_sha and value['nonce'] == self.nonce, 'IPC context/nonce differs')
            return value['payload']
        finally: os.close(d)

    def write_once(self, name, payload):
        require(name.endswith('.json'), 'JSON singleton name required')
        return self._publish(name, payload)

    def read_singleton(self, name): return self.read_json(name)

    def has_intent(self, action):
        require(type(action) is str and re.fullmatch(r'[a-z][a-z0-9:-]{0,100}', action), 'Unknown action shape')
        name = 'intent-' + hashlib.sha256(action.encode()).hexdigest() + '.json'
        try: value = self.read_json(name)
        except FileNotFoundError: return False
        require(type(value) is dict and set(value) == {'action', 'requestSHA256'} and value['action'] == action
            and (value['requestSHA256'] is None or type(value['requestSHA256']) is str and HEX.fullmatch(value['requestSHA256'])), 'Malformed consumed intent')
        return True

    def mark_once(self, action, context_sha, nonce, request_sha=None):
        require(context_sha == self.context_sha and nonce == self.nonce, 'Intent context differs')
        require(type(action) is str and re.fullmatch(r'[a-z][a-z0-9:-]{0,100}', action), 'Unknown action shape')
        require(request_sha is None or type(request_sha) is str and HEX.fullmatch(request_sha), 'Request pin malformed')
        name = 'intent-' + hashlib.sha256(action.encode()).hexdigest() + '.json'
        payload = {'action': action, 'requestSHA256': request_sha}
        added = self._publish(name, payload)
        if not added: require(same(self.read_json(name), payload), 'Existing intent differs; do not reuse')
        return added

    def close_input(self):
        self._publish('input-closed.json', {'closed': True})
        return same(self.read_json('input-closed.json'), {'closed': True})

    def input_is_open(self):
        self._check_directory()
        try: value = self.read_json('input-closed.json')
        except FileNotFoundError: return True
        require(same(value, {'closed': True}), 'Input latch malformed')
        return False

    def request_stop(self, reason):
        require(reason in REASONS, 'Unknown STOP reason')
        self.close_input(); self._publish('stop.json', {'reason': reason})
        return self.read_stop()

    def read_stop(self):
        try: value = self.read_json('stop.json')
        except FileNotFoundError: return None
        require(type(value) is dict and set(value) == {'reason'} and value['reason'] in REASONS, 'STOP record malformed')
        require(not self.input_is_open(), 'STOP without sticky closed input')
        return value['reason']

    def append_json(self, kind, payload):
        require(type(kind) is str and re.fullmatch(r'[a-z][a-z0-9-]{0,40}', kind), 'Unknown record kind')
        name = kind + '-' + uuid.uuid4().hex + '.json'
        require(self._publish(name, payload), 'Exclusive record collision')
        return self.path / name

    def append_receipt(self, payload): return self.append_json('receipt', payload)

    def publish_heartbeat(self, kind, identity, at):
        require(kind in ('writer', 'watchdog') and identity_valid(identity, self.nonce) and identity['uid'] == self.uid
            and identity['pid'] == identity['pgid'] == identity['sid'], 'Heartbeat process identity differs')
        require(type(at) in (int, float) and math.isfinite(at) and at >= 0, 'Heartbeat monotonic time invalid')
        previous = self.latest_heartbeat(kind)
        if previous is not None:
            require(same(previous['identity'], identity) and at >= previous['at'], 'Heartbeat identity/time went backwards')
        return self.append_json(kind + '-heartbeat', {'identity': identity, 'at': at})

    def latest_heartbeat(self, kind):
        require(kind in ('writer', 'watchdog'), 'Unknown heartbeat kind'); self._check_directory()
        names = [p.name for p in self.path.iterdir() if p.name.startswith(kind + '-heartbeat-')]
        require(len(names) <= 4096, 'Heartbeat record limit exceeded')
        records = [self.read_json(n) for n in names]
        require(all(type(v) is dict and set(v) == {'identity', 'at'} and identity_valid(v['identity'], self.nonce)
            and v['identity']['uid'] == self.uid and v['identity']['pid'] == v['identity']['pgid'] == v['identity']['sid']
            and type(v['at']) in (int, float) and math.isfinite(v['at']) and v['at'] >= 0 for v in records), 'Malformed heartbeat')
        if not records: return None
        require(all(same(v['identity'], records[0]['identity']) for v in records), 'Multiple heartbeat owners')
        return max(records, key=lambda v: v['at'])

    def write_identity(self, kind, identity):
        require(kind in ('writer', 'watchdog') and identity_valid(identity, self.nonce)
            and identity['uid'] == self.uid and identity['pid'] == identity['pgid'] == identity['sid'], 'Private process identity differs')
        require(self._publish(kind + '-identity.json', identity), 'Process identity already recorded; no respawn')

    def identity(self, kind):
        require(kind in ('writer', 'watchdog'), 'Unknown process kind')
        value = self.read_json(kind + '-identity.json')
        require(identity_valid(value, self.nonce) and value['uid'] == self.uid and value['pid'] == value['pgid'] == value['sid'], 'Stored process identity differs')
        return value


class LinuxProc:
    """Only process IDs/stat/status/cmdline; never /proc/environ or auth files."""
    def __init__(self, root=Path('/proc')):
        self.root = Path(root)
        self.boot = (self.root / 'sys/kernel/random/boot_id').read_text().strip()
        require(re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', self.boot), 'Linux boot identity unavailable')

    def _stat(self, pid):
        require(type(pid) is int and pid > 0, 'Positive PID required')
        raw = (self.root / str(pid) / 'stat').read_text()
        leader, rest = raw.rsplit(') ', 1); fields = rest.split()
        require(int(leader.split(' ', 1)[0]) == pid and len(fields) >= 20, 'Malformed Linux stat')
        return fields

    def snapshot(self, pid, nonce):
        try:
            fields = self._stat(pid)
            if fields[0] == 'Z': return None
            path = self.root / str(pid)
            uidline = next(line for line in (path / 'status').read_text().splitlines() if line.startswith('Uid:'))
            uids = [int(v) for v in uidline.split()[1:]]
            require(len(uids) == 4 and len(set(uids)) == 1, 'Process UID is ambiguous')
            with (path / 'cmdline').open('rb') as f: argv = f.read(65537)
            require(len(argv) <= 65536 and argv.endswith(b'\0'), 'Process command is unbounded/malformed')
            parts = argv[:-1].split(b'\0'); token = nonce.encode()
            tagged = sum(parts[i] == b'--nonce' and parts[i+1] == token for i in range(len(parts)-1)) == 1
            ident = {'pid': pid, 'pgid': int(fields[2]), 'sid': int(fields[3]), 'startTicks': int(fields[19]), 'uid': uids[0],
                'bootID': self.boot, 'cmdlineSHA256': hashlib.sha256(argv).hexdigest(), 'nonce': nonce if tagged else None}
            # Re-read incarnation/group after the other files; a disappearing or
            # reused PID cannot combine one process's command with another's stat.
            again = self._stat(pid)
            require((fields[2], fields[3], fields[19]) == (again[2], again[3], again[19]), 'Process changed during observation')
            require(identity_valid(ident), 'Malformed process identity')
            return {'identity': ident, 'ppid': int(again[1])}
        except (FileNotFoundError, ProcessLookupError): return None

    def identity(self, pid, nonce):
        value = self.snapshot(pid, nonce)
        return None if value is None else value['identity']

    def signal_exact(self, identity, sig, nonce):
        # pidfd binds the kernel process incarnation through the signal syscall.
        # Adjacent numeric-PID checks alone cannot remove PID-reuse TOCTOU.
        require(hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal'), 'Native pidfd signalling unavailable; no unsafe fallback')
        fd = os.pidfd_open(identity['pid'], 0)
        try:
            require(same(self.identity(identity['pid'], nonce), identity), 'Process changed before pidfd signal')
            signal.pidfd_send_signal(fd, sig, None, 0)
        finally: os.close(fd)

    def members(self, pgid, nonce):
        require(type(pgid) is int and pgid > 0, 'Positive process group required')
        members = {}
        for path in self.root.iterdir():
            if not path.name.isdecimal(): continue
            pid = int(path.name)
            try:
                if int(self._stat(pid)[2]) != pgid: continue
                value = self.snapshot(pid, nonce)
                if value is not None: members[pid] = value
            except (FileNotFoundError, ProcessLookupError): continue
        require(len(members) <= 128, 'Writer process group exceeds reviewed bound')
        return members


class Quiescer:
    def __init__(self, proc, *, store=None, send_signal=None, sleep=time.sleep, clock=time.monotonic,
                 self_pid=None, watchdog_identity=None):
        self.proc, self.store, self.send_signal, self.sleep, self.clock = proc, store, send_signal, sleep, clock
        self.self_pid = os.getpid() if self_pid is None else self_pid
        self.watchdog = watchdog_identity

    def quiesce_writer(self, expected, timeout_seconds):
        # RuntimePort/core carries exactly five stable fields. Resolve to the
        # registered full private identity, never reconstruct missing boot/argv.
        try:
            require(self.store is not None, 'Registered private process store required')
            full = self.store.identity('writer')
            require(same(core_identity(full), expected), 'Core writer identity differs from registration')
            result = self._quiesce_full(full, timeout_seconds)
            result['identity'] = expected
            return result
        except Exception:
            return {'identity': expected, 'quiesced': False, 'inFlightCloudCallsRetracted': False,
                'termSignals': 0, 'killSignals': 0, 'reason': 'registered-writer-identity-unverified'}

    def _quiesce_full(self, expected, timeout_seconds):
        result = {'identity': expected, 'quiesced': False, 'inFlightCloudCallsRetracted': False,
            'termSignals': 0, 'killSignals': 0, 'reason': 'unverified-writer'}
        try:
            require(identity_valid(expected, expected.get('nonce')) and expected['nonce'] is not None
                and expected['pid'] == expected['pgid'] == expected['sid'] and expected['pid'] != self.self_pid, 'Writer identity invalid/self')
            require(type(timeout_seconds) in (int, float) and math.isfinite(timeout_seconds) and 0 < timeout_seconds <= 60, 'Quiesce timeout outside bound')
            me = self.proc.identity(self.self_pid, expected['nonce'])
            require(me is not None and me['pgid'] != expected['pgid'], 'Cannot stop own process group')
            if self.watchdog is not None:
                require(identity_valid(self.watchdog, expected['nonce']) and self.watchdog['pgid'] != expected['pgid']
                    and same(self.proc.identity(self.watchdog['pid'], expected['nonce']), self.watchdog), 'Watchdog identity changed/group collides')
            require(self.proc.boot == expected['bootID'], 'System boot changed')
            known, sent_term, sent_kill = {}, set(), set()
            start = self.clock()
            require(type(start) in (int, float) and math.isfinite(start) and start >= 0, 'Monotonic clock invalid')
            deadline = start + timeout_seconds; kill_at = start + timeout_seconds / 2
            for _ in range(1024):
                leader = self.proc.identity(expected['pid'], expected['nonce'])
                require(leader is None or same(leader, expected), 'Writer PID reused')
                members = self.proc.members(expected['pgid'], expected['nonce'])
                for pid, row in members.items():
                    ident = row['identity']
                    require(identity_valid(ident) and ident['uid'] == expected['uid'] and ident['bootID'] == expected['bootID']
                        and ident['pgid'] == ident['sid'] == expected['pgid'] and pid not in {self.self_pid, self.watchdog['pid'] if self.watchdog else -1}, 'Unowned group member')
                    if pid in known:
                        require(same(known[pid], ident), 'Child PID reused')
                        continue
                    require(leader is not None, 'New orphan ancestry cannot be proved')
                    cursor, seen = pid, set()
                    while cursor != expected['pid']:
                        require(cursor in members and cursor not in seen, 'Child parent chain is unowned')
                        seen.add(cursor); cursor = members[cursor]['ppid']
                    known[pid] = ident
                if leader is None and not members:
                    result.update(quiesced=True, reason='writer-group-absent'); return result
                require(expected['pid'] in known, 'Writer group leader missing from snapshot')
                now = self.clock()
                require(type(now) in (int, float) and math.isfinite(now) and now >= start, 'Monotonic clock regressed')
                if now >= deadline: break
                sig = signal.SIGKILL if now >= kill_at else signal.SIGTERM
                sent = sent_kill if sig == signal.SIGKILL else sent_term
                # Signal exact known individual PIDs, never killpg. Each identity
                # is freshly checked immediately adjacent to the signal call.
                for pid in sorted(members, key=lambda p: p != expected['pid']):
                    if pid in sent: continue
                    fresh = self.proc.identity(pid, expected['nonce'])
                    if fresh is None: continue
                    require(same(fresh, known[pid]), 'PID identity changed before signal')
                    try:
                        if self.send_signal is None: self.proc.signal_exact(fresh, sig, expected['nonce'])
                        else: self.send_signal(fresh, sig)
                    except ProcessLookupError: continue
                    sent.add(pid); result['killSignals' if sig == signal.SIGKILL else 'termSignals'] += 1
                self.sleep(min(0.05, max(0.0, deadline - self.clock())))
            result['reason'] = 'writer-group-not-verified-stopped'
        except Exception:
            result['reason'] = 'writer-identity-or-signal-unverified'
        return result


@dataclass(frozen=True)
class LaunchSpec:
    python: Path | None = None
    python_sha256: str | None = None
    driver: Path | None = None
    driver_sha256: str | None = None
    context_file: Path | None = None
    context_file_sha256: str | None = None


def credential_guard():
    path=Path(__file__).with_name('credential_route.py')
    regular(path)
    require(sha_file(path)==CREDENTIAL_ROUTE_GUARD_SHA256,'Shared route guard SHA differs')
    spec=importlib.util.spec_from_file_location('private_pinned_cloudshell_route_guard',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def check_credential_environment(env, credential_route=None):
    credential_guard().reviewed_credentials(env,credential_route)


class DetachedSupervisor:
    """Explicit fixed pinned driver launch only; no arbitrary argv or shell."""
    def __init__(self, proc=None, *, credential_route=None, spawn=subprocess.Popen, clock=time.monotonic, sleep=time.sleep, self_pid=None):
        self.proc, self.spawn, self.clock, self.sleep = proc, spawn, clock, sleep
        self.credential_route = None if credential_route is None else dict(credential_route)
        self.self_pid = os.getpid() if self_pid is None else self_pid

    def _spawn(self, mode, spec, store, env):
        require(mode in ('writer', 'watchdog') and isinstance(spec, LaunchSpec), 'Unknown supervised mode')
        for path, digest in ((spec.python, spec.python_sha256), (spec.driver, spec.driver_sha256), (spec.context_file, spec.context_file_sha256)):
            require(isinstance(path, Path) and type(digest) is str and HEX.fullmatch(digest), 'Actual launch file pins pending')
            regular(path, store.uid if path != spec.python else None, private=path == spec.context_file)
            require(sha_file(path) == digest, 'Frozen launch file SHA differs')
        require(type(env) is dict and all(type(k) is str and type(v) is str for k, v in env.items()), 'Explicit memory-only environment required')
        check_credential_environment(env,self.credential_route)
        initial_env=dict(env)  # memory-only token; never written to IPC or receipts
        allowed = {'AWS_CONTAINER_CREDENTIALS_FULL_URI','AWS_CONTAINER_AUTHORIZATION_TOKEN','PATH', 'HOME', 'LANG', 'LC_ALL', 'TMPDIR', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN',
            'AWS_SECURITY_TOKEN', 'AWS_EXECUTION_ENV', 'AWS_REGION', 'AWS_DEFAULT_REGION', 'AWS_PAGER', 'AWS_CLI_AUTO_PROMPT',
            'AWS_MAX_ATTEMPTS', 'AWS_IGNORE_CONFIGURED_ENDPOINT_URLS', 'TF_DATA_DIR', 'TF_CLI_CONFIG_FILE', 'TF_IN_AUTOMATION',
            'CHECKPOINT_DISABLE', 'PYTHONDONTWRITEBYTECODE', 'PYTHONNOUSERSITE', 'AWS_CONFIG_FILE', 'AWS_SHARED_CREDENTIALS_FILE',
            'BOTO_CONFIG', 'AWS_RETRY_MODE', 'AWS_EC2_METADATA_DISABLED'}
        require(set(env) <= allowed and env.get('HOME') == '/home/cloudshell-user' and env.get('PATH') == os.defpath
            and env.get('AWS_REGION') == env.get('AWS_DEFAULT_REGION') == 'us-east-1' and env.get('AWS_MAX_ATTEMPTS') == '1'
            and env.get('AWS_IGNORE_CONFIGURED_ENDPOINT_URLS') == 'true', 'Unreviewed process environment')
        require(all(env.get(k) == v for k, v in {'AWS_CONFIG_FILE': '/dev/null', 'AWS_SHARED_CREDENTIALS_FILE': '/dev/null',
            'BOTO_CONFIG': '/dev/null', 'AWS_RETRY_MODE': 'standard', 'AWS_EC2_METADATA_DISABLED': 'true', 'PYTHONNOUSERSITE': '1'}.items()),
            'Profile/metadata/user-site isolation differs')
        store._check_directory(); require(store.input_is_open() and store.read_stop() is None, 'STOP already latched')
        proc = self.proc or LinuxProc()
        if mode == 'watchdog':
            writer = store.identity('writer')
            require(writer['pid'] == self.self_pid and same(proc.identity(self.self_pid, store.nonce), writer), 'Only exact isolated writer may spawn watchdog')
        require(store.mark_once('spawn:' + mode, store.context_sha, store.nonce), 'Spawn already consumed; no relaunch')
        argv = [str(spec.python), '-I', '-B', str(spec.driver), '--' + mode, '--attempt', str(store.path),
            '--context', str(spec.context_file), '--context-sha256', spec.context_file_sha256, '--nonce', store.nonce]
        name = mode + '-process-private.log'; d = store._dirfd()
        try:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=d)
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, 'wb') as log:
                require(env==initial_env,'Memory-only child environment changed')
                check_credential_environment(env,self.credential_route)
                child = self.spawn(argv, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                    start_new_session=True, close_fds=True, shell=False)
        finally: os.close(d)
        require(type(child.pid) is int and child.pid > 0 and child.pid != self.self_pid, 'Spawn PID invalid')
        deadline = self.clock() + 5
        for _ in range(100):
            identity = proc.identity(child.pid, store.nonce)
            if identity is not None:
                require(identity_valid(identity, store.nonce) and identity['uid'] == store.uid and identity['pid'] == identity['pgid'] == identity['sid']
                    and identity['bootID'] == proc.boot, 'Child is not the pinned new session/nonce/boot')
                expected = b'\0'.join(s.encode() for s in argv) + b'\0'
                require(identity['cmdlineSHA256'] == hashlib.sha256(expected).hexdigest(), 'Spawn command bytes differ')
                for path, digest in ((spec.python, spec.python_sha256), (spec.driver, spec.driver_sha256), (spec.context_file, spec.context_file_sha256)):
                    require(sha_file(regular(path, store.uid if path != spec.python else None, private=path == spec.context_file)) == digest, 'Launch inputs changed before registration')
                store.write_identity(mode, identity)
                return identity
            require(self.clock() < deadline, 'Supervised child identity not verified')
            self.sleep(0.05)
        raise RuntimeError('Supervised child identity not verified; do not relaunch')

    def spawn_writer(self, spec, store, env): return self._spawn('writer', spec, store, env)
    def spawn_watchdog(self, spec, store, env): return self._spawn('watchdog', spec, store, env)
