"""Offline regression tests for preserving initialized PostgreSQL credentials.

Run on any supported OS with: python -m unittest discover -s tests -v
No subprocess, Kubernetes cluster, credentials, or network is used.
"""
import base64
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / 'scripts' / 'local.py'
SPEC = importlib.util.spec_from_file_location('tutorial_local_workflow', SOURCE)
workflow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workflow)


class InitializeSecretTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.kube = ['kubectl', '--kubeconfig', 'offline-test-kubeconfig.yaml']
        self.output = io.StringIO()
        self.enterContext(patch.object(workflow, 'ROOT', self.directory))
        self.enterContext(patch.object(workflow, 'STATE', self.directory / '.local'))
        self.enterContext(redirect_stdout(self.output))
        self.run = self.enterContext(patch.object(workflow, 'run'))
        self.generate = self.enterContext(
            patch.object(workflow.secrets, 'token_urlsafe', return_value='fixture-random-password')
        )

    def assert_no_files_written(self):
        self.assertEqual(list(self.directory.rglob('*')), [])

    def assert_no_apply(self):
        self.assertFalse(any('apply' in call.args[0] for call in self.run.call_args_list))

    def test_existing_secret_is_reused_without_overwrite_or_generation(self):
        encoded = base64.b64encode(b'fixture-existing-password').decode('ascii')
        self.run.return_value = json.dumps({
            'data': {'DATABASE_URL': encoded, 'POSTGRES_PASSWORD': encoded}
        })

        workflow.initialize_secret(self.kube)

        self.assertEqual(self.run.call_count, 1)
        self.assertIn('secret', self.run.call_args.args[0])
        self.assertEqual(self.run.call_args.args[0][:3], self.kube)
        self.generate.assert_not_called()
        self.assert_no_apply()
        self.assert_no_files_written()
        self.assertNotIn(encoded, self.output.getvalue())

    def test_fresh_cluster_creates_secret_via_stdin_without_password_files(self):
        self.run.side_effect = ['', '', 'secret/database-url created']

        workflow.initialize_secret(self.kube)

        self.generate.assert_called_once_with(24)
        self.assertEqual(self.run.call_count, 3)
        apply = self.run.call_args
        self.assertEqual(apply.args[0], self.kube + ['apply', '-f', '-'])
        secret = json.loads(apply.kwargs['data'])
        self.assertEqual(secret['kind'], 'Secret')
        self.assertEqual(secret['metadata'], {'name': 'database-url', 'namespace': 'tutorial'})
        self.assertEqual(secret['stringData']['POSTGRES_PASSWORD'], 'fixture-random-password')
        self.assertEqual(
            secret['stringData']['DATABASE_URL'],
            'postgres://postgres:fixture-random-password@db-postgresql:5432/postgres',
        )
        self.assertNotIn('fixture-random-password', ' '.join(apply.args[0]))
        self.assertNotIn('fixture-random-password', self.output.getvalue())
        self.assert_no_files_written()

    def test_existing_pvc_without_secret_fails_without_replacing_credentials(self):
        self.run.side_effect = ['', 'persistentvolumeclaim/data-postgres-0\n']

        with self.assertRaisesRegex(RuntimeError, 'PVC exists without its Secret'):
            workflow.initialize_secret(self.kube)

        self.assertEqual(self.run.call_count, 2)
        self.generate.assert_not_called()
        self.assert_no_apply()
        self.assert_no_files_written()

    def test_incomplete_existing_secret_fails_without_generating_a_replacement(self):
        self.run.return_value = json.dumps({'data': {'POSTGRES_PASSWORD': 'Zml4dHVyZQ=='}})

        with self.assertRaisesRegex(RuntimeError, 'Secret is incomplete'):
            workflow.initialize_secret(self.kube)

        self.generate.assert_not_called()
        self.assert_no_apply()
        self.assert_no_files_written()

    def test_permission_and_network_errors_are_not_treated_as_missing_resources(self):
        for failure in [
            subprocess.CalledProcessError(1, ['kubectl'], stderr='Forbidden'),
            OSError('network connection refused'),
        ]:
            for query in ['secret', 'pvc']:
                with self.subTest(failure=type(failure).__name__, query=query):
                    self.run.reset_mock()
                    self.generate.reset_mock()
                    self.run.side_effect = [failure] if query == 'secret' else ['', failure]

                    with self.assertRaises(type(failure)) as raised:
                        workflow.initialize_secret(self.kube)

                    self.assertIs(raised.exception, failure)
                    self.assertEqual(self.run.call_count, 1 if query == 'secret' else 2)
                    self.generate.assert_not_called()
                    self.assert_no_apply()
                    self.assert_no_files_written()


if __name__ == '__main__':
    unittest.main()
