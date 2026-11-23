"""Harbor verifier adapter for isolated Program Bench Pro episode lanes.

Harbor still collects the submission, owns the verification deadline and stores
the trial result. The existing parallel coordinator owns only its lane containers.
"""
import asyncio
import json
import math
import os
from pathlib import Path
import signal
import sys
import time

from harbor.models.verifier.result import VerifierResult
from harbor.verifier.verifier import Verifier, RewardFileNotFoundError

HERE = Path(__file__).resolve().parent


def write(path, value):
    pending = path.with_suffix('.pending')
    pending.write_text(json.dumps(value, indent=2) + '\n')
    pending.replace(path)


def valid_reward(directory):
    """Accept a complete full comparison, including a genuine zero score."""
    summary = json.loads((directory / 'summary.json').read_text())
    collection = json.loads((directory / 'collection.json').read_text())
    if (summary.get('infrastructure_error') or summary.get('diagnostic')
            or not summary.get('full_suite') or collection.get('incomplete')):
        raise ValueError('parallel comparison is incomplete or diagnostic')
    reward = float((directory / 'reward.txt').read_text())
    total, passed = summary['episode_total'], summary['episode_passed']
    # scoring.aggregate publishes six decimal places; validate that same value.
    if (not math.isfinite(reward) or not 0 <= reward <= 1
            or type(total) is not int or type(passed) is not int
            or total <= 0 or not 0 <= passed <= total
            or reward != round(passed / total, 6) or reward != summary['reward']):
        raise ValueError('parallel reward does not match full episode accounting')
    return reward


class ParallelVerifier(Verifier):
    def __init__(self, *args, task_root, image, api_key_file, base_url,
                 parallelism=2, model='kimi-k3', effort='high', protocol='openai-chat',
                 admission_file=None, event_log=None, max_attempts=4, data_reserve_gib=100, **kwargs):
        super().__init__(*args, **kwargs)
        self.task_root = Path(task_root).resolve()
        self.image, self.api_key_file, self.base_url = image, Path(api_key_file), base_url
        self.parallelism = parallelism
        self.model, self.effort, self.protocol = model, effort, protocol
        self.admission_file = Path(admission_file) if admission_file else None
        self.event_log = Path(event_log) if event_log else None
        self.max_attempts, self.data_reserve_gib = max_attempts, data_reserve_gib
        if parallelism not in (1, 2, 4) or max_attempts < 1:
            raise ValueError('invalid episode parallelism or attempt limit')

    def publish(self, attempt):
        """Expose standard Harbor evidence paths without changing original outputs."""
        root = self.trial_paths.verifier_dir
        names = ('summary.json', 'results.jsonl', 'manifest.json', 'identity.json',
                 'collection.json', 'accepted.json', 'episodes', 'reward.txt', 'reward.json')
        for name in names:
            source, target = attempt / name, root / name
            if not source.exists():
                continue
            if target.is_symlink():
                target.unlink()
            elif target.exists():
                raise ValueError('refusing to overwrite existing verifier evidence: ' + str(target))
            target.symlink_to(source.relative_to(root), target_is_directory=source.is_dir())

    async def verify(self):
        root = self.trial_paths.verifier_dir
        candidate = self.trial_paths.artifacts_dir / 'app/solution'
        if not candidate.is_dir():
            raise ValueError('Harbor did not collect /app/solution')
        lanes = self.parallelism
        if self.admission_file and self.admission_file.exists():
            admission = json.loads(self.admission_file.read_text())
            lanes = admission['episode_parallelism']
        if lanes not in (1, 2, 4):
            raise ValueError('episode parallelism must be 1, 2, or 4')
        parent = root / 'parallel'
        parent.mkdir(exist_ok=False)
        # Pin once, including across retries. No mutable image tag is reused.
        pin = await asyncio.create_subprocess_exec('docker', 'image', 'inspect', self.image,
                                                   '--format', '{{.Id}}', stdout=asyncio.subprocess.PIPE)
        stdout, _ = await pin.communicate()
        if pin.returncode:
            raise ValueError('verifier image is unavailable')
        image = stdout.decode().strip()
        previous = None
        for number in range(self.max_attempts):
            attempt = parent / f'attempt-{number:02d}'
            command = [sys.executable, '-B', str(HERE / 'parallel_compare.py'),
                       '--task', str(self.task_root), '--image', image,
                       '--candidate', str(candidate), '--out', str(attempt),
                       '--parallelism', str(lanes), '--api-key-file', str(self.api_key_file),
                       '--base-url', self.base_url, '--model', self.model, '--effort', self.effort,
                       '--protocol', self.protocol, '--data-reserve-gib', str(self.data_reserve_gib)]
            if previous:
                command += ['--resume-from', str(previous)]
            metadata = {'parallelism': lanes, 'attempt': number, 'output': str(attempt.relative_to(root)),
                        'image_id': image, 'started': time.time(), 'status': 'running'}
            with self.trial_paths.test_stdout_path.open('ab') as log:
                process = await asyncio.create_subprocess_exec(*command, stdout=log, stderr=log,
                                                               start_new_session=True)
                metadata['pid'] = process.pid
                write(root / 'parallel.json', metadata)
                try:
                    code = await process.wait()
                except asyncio.CancelledError:
                    # Harbor's original verifier timeout still bounds all attempts.
                    if process.returncode is None:
                        process.send_signal(signal.SIGTERM)
                        try:
                            await asyncio.wait_for(process.wait(), 90)
                        except asyncio.TimeoutError:
                            os.killpg(process.pid, signal.SIGKILL)
                            await process.wait()
                    metadata.update(status='interrupted', finished=time.time())
                    write(root / 'parallel.json', metadata)
                    raise
            metadata.update(returncode=code, finished=time.time())
            if code in (0, 1):
                reward = valid_reward(attempt)
                self.publish(attempt)
                metadata['status'] = 'complete'
                write(root / 'parallel.json', metadata)
                return VerifierResult(rewards={'reward': reward})
            metadata['status'] = 'incomplete'
            write(root / 'parallel.json', metadata)
            collection = attempt / 'collection.json'
            # Configuration/identity failures are not retried blindly.
            if not collection.exists() or not json.loads(collection.read_text()).get('incomplete'):
                raise RewardFileNotFoundError('parallel coordinator failed; inspect test-stdout.txt')
            cleanups = list((attempt / 'lanes').glob('*/cleanup.json'))
            if not cleanups or not all(json.loads(p.read_text()).get('container_absent') for p in cleanups):
                raise RewardFileNotFoundError('parallel lane cleanup incomplete; manual inspection required')
            previous = attempt
            if number + 1 < self.max_attempts:
                if self.event_log:
                    with self.event_log.open('a') as log:
                        log.write(json.dumps({'time': time.time(), 'event': 'verifier_resume',
                                              'attempt': number + 1, 'episode_parallelism': lanes,
                                              'resume_from': str(previous)}) + '\n')
                await asyncio.sleep(min(120, 30 * (number + 1)))
        raise RewardFileNotFoundError('parallel episodes remain incomplete after recovery attempts')
