"""Exercise real local Git checkouts and training, with uv installation mocked."""
import argparse
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name('train-submit')
loader = importlib.machinery.SourceFileLoader('train_submit', str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)


class TrainSubmitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'source project'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        (self.repo / 'pyproject.toml').write_text('[project]\nname="test-job"\nversion="0.1.0"\nrequires-python=">=3.13,<3.14"\n')
        (self.repo / 'uv.lock').write_text('test lock fixture\n')
        (self.repo / '.python-version').write_text('3.13.99\n')
        (self.repo / '.gitignore').write_text('.venv/\n')
        (self.repo / 'train.py').write_text('import os, pathlib, sys\n'
            'p=pathlib.Path(os.environ["GPU_JOB_OUTPUT_DIR"])\n'
            '(p/"result.txt").write_text("original:" + sys.argv[1] + ":" + os.environ["DATASET_LABEL"])\n')
        (self.repo / 'train-job.toml').write_text(
            'command=[".venv/bin/python", "train.py", "$(touch HACKED); spaces"]\n'
            '[env]\nDATASET_LABEL="demo-v1"\n')
        self.commit()
        self.sha = self.git('rev-parse', 'HEAD')
        self.uv = self.root / 'fake-uv'
        self.uv.write_text('#!' + sys.executable + '\n' + '''import os, pathlib, sys
if '--version' in sys.argv:
    print('uv test-double'); raise SystemExit(0)
if os.environ.get('TEST_UV_FAIL'):
    raise SystemExit(9)
assert '--locked' in sys.argv
assert '--managed-python' in sys.argv
assert sys.argv[-1] == '3.13.99'
assert os.environ['UV_PROJECT_ENVIRONMENT'] == str(pathlib.Path.cwd()/'.venv')
p=pathlib.Path('.venv/bin'); p.mkdir(parents=True)
(p/'python').write_text('#!'+sys.executable+'\\nimport os,sys\\n'
    'if len(sys.argv)>2 and sys.argv[1]=="-c" and "platform.python_version" in sys.argv[2]:\\n'
    ' print("3.13.99")\\n'
    'else: os.execv('+repr(sys.executable)+', ['+repr(sys.executable)+', *sys.argv[1:]])\\n')
(p/'python').chmod(0o700)
''')
        self.uv.chmod(0o700)
        self.work = self.root / 'submission'
        self.work.mkdir()
        self.output = self.root / 'output'
        self.output.mkdir()
        self.request = self.work / 'request.json'
        module.save(self.request, dict(repo=str(self.repo), revision=self.sha,
                    config='train-job.toml', tools={'git': shutil.which('git'), 'uv': str(self.uv)}))

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True, stderr=subprocess.PIPE).strip()

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')

    def prepare(self, **env):
        with patch.dict(os.environ, {'GPU_JOB_OUTPUT_DIR': str(self.output), **env}), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return module.prepare(self.request)

    def record(self):
        return json.loads((self.output / '_submission/preparation.json').read_text())

    def test_exact_commit_isolated_environment_and_literal_arguments(self):
        (self.repo / 'train.py').write_text('raise SystemExit(99)\n')
        self.commit()
        self.assertEqual(self.prepare(UV_PROJECT_ENVIRONMENT='/wrong', VIRTUAL_ENV='/wrong'), 0)
        self.assertEqual((self.output / 'result.txt').read_text(), 'original:$(touch HACKED); spaces:demo-v1')
        self.assertEqual(self.record()['revision'], self.sha)
        self.assertEqual(self.record()['training_exit_code'], 0)
        self.assertTrue((self.work / 'project/.venv/bin/python').exists())
        self.assertFalse((self.repo / '.venv').exists())
        self.assertFalse((self.work / 'project/HACKED').exists())
        self.assertTrue((self.output / '_submission/uv.lock').exists())

    def test_dependency_failure_never_starts_training(self):
        self.assertEqual(self.prepare(TEST_UV_FAIL='1'), 1)
        self.assertEqual(self.record()['failed_phase'], 'installing')
        self.assertFalse((self.output / 'result.txt').exists())

    def test_missing_lock_is_rejected(self):
        (self.repo / 'uv.lock').unlink()
        self.commit()
        request = json.loads(self.request.read_text())
        request['revision'] = self.git('rev-parse', 'HEAD')
        module.save(self.request, request)
        self.assertEqual(self.prepare(), 1)
        self.assertEqual(self.record()['failed_phase'], 'validating')

    def test_training_exit_code_is_preserved(self):
        (self.repo / 'train.py').write_text('raise SystemExit(7)\n')
        self.commit()
        request = json.loads(self.request.read_text())
        request['revision'] = self.git('rev-parse', 'HEAD')
        module.save(self.request, request)
        self.assertEqual(self.prepare(), 7)
        self.assertEqual(self.record()['phase'], 'finished')
        self.assertEqual(self.record()['training_exit_code'], 7)

    def test_output_placeholder_is_an_argument_not_shell_expansion(self):
        (self.repo / 'train-job.toml').write_text(
            'command=[".venv/bin/python", "-c", '
            '"import pathlib,sys; pathlib.Path(sys.argv[1]).joinpath(\\\"explicit.txt\\\").write_text(\\\"ok\\\")", '
            '"{output}"]\n')
        self.commit()
        request = json.loads(self.request.read_text())
        request['revision'] = self.git('rev-parse', 'HEAD')
        module.save(self.request, request)
        self.assertEqual(self.prepare(), 0)
        self.assertEqual((self.output / 'explicit.txt').read_text(), 'ok')
        self.assertEqual(self.record()['command'][-1], str(self.output))

    def test_reject_path_traversal_and_external_symlink(self):
        with self.assertRaises(ValueError): module.inside(self.repo, '../outside')
        (self.root / 'outside').write_text('secret')
        (self.repo / 'linked').symlink_to(self.root / 'outside')
        with self.assertRaises(ValueError): module.inside(self.repo, 'linked')

    def test_reserved_environment_and_unpinned_python(self):
        (self.repo / 'train-job.toml').write_text('command=[".venv/bin/python", "train.py"]\n[env]\nCUDA_VISIBLE_DEVICES="1"\n')
        with self.assertRaises(ValueError): module.contract(self.repo, 'train-job.toml')
        (self.repo / '.python-version').write_text('3.13\n')
        with self.assertRaises(ValueError): module.contract(self.repo, 'train-job.toml')

    def init_args(self, **changes):
        values = dict(project=self.repo, train='train.py', epochs=120,
                      config='generated.toml', force=False, command=[])
        values.update(changes)
        return argparse.Namespace(**values)

    def test_init_generates_expected_command(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(module.initialize(self.init_args()), 0)
        _, command, _ = module.contract(self.repo, 'generated.toml')
        self.assertEqual(command, ['.venv/bin/python', '-u', 'train.py',
                                  '--epochs', '120', '--output', '{output}'])
        self.assertFalse((self.repo / '.venv').exists())

    def test_init_preserves_existing_file_and_force_replaces(self):
        target = self.repo / 'generated.toml'
        target.write_text('keep me')
        with self.assertRaises(ValueError): module.initialize(self.init_args())
        self.assertEqual(target.read_text(), 'keep me')
        with contextlib.redirect_stdout(io.StringIO()):
            module.initialize(self.init_args(force=True))
        module.contract(self.repo, 'generated.toml')

    def test_init_rejects_invalid_inputs_without_writing(self):
        for changes in ({'epochs': 0}, {'epochs': -1}, {'train': 'missing.py'},
                        {'config': '../outside.toml'}, {'train': None},
                        {'command': ['--', '.venv/bin/python', '-V']}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                module.initialize(self.init_args(**changes))
        self.assertFalse((self.repo / 'generated.toml').exists())

    def test_explicit_command_round_trips_special_characters(self):
        command = ['.venv/bin/python', '-c', 'print("hello")',
                   'line1\nline2', 'back\\slash', 'é😀', '{output}', '$(touch HACKED)']
        with contextlib.redirect_stdout(io.StringIO()):
            module.initialize(self.init_args(train=None, epochs=None, command=['--', *command]))
        self.assertEqual(module.contract(self.repo, 'generated.toml')[1], command)

    def test_init_rejects_symlink_target(self):
        (self.repo / 'generated.toml').symlink_to(self.repo / 'train-job.toml')
        with self.assertRaises(ValueError): module.initialize(self.init_args(force=True))

    def test_validate_checks_lock_without_sync_or_training(self):
        args = argparse.Namespace(project=self.repo, config='train-job.toml')
        with patch.object(module.shutil, 'which', return_value='/fake/uv'), \
             patch.object(module.subprocess, 'run') as run, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(module.validate(args), 0)
        self.assertEqual(run.call_args.args[0],
                         ['/fake/uv', 'lock', '--check', '--managed-python', '--python', '3.13.99'])
        self.assertEqual(run.call_args.kwargs['cwd'], self.repo)
        self.assertFalse((self.repo / '.venv').exists())

    def test_validate_propagates_stale_lock_failure(self):
        args = argparse.Namespace(project=self.repo, config='train-job.toml')
        with patch.object(module.shutil, 'which', return_value='/fake/uv'), \
             patch.object(module.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, ['uv'])):
            with self.assertRaises(subprocess.CalledProcessError): module.validate(args)

    def test_validate_names_invalid_toml_file(self):
        (self.repo / 'train-job.toml').write_text('command = ["broken\n"]')
        with self.assertRaisesRegex(ValueError, 'train-job.toml:'):
            module.validate(argparse.Namespace(project=self.repo, config='train-job.toml'))

    def test_init_cli_and_original_submit_cli_coexist(self):
        result = subprocess.run([sys.executable, str(SOURCE), 'init', '--project', str(self.repo),
                                 '--config', 'generated.toml', '--train', 'train.py', '--epochs', '2'],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(module.contract(self.repo, 'generated.toml')[1][-3:], ['2', '--output', '{output}'])
        with patch.object(sys, 'argv', ['train-submit', '--repo', str(self.repo), '--ref', self.sha]), \
             patch.object(module, 'submit', return_value=0) as submit:
            self.assertEqual(module.main(), 0)
        self.assertEqual(submit.call_args.args[0].ref, self.sha)

    def test_branch_ref_rejected(self):
        args = argparse.Namespace(repo=str(self.repo), ref='main', config='train-job.toml', gpu='0')
        with self.assertRaises(ValueError): module.submit(args)

    def test_submission_uses_gpu_run_for_whole_pipeline(self):
        args = argparse.Namespace(repo=str(self.repo), ref=self.sha, config='train-job.toml', gpu='0')
        with patch.object(module, 'ROOT', self.root / 'requests'), \
             patch.object(module.shutil, 'which', side_effect=lambda name: '/fake/' + name), \
             patch.object(module.subprocess, 'call', return_value=0) as call, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(module.submit(args), 0)
        command = call.call_args.args[0]
        self.assertEqual(command[:2], ['/fake/gpu-run', 'submit'])
        self.assertIn('_prepare', command)
        request = Path(command[-1])
        self.assertEqual(json.loads(request.read_text())['revision'], self.sha)
        self.assertTrue(request.with_name('prepare.py').exists())


if __name__ == '__main__':
    unittest.main()
