"""Run with python -B -m unittest discover -s tests/maintainer -v.

Use an external TMPDIR. BENTOPDF_TEST_RUNTIME can select an unmodified runtime
snapshot to demonstrate the old failure; it never changes that snapshot.
"""
import argparse
import errno
import importlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

TASK = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TASK / 'tests'))
sys.path.insert(0, os.environ.get('BENTOPDF_TEST_RUNTIME', str(TASK / 'environment/runtime')))
import blackbox_runtime as runtime
from evaluation.broker import BrokerError
from evaluation.contract import InfrastructureError
from runtime_client import RuntimeClient


PAYLOAD = '''#!/usr/bin/python3
import json, os, signal, subprocess, sys, time
from pathlib import Path
if len(sys.argv) > 1:
    if os.fork(): os._exit(0)
    os.setsid()
    if os.fork(): os._exit(0)
    profile = Path(os.environ['TMPDIR'])/'profile'/'Default'
    profile.mkdir(parents=True, exist_ok=True)
    (Path(os.environ['DATA_DIR'])/'writer.json').write_text(json.dumps({'pid':os.getpid(),'session':os.getsid(0)}))
    def late_write(signum, frame):
        # A new session born during shutdown must still belong to this instance.
        subprocess.Popen([sys.executable, '-c', 'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)'], start_new_session=True)
        time.sleep(.03)
        (profile/'late-write').write_text('shutdown')
        signal.signal(signal.SIGTERM,signal.SIG_IGN)
    signal.signal(signal.SIGTERM,late_write)
    n=0
    while True:
        (profile/str(n%8)).write_text(str(n));n+=1;time.sleep(.002)
subprocess.Popen([sys.executable,__file__,'writer'], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
while not (Path(os.environ['DATA_DIR'])/'writer.json').exists(): time.sleep(.005)
if (Path(__file__).parent/'exit-launcher').exists(): sys.exit(23)
while True: time.sleep(1)
'''


def until(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError('condition did not become true')
        time.sleep(.01)


def active(pid):
    try:
        return Path(f'/proc/{pid}/stat').read_text().rpartition(')')[2].split()[0] != 'Z'
    except FileNotFoundError:
        return False


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.products = []
        self.writers = []
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for product in self.products:
            product.stop(.08)
        # Exact pidfds preserve isolation even when testing the old broken stop.
        for fd in self.writers:
            try:
                signal.pidfd_send_signal(fd, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.close(fd)

    def product(self, name='one', payload=PAYLOAD):
        solution = self.root / name / 'solution'
        solution.mkdir(parents=True)
        script = solution / 'start.sh'
        script.write_text(payload)
        script.chmod(0o755)
        config = argparse.Namespace(solution=solution, state=solution.parent/'state',
                                    user='', port=1, ready_timeout=.05)
        product = runtime.Product(config, log=runtime.BoundedLog(solution.parent/'logs'))
        self.products.append(product)
        return product

    def writer(self, product):
        path = Path(product.directories['DATA_DIR']) / 'writer.json'
        until(lambda: path.exists() and path.stat().st_size)
        writer = json.loads(path.read_text())
        self.writers.append(os.pidfd_open(writer['pid']))
        self.assertNotEqual(writer['session'], product.proc.pid)
        return writer['pid']

    def test_stop_waits_for_double_fork_and_new_sessions(self):
        product = self.product()
        self.assertTrue(product.start(True))
        pid = self.writer(product)
        product.stop(.08)
        self.assertFalse(active(pid), 'session-escaping writer survived stop')
        profile = product.directories['TMPDIR'] / 'profile' / 'Default'
        before = {p.name: p.read_bytes() for p in profile.iterdir()}
        time.sleep(.05)
        self.assertEqual(before, {p.name: p.read_bytes() for p in profile.iterdir()})

    def test_fresh_reset_preserves_unrelated_instance(self):
        first, other = self.product('one'), self.product('other')
        self.assertTrue(first.start(True)); self.assertTrue(other.start(True))
        old_pid, unrelated_pid = self.writer(first), self.writer(other)
        first.stop(.08)
        self.assertTrue(first.start(True))
        self.writer(first)
        self.assertFalse(active(old_pid))
        self.assertTrue(other.running()); self.assertTrue(active(unrelated_pid))
        self.assertTrue((other.directories['TMPDIR']/'profile'/'Default').is_dir())

    def test_launcher_exit_still_cleans_owned_descendants(self):
        product = self.product()
        (product.solution/'exit-launcher').touch()
        self.assertTrue(product.start(True))
        pid = self.writer(product)
        # Natural exit also owns cleanup, rather than leaving orphaned children.
        until(lambda: not active(product.proc.pid))
        product.stop(.08)
        self.assertEqual(product.proc.returncode, 23)
        self.assertFalse(active(pid))

    @unittest.skipUnless(os.geteuid() == 0, 'requires the verifier root/candidate user split')
    def test_unprivileged_descendant_cleanup(self):
        product = self.product()
        self.root.chmod(0o711)
        product.solution.parent.chmod(0o711)
        product.config.user = 'agent'
        self.assertTrue(product.start(True))
        pid = self.writer(product)
        product.stop(.08)
        self.assertFalse(active(pid))

    def test_execute_and_ready_failures_remain_candidate_outcomes(self):
        product = self.product(payload='#!/bin/sh\nexit 23\n')
        product.solution.joinpath('start.sh').chmod(0o644)
        self.assertFalse(product.start(True))
        self.assertIn('could not be executed', product.detail)
        product.solution.joinpath('start.sh').chmod(0o755)
        self.assertTrue(product.start(True))
        until(lambda: not product.running())
        self.assertEqual(product.status()['exit_code'], 23)
        slow = self.product('slow', '#!/bin/sh\nexec sleep 60\n')
        self.assertTrue(slow.start(True))
        self.assertFalse(runtime.wait_http(slow))
        self.assertFalse(slow.status()['ready'])

    def test_stop_fault_prevents_state_deletion(self):
        product = self.product()
        product.proc = mock.Mock()
        product.proc.stop.side_effect = runtime.RuntimeCleanupError('stop failed')
        with mock.patch.object(product, 'prepare') as prepare:
            with self.assertRaises(runtime.RuntimeCleanupError):
                product.start(True)
            prepare.assert_not_called()
        product.proc = None

    def test_stop_timeout_does_not_leave_supervisor_running(self):
        from product_process import ProductProcess
        child = subprocess.Popen(['/bin/sleep', '60'])
        process = ProductProcess.__new__(ProductProcess)
        process.supervisor = child
        process.stream = mock.Mock()
        process.control = mock.Mock()
        try:
            with mock.patch.object(process, 'wait', side_effect=subprocess.TimeoutExpired('injected', 1)):
                with self.assertRaises(runtime.RuntimeCleanupError):
                    process.stop(.01)
            self.assertIsNotNone(child.poll())
        finally:
            if child.poll() is None:
                child.kill(); child.wait()


class CleanupTests(unittest.TestCase):
    def test_fd_cleanup_retries_late_directory_write_without_following_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); state = root/'state'; state.mkdir()
            outside = root/'outside'; outside.mkdir()
            (outside/'keep').write_text('untouched')
            profile = state/'tmp'/'Default'; profile.mkdir(parents=True)
            (profile/'outside').symlink_to(outside, target_is_directory=True)
            original = os.rmdir
            races = []

            def delayed_write(name, *, dir_fd=None):
                if name == 'Default' and not races:
                    races.append(name)
                    (profile/'late').write_text('arrived after enumeration')
                return original(name, dir_fd=dir_fd)

            with runtime.open_directory(state) as fd, mock.patch.object(os, 'rmdir', delayed_write):
                runtime.clear_instance(fd)
            self.assertEqual(races, ['Default'])
            self.assertEqual(list(state.iterdir()), [])
            self.assertEqual((outside/'keep').read_text(), 'untouched')

    def test_persistent_races_are_bounded_and_internal(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'entry').touch()
            for err, calls in ((errno.ENOTEMPTY, 3), (errno.EACCES, 1)):
                with runtime.open_directory(tmp) as fd, \
                     mock.patch.object(runtime, 'remove_entry', side_effect=OSError(err, 'injected')) as remove, \
                     mock.patch.object(runtime.time, 'sleep'):
                    with self.assertRaises(runtime.RuntimeCleanupError):
                        runtime.clear_instance(fd, attempts=3)
                    self.assertEqual(remove.call_count, calls)


class ClassificationTests(unittest.TestCase):
    def test_only_structured_internal_cleanup_fault_is_infrastructure(self):
        client = mock.Mock()
        wrapped = RuntimeClient(client)
        for op in ('reset', 'restart', 'status'):
            client.call.side_effect = BrokerError(500, 'RuntimeCleanupError', 'private cleanup failed')
            with self.assertRaises(InfrastructureError):
                wrapped.call({'op': op})
        for status, kind in ((400, 'OSError'), (400, 'RuntimeCleanupError'),
                             (500, 'ValueError'), (408, 'TimeoutError')):
            fault = BrokerError(status, kind, 'candidate failure')
            client.call.side_effect = fault
            with self.assertRaises(BrokerError) as caught:
                wrapped.call({'op': 'reset'})
            self.assertIs(caught.exception, fault)
        client.call.side_effect = None
        client.call.return_value = {'ready': False, 'detail': 'candidate did not start'}
        self.assertFalse(wrapped.call({'op': 'reset'})['ready'])

    def test_rpc_preserves_structured_fault_type(self):
        try:
            broker = importlib.import_module('broker')
        except ModuleNotFoundError as exc:
            self.skipTest('RPC test requires the built base/verifier dependencies: ' + str(exc))
        import asyncio
        async def read_request(request):
            return b'{"op":"reset"}'
        async def failed_dispatch(data):
            raise runtime.RuntimeCleanupError('owned directory could not be cleared')
        with mock.patch.object(broker, 'read_request', read_request), \
             mock.patch.object(broker, 'dispatch', failed_dispatch), \
             mock.patch.object(broker, 'audit', mock.Mock()), \
             mock.patch.object(broker, 'private', __import__('re').compile('never-match')), \
             mock.patch.object(broker, 'redact', lambda x: x):
            response = asyncio.run(broker.rpc(None))
        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.loads(response.body)['error'], 'RuntimeCleanupError')


if __name__ == '__main__':
    unittest.main()
