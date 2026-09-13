"""Tests need neither a GPU nor access to the systemd user manager."""
import argparse
import contextlib
import fcntl
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name('gpu-run')
loader = importlib.machinery.SourceFileLoader('gpu_run', str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
runner = importlib.util.module_from_spec(spec)
loader.exec_module(runner)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / 'project with spaces'
        self.project.mkdir()
        self.previous = runner.ROOT
        runner.ROOT = self.root / 'state'
        self.addCleanup(setattr, runner, 'ROOT', self.previous)
        self.id = 'job-20260912T120000-123456abcdef'
        self.path = runner.ROOT / 'jobs' / self.id
        self.path.mkdir(parents=True)
        (self.path / 'output').mkdir()

    def job(self, code, *args):
        runner.save(self.path / 'job.json', dict(project=str(self.project),
                    command=[sys.executable, '-c', code, *args], gpu='GPU-aabb-1234'))

    def result(self):
        return json.loads((self.path / 'result.json').read_text())

    def test_command_cwd_output_and_literal_arguments(self):
        self.job('import os,sys; print(os.getcwd()); print(sys.argv[1]); '
                 'print(os.environ["CUDA_VISIBLE_DEVICES"]); '
                 'open(os.path.join(os.environ["GPU_JOB_OUTPUT_DIR"],"saved"),"w").write("ok")',
                 '$(touch SHOULD_NOT_EXIST); spaces')
        self.assertEqual(runner.worker(self.id), 0)
        log = (self.path / 'train.log').read_text()
        self.assertIn(str(self.project), log)
        self.assertIn('$(touch SHOULD_NOT_EXIST); spaces', log)
        self.assertIn('GPU-aabb-1234', log)
        self.assertEqual((self.path / 'output/saved').read_text(), 'ok')
        self.assertEqual(self.result()['state'], 'succeeded')
        self.assertFalse((self.project / 'SHOULD_NOT_EXIST').exists())

    def test_nonzero_exit(self):
        self.job('import sys; print("failure"); sys.exit(7)')
        self.assertEqual(runner.worker(self.id), 7)
        self.assertEqual(self.result()['exit_code'], 7)
        self.assertEqual(self.result()['state'], 'failed')

    def test_missing_executable(self):
        self.job('pass')
        data = json.loads((self.path / 'job.json').read_text())
        data['command'] = ['/does/not/exist']
        runner.save(self.path / 'job.json', data)
        self.assertEqual(runner.worker(self.id), 127)
        self.assertEqual(self.result()['state'], 'failed')

    def test_gpu_lock_and_release(self):
        self.job('pass')
        locks = runner.ROOT / 'locks'
        locks.mkdir()
        with (locks / 'GPU-aabb-1234.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(runner.worker(self.id), 75)
            self.assertEqual(self.result()['state'], 'gpu_busy')
        self.assertEqual(runner.worker(self.id), 0)

    def test_bad_job_id(self):
        with self.assertRaises(ValueError):
            runner.job_path('../../outside')

    def test_submit_preserves_venv_path_and_snapshots(self):
        venv = self.project / '.venv/bin'
        venv.mkdir(parents=True)
        (venv / 'python').symlink_to(sys.executable)
        (self.project / 'uv.lock').write_text('test lock')
        args = argparse.Namespace(project=self.project, gpu='0',
                                  command=['--', '.venv/bin/python', '-c', 'print("$HOME")'])
        responses = ['GPU-aabb-1234', 'yes', '', 'revision', '']
        with patch.object(runner, 'query', side_effect=responses), \
             patch.object(runner.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(runner.submit(args), 0)
        path = runner.ROOT / 'jobs' / output.getvalue().splitlines()[0]
        job = json.loads((path / 'job.json').read_text())
        self.assertEqual(job['command'][0], str(venv / 'python'))
        self.assertEqual(job['command'][-1], 'print("$HOME")')
        self.assertEqual((path / 'uv.lock').read_text(), 'test lock')
        self.assertTrue((path / 'worker.py').exists())
        self.assertIn('--user', run.call_args.args[0])
        self.assertNotIn('--wait', run.call_args.args[0])

    def test_submission_failure_is_recorded(self):
        args = argparse.Namespace(project=self.project, gpu='0', command=[sys.executable, '-V'])
        with patch.object(runner, 'query', side_effect=['GPU-aabb', 'yes', '', 'rev', '']), \
             patch.object(runner.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)), \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(runner.submit(args), 1)
        results = list((runner.ROOT / 'jobs').glob('*/result.json'))
        self.assertEqual(json.loads(results[0].read_text())['state'], 'submission_failed')

    def test_cancellation_records_signal(self):
        self.job('import time; print("ready", flush=True); time.sleep(60)')
        # Run the worker in a separate process so its signal handlers are exercised.
        code = ('import runpy; m=runpy.run_path(' + repr(str(SOURCE)) + '); '
                'm["worker"].__globals__["ROOT"]=__import__("pathlib").Path(' + repr(str(runner.ROOT)) + '); '
                'raise SystemExit(m["worker"](' + repr(self.id) + '))')
        process = subprocess.Popen([sys.executable, '-c', code])
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                log = self.path / 'train.log'
                if log.exists() and 'ready' in log.read_text():
                    break
                time.sleep(0.02)
            else:
                self.fail('Worker never started')
            process.send_signal(signal.SIGTERM)
            self.assertEqual(process.wait(timeout=5), 143)
            self.assertEqual(self.result()['state'], 'cancelled')
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()


if __name__ == '__main__':
    unittest.main()
