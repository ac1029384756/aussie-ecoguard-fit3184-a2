"""Pure V13 lifecycle checks: injected clock/thread/process/IPC; no native calls."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('v13_pure_driver',HERE/'controller_driver.py')
driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)

class YieldThread(BaseException): pass
class Clock:
    def __init__(self):self.at=100.;self.threads=[];self.hooks=[]
    def monotonic(self):return self.at
    def sleep(self,delta):
        end=self.at+delta
        while True:
            due=[t for t in self.threads if t.next is not None and t.next<=end]
            if not due:break
            t=min(due,key=lambda t:t.next);self.at=t.next;t.step()
        self.at=end
        for hook in self.hooks:hook(self.at)
class Event:
    def __init__(self):self.flag=False;self.delay=None
    def is_set(self):return self.flag
    def set(self):self.flag=True
    def wait(self,delay):self.delay=delay;raise YieldThread()
class FakeThread:
    def __init__(self,clock,**kwargs):
        self.clock=clock;self.target=kwargs['target'];self.ident=None;self.next=None;self.joined=False
        clock.threads.append(self)
    def start(self):self.ident=999;self.step()
    def step(self):
        self.next=None
        try:self.target()
        except YieldThread:self.next=self.clock.at+1
    def join(self,timeout):self.joined=True;self.next=None

def same(a,b):return json.dumps(a,sort_keys=True)==json.dumps(b,sort_keys=True)
def core_identity(full):return {k:full[k] for k in ('pid','pgid','uid','nonce')}|{'startTime':full['startTicks']}
def identity(pid):return dict(pid=pid,pgid=pid,sid=pid,uid=1000,startTicks=pid+1000,nonce='a'*64,bootID='stub',cmdlineSHA256='b'*64)

class Store:
    def __init__(self,h):self.h=h;self.records={};self.hbs=[];self.stop=None;self.closed=False;self.close_calls=0;self.stop_calls=0
    def identity(self,role):return self.h.writer if role=='writer' else self.h.watchdog
    def publish_heartbeat(self,role,full,at):
        self.hbs.append(at)
        if self.h.fail_heartbeat and len(self.hbs)>1:raise OSError('injected publication failure')
    def latest_heartbeat(self,role):
        if self.h.ack_after is None or self.h.clock.at<100+self.h.ack_after:return None
        full=dict(self.h.watchdog)
        if self.h.bad_ack_identity:full['startTicks']+=1
        at=self.h.clock.at if self.h.ack_at is None else self.h.ack_at
        return {'identity':full,'at':at}
    def read_stop(self):return self.stop
    def input_is_open(self):return not self.closed
    def close_input(self):
        self.close_calls+=1;self.closed=True
        if self.h.close_raises:raise OSError('injected close failure')
        return True
    def request_stop(self,reason):self.stop_calls+=1;self.stop=reason;self.closed=True
    def write_once(self,name,payload):
        if name in self.records:raise ValueError('already written')
        self.records[name]=payload
    def read_singleton(self,name):
        if name not in self.records:raise FileNotFoundError(name)
        return self.records[name]
    def append_json(self,*args):pass

class Harness:
    def __init__(self,**overrides):
        self.clock=Clock();self.writer=identity(111);self.watchdog=identity(222)
        self.ack_after=8;self.ack_at=None;self.bad_ack_identity=False;self.alive=True
        self.funding=True;self.fail_heartbeat=False;self.close_raises=False
        self.spawn_delay=0;self.spawn_error=False;self.objects_delay=0;self.objects_error=False
        self.reserve=350;self.spawn_calls=0;self.object_calls=0;self.activation_calls=0;self.validated_arms=[]
        for k,v in overrides.items():setattr(self,k,v)
        self.store=Store(self)
        self.ctx={'nonce':'a'*64,'windowSeconds':600,'stopReserveSeconds':self.reserve,'heartbeatSeconds':10,'callTimeoutSeconds':10,'drainPollSeconds':1}
        self.binding={'context':self.ctx}
        self.args=SimpleNamespace(nonce=self.ctx['nonce'],attempt=str(driver.BASE/'processing-bounded-private'/('run-'+self.ctx['nonce'])),launch=False,writer=True,watchdog=False,context='unused',context_sha256='c'*64)
        self.proc=SimpleNamespace(identity=lambda pid,nonce: self.writer if pid==111 else (self.watchdog if self.alive else None))
        self.private=SimpleNamespace(PrivateStore=SimpleNamespace(open=lambda *a:self.store),LinuxProc=lambda:self.proc,same=same,core_identity=core_identity,DetachedSupervisor=lambda **kw:SimpleNamespace(spawn_watchdog=self.spawn))
        self.core=SimpleNamespace(digest=lambda ctx:'d'*64,same=same,validate_arm=self.validate_arm,TARGETS=('one',),observation_state=lambda *a:'safe',activate_once=self.activate)
        self.aws=SimpleNamespace(reviewed_environment=lambda *a,**kw:{})
    def validate_arm(self,ctx,armed):
        assert armed['stopNewWorkBy']==armed['t0']+600
        self.validated_arms.append(dict(armed))
    def spawn(self,*args):
        self.spawn_calls+=1
        assert len(self.clock.threads)==1 and self.clock.threads[0].ident is not None
        self.clock.sleep(self.spawn_delay)
        if self.spawn_error:raise RuntimeError('injected spawn failure')
        return self.watchdog
    def objects(self,*args):
        self.object_calls+=1;self.clock.sleep(self.objects_delay)
        if self.objects_error:raise RuntimeError('injected object failure')
        return self.proc,SimpleNamespace(observe=lambda *a:{},unchanged_boundaries=lambda *a:True,verify_empty_backlog=lambda *a:{}),object()
    def activate(self,ctx,armed,*args):
        self.activation_calls+=1
        assert self.store.latest_heartbeat('watchdog') is not None
        assert not self.store.closed
        assert armed['t0']==100 and armed['stopNewWorkBy']==700
        return {'activeVerified':False}
    def run(self):
        with patch.object(driver,'time',SimpleNamespace(monotonic=self.clock.monotonic,sleep=self.clock.sleep)),\
          patch.object(driver,'threading',SimpleNamespace(Event=Event,Thread=lambda **kw:FakeThread(self.clock,**kw))),\
          patch.object(driver.os,'getpid',return_value=111),patch.object(driver.os,'getuid',return_value=1000),\
          patch.object(driver.Path,'stat',return_value=SimpleNamespace(st_uid=1000,st_mode=0o700)),\
          patch.object(driver,'credential_route_reference',return_value={}),patch.object(driver,'launch_spec',return_value={}),\
          patch.object(driver,'objects',side_effect=self.objects),patch.object(driver,'verify_funding',side_effect=lambda *a:self.funding):
            return driver.run_mode(self.args,self.core,self.private,self.aws,self.binding,{})
    def stopped_cleanly(self):
        assert self.store.closed and self.store.stop=='verification'
        assert all(t.joined and t.next is None for t in self.clock.threads)
        assert self.activation_calls==0 and self.spawn_calls==1

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


class StartupLifecycleTests(unittest.TestCase):
    def test_healthy_initialization_longer_than_five_seconds(self):
        h=Harness(spawn_delay=7,ack_after=12,objects_delay=15);h.run()
        self.assertEqual(h.spawn_calls,1);self.assertEqual(h.activation_calls,1)
        self.assertGreaterEqual(h.clock.at,127);self.assertGreater(len(h.store.hbs),25)
        self.assertLessEqual(max(b-a for a,b in zip(h.store.hbs,h.store.hbs[1:])),1)
        self.assertTrue(h.clock.threads[0].joined)
        self.assertEqual(h.store.records['armed.json']['stopNewWorkBy'],700)
    def test_no_ack_stops_at_original_fixed_readiness_deadline(self):
        h=Harness(ack_after=None,spawn_delay=9)
        with self.assertRaises(ValueError):h.run()
        h.stopped_cleanly();self.assertAlmostEqual(h.clock.at,220)
        self.assertEqual(h.store.records['armed.json']['t0'],100)
    def test_original_stop_reserve_can_cut_startup_short(self):
        h=Harness(ack_after=None,reserve=550)
        with self.assertRaises(ValueError):h.run()
        h.stopped_cleanly();self.assertAlmostEqual(h.clock.at,150)
    def test_spawn_and_object_exceptions_close_and_stop(self):
        for opts in ({'spawn_error':True},{'objects_error':True,'objects_delay':16}):
            with self.subTest(opts=opts):
                h=Harness(**opts)
                with self.assertRaises(RuntimeError):h.run()
                h.stopped_cleanly()
    def test_stop_funding_and_child_identity_fail_closed(self):
        for reason in ('stop','funding','identity'):
            with self.subTest(reason=reason):
                h=Harness(ack_after=20)
                def hook(at):
                    if at>=106:
                        if reason=='stop':h.store.stop='verification';h.store.closed=True
                        elif reason=='funding':h.funding=False
                        else:h.alive=False
                h.clock.hooks.append(hook)
                with self.assertRaises(ValueError):h.run()
                h.stopped_cleanly();self.assertLess(h.clock.at,107)
    def test_malformed_future_stale_or_wrong_owner_ack_rejected(self):
        for opts in ({'ack_at':float('nan')},{'ack_at':500},{'ack_at':99},{'ack_at':100,'ack_after':12},{'bad_ack_identity':True}):
            with self.subTest(opts=opts):
                h=Harness(**opts)
                with self.assertRaises(ValueError):h.run()
                h.stopped_cleanly()
    def test_stop_attempted_even_when_close_input_raises(self):
        h=Harness(spawn_error=True,close_raises=True)
        with self.assertRaises(RuntimeError):h.run()
        h.stopped_cleanly();self.assertEqual(h.store.close_calls,1);self.assertEqual(h.store.stop_calls,1)
    def test_failed_heartbeat_aborts_before_apply(self):
        h=Harness(fail_heartbeat=True)
        with self.assertRaises(ValueError):h.run()
        h.stopped_cleanly()
    def test_core_once_deadline_and_other_modules_unchanged(self):
        # Packaging-only port: frozen hashes/ASTs replace a sibling work directory.
        baseline=json.loads((HERE/'tests/fixtures/v12-static-baseline.json').read_text())
        reviewed=json.loads((HERE/'tests/fixtures/v15-reviewed-snapshot.json').read_text())
        for name,expected in baseline['dependencySHA256'].items():
            expected=reviewed['dependencyOverrides'].get(name,expected)
            self.assertEqual(hashlib.sha256((HERE/name).read_bytes()).hexdigest(),expected,name)
        self.assertEqual(hashlib.sha256((HERE/'controller_driver.py').read_bytes()).hexdigest(),reviewed['driverSHA256'])
        after={node.name:ast_fingerprint(node)
            for node in ast.parse((HERE/'controller_driver.py').read_text()).body
            if isinstance(node,(ast.FunctionDef,ast.ClassDef))}
        self.assertTrue(set(baseline['canonicalFunctionASTSHA256']).issubset(after))
        changed={name for name,expected in baseline['canonicalFunctionASTSHA256'].items()
            if after[name]!=expected}
        self.assertEqual(changed,set(reviewed['changedFromV12FunctionASTSHA256']))
        for name,expected in reviewed['changedFromV12FunctionASTSHA256'].items():
            self.assertEqual(after[name],expected,name)
        self.assertFalse(driver.ARM_REVIEWED);self.assertIsNone(driver.ACTIVATION_PREPARER_SHA256)
        self.assertIsNone(driver.CURRENT_PAUSED_AUDIT_SHA256)

if __name__=='__main__':unittest.main(verbosity=2)
