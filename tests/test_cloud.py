"""Offline cloud workflow tests; every kubectl call and credential action is mocked."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
with patch.object(sys, 'path', [str(SCRIPTS), *sys.path]):
    SPEC = importlib.util.spec_from_file_location('tutorial_cloud_workflow', SCRIPTS / 'cloud.py')
    cloud = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(cloud)


class CloudWorkflowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.config = Path(temporary.name) / 'selected kubeconfig.yaml'
        self.config.write_text('authored fixture, not real credentials')
        self.args = cloud.parser().parse_args([
            '--kubeconfig', str(self.config), '--context', 'chosen-civo-context',
            '--registry', 'ghcr.io/fixture-owner', '--host', 'Demo.Example.Invalid',
        ])
        self.run = self.enterContext(patch.object(cloud, 'run', return_value=''))
        self.secret = self.enterContext(patch.object(cloud, 'initialize_secret'))
        self.enterContext(redirect_stdout(io.StringIO()))

    def test_every_cluster_call_and_secret_use_explicit_file_and_context(self):
        with patch.dict('os.environ', {'KUBECTL': 'selected-kubectl'}):
            cloud.deploy(self.args)
        prefix = ['selected-kubectl', '--kubeconfig', str(self.config.resolve()), '--context', 'chosen-civo-context']
        for call in self.run.call_args_list:
            self.assertEqual(call.args[0][:len(prefix)], prefix)
            self.assertNotIn('use-context', call.args[0])
        self.secret.assert_called_once_with(prefix)

    def test_public_manifest_rewrite_keeps_database_and_local_templates_intact(self):
        before = (cloud.ROOT / 'k8s/app.json').read_text()
        self.args.storage_class = 'civo-fixture-storage'
        app, ingress = cloud.manifests(self.args)
        deployments = [x for x in app['items'] if x['kind'] == 'Deployment']
        self.assertEqual(len(deployments), 3)
        for item in deployments:
            pod = item['spec']['template']['spec']
            self.assertNotIn('imagePullSecrets', pod)
            for container in pod['containers']:
                self.assertEqual(container['image'], f"ghcr.io/fixture-owner/{container['name']}:1.0.0")
                self.assertEqual(container['imagePullPolicy'], 'Always')
        database = next(x for x in app['items'] if x['kind'] == 'StatefulSet')
        self.assertTrue(database['spec']['template']['spec']['containers'][0]['image'].startswith('postgres:'))
        self.assertEqual(database['spec']['volumeClaimTemplates'][0]['spec']['storageClassName'], 'civo-fixture-storage')
        route = next(x for x in ingress['items'] if x['kind'] == 'IngressRoute')
        self.assertEqual(route['apiVersion'], 'traefik.io/v1alpha1')
        self.assertTrue(all(x['match'].startswith('Host(`demo.example.invalid`) && ') for x in route['spec']['routes']))
        self.assertEqual((cloud.ROOT / 'k8s/app.json').read_text(), before)

    def test_same_tag_deployment_restarts_and_waits_for_each_application(self):
        cloud.deploy(self.args)
        commands = [call.args[0] for call in self.run.call_args_list]
        postgres = next(i for i, cmd in enumerate(commands) if 'statefulset/postgres' in cmd)
        for name, _ in cloud.APPS:
            restart = next(i for i, cmd in enumerate(commands) if 'restart' in cmd and f'deployment/{name}' in cmd)
            status = next(i for i, cmd in enumerate(commands) if 'status' in cmd and f'deployment/{name}' in cmd)
            self.assertLess(postgres, restart)
            self.assertLess(restart, status)

    def test_private_registry_requires_valid_namespaced_pull_secret(self):
        self.args.image_pull_secret = 'registry-auth'
        self.run.return_value = 'kubernetes.io/dockerconfigjson'
        cloud.deploy(self.args)
        apps = [json.loads(call.kwargs['data']) for call in self.run.call_args_list
                if call.kwargs.get('data') and 'Deployment' in call.kwargs['data']]
        for item in apps[0]['items']:
            if item['kind'] == 'Deployment':
                self.assertEqual(item['spec']['template']['spec']['imagePullSecrets'], [{'name': 'registry-auth'}])
        self.run.reset_mock()
        self.secret.reset_mock()
        self.run.return_value = 'Opaque'
        with self.assertRaisesRegex(ValueError, 'Docker registry credentials'):
            cloud.deploy(self.args)
        self.secret.assert_not_called()

    def test_invalid_configuration_makes_no_cluster_calls(self):
        for key, value in [('host', 'demo.example/route'), ('host', '-invalid.example'),
                           ('registry', 'ghcr.io/MixedCase'), ('registry', 'https://ghcr.io/user'),
                           ('tag', 'bad/tag'), ('kubeconfig', str(self.config) + '.missing')]:
            with self.subTest(key=key, value=value):
                original = getattr(self.args, key)
                setattr(self.args, key, value)
                with self.assertRaises(ValueError):
                    cloud.deploy(self.args)
                setattr(self.args, key, original)
                self.run.assert_not_called()
                self.secret.assert_not_called()


if __name__ == '__main__':
    unittest.main()
