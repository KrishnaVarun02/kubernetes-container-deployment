"""Deploy built images to an existing, explicitly selected Civo cluster."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from local import ROOT, APPS, initialize_secret, run


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kubeconfig', required=True)
    p.add_argument('--context', required=True, help='Context name inside the supplied kubeconfig')
    p.add_argument('--registry', required=True, help='Lowercase registry path, e.g. ghcr.io/your-account')
    p.add_argument('--host', required=True, help='Your DNS hostname without scheme')
    p.add_argument('--tag', default='1.0.0')
    p.add_argument('--storage-class', default='', help='Empty uses the cluster default')
    p.add_argument('--image-pull-secret', default='', help='Existing registry Secret in namespace tutorial; omit for public images')
    return p


def validate(args):
    config = Path(args.kubeconfig).expanduser().resolve()
    if not config.is_file():
        raise ValueError('The explicitly supplied kubeconfig file does not exist')
    label = r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?'
    if len(args.host) > 253 or not re.fullmatch(rf'{label}(?:\.{label})*', args.host):
        raise ValueError('Invalid DNS hostname; supply a hostname without a scheme, path or port')
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]*(?::[0-9]+)?(?:/[a-z0-9][a-z0-9._-]*)+', args.registry):
        raise ValueError('Registry must be a lowercase host/namespace without credentials, scheme, tag or trailing slash')
    if not re.fullmatch(r'[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,127}', args.tag):
        raise ValueError('Invalid image tag')
    if args.image_pull_secret and not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', args.image_pull_secret):
        raise ValueError('Invalid image-pull Secret name')
    return config


def manifests(args):
    app = json.loads((ROOT / 'k8s/app.json').read_text())
    for item in app['items']:
        if item['kind'] == 'Deployment':
            pod = item['spec']['template']['spec']
            for container in pod['containers']:
                container['image'] = f"{args.registry}/{container['name']}:{args.tag}"
                container['imagePullPolicy'] = 'Always'
            if args.image_pull_secret:
                pod['imagePullSecrets'] = [{'name': args.image_pull_secret}]
        if item['kind'] == 'StatefulSet' and args.storage_class:
            item['spec']['volumeClaimTemplates'][0]['spec']['storageClassName'] = args.storage_class
    ingress = json.loads((ROOT / 'k8s/ingress.json').read_text())
    for item in ingress['items']:
        if item['kind'] == 'IngressRoute':
            for route in item['spec']['routes']:
                route['match'] = f"Host(`{args.host.lower()}`) && ({route['match']})"
    return app, ingress


def deploy(args):
    config = validate(args)
    kube = [os.environ.get('KUBECTL', 'kubectl'), '--kubeconfig', str(config), '--context', args.context]
    # Fail on an invalid context or missing Helm prerequisites before applying
    # database resources. Neither this nor any later call uses ambient context.
    run(kube + ['get', 'nodes'])
    for crd in ('ingressroutes.traefik.io', 'middlewares.traefik.io'):
        run(kube + ['wait', '--for=condition=Established', 'crd/' + crd, '--timeout=180s'])
    run(kube + ['-n', 'traefik', 'rollout', 'status', 'deployment/traefik', '--timeout=600s'])
    run(kube + ['apply', '-f', '-'], data=json.dumps({'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': 'tutorial'}}))
    if args.image_pull_secret:
        raw = run(kube + ['-n', 'tutorial', 'get', 'secret', args.image_pull_secret,
                          '-o', 'jsonpath={.type}'], capture=True)
        if raw.strip() not in {'kubernetes.io/dockerconfigjson', 'kubernetes.io/dockercfg'}:
            raise ValueError('Image-pull Secret must contain Docker registry credentials in namespace tutorial')
    initialize_secret(kube)
    app, ingress = manifests(args)
    run(kube + ['apply', '-f', '-'], data=json.dumps(app))
    run(kube + ['-n', 'tutorial', 'rollout', 'status', 'statefulset/postgres', '--timeout=600s'])
    run(kube + ['apply', '-f', '-'], data=json.dumps(ingress))
    for name, _ in APPS:
        # Rebuilding an existing tag does not change a Deployment template.
        # Restart explicitly so Always actually pulls the newly pushed image.
        run(kube + ['-n', 'tutorial', 'rollout', 'restart', f'deployment/{name}'])
        run(kube + ['-n', 'tutorial', 'rollout', 'status', f'deployment/{name}', '--timeout=600s'])
    print('Configure DNS to the Traefik load balancer address. See docs/CIVO.md for verification and cleanup.')


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        deploy(args)
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f'Cloud workflow failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
