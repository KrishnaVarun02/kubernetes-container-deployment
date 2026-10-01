"""Portable, isolated local Kubernetes workflow. Python 3.11+; no pip packages."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.local'
CLUSTER = 'tutorial-containers'
K3D = os.environ.get('K3D', 'k3d')
CONFIG = STATE / 'kubeconfig.yaml'
KUBE = [os.environ.get('KUBECTL', 'kubectl'), '--kubeconfig', str(CONFIG)]
APPS = [('api-node', 'api-node'), ('api-golang', 'api-golang'), ('client-react-nginx', 'client-react')]

def run(args, *, data=None, capture=False):
    print('+', ' '.join(map(str, args)), flush=True)
    return subprocess.run(list(map(str, args)), input=data, text=True, check=True,
                          cwd=ROOT, capture_output=capture).stdout

def kube(*args, **kw):
    return run(KUBE + list(args), **kw)

def initialize_secret(kube_args=KUBE):
    existing=run(kube_args+['-n','tutorial','get','secret','database-url',
                           '--ignore-not-found','-o','json'],capture=True)
    if existing.strip():
        data=json.loads(existing).get('data',{})
        if not {'DATABASE_URL','POSTGRES_PASSWORD'} <= data.keys():
            raise RuntimeError('Existing database-url Secret is incomplete; restore its original values.')
        print('Reusing existing cluster database credentials.')
        return
    pvc=run(kube_args+['-n','tutorial','get','pvc','data-postgres-0',
                      '--ignore-not-found','-o','name'],capture=True)
    if pvc.strip():
        raise RuntimeError('Database PVC exists without its Secret. Restore the original credentials; '
                           'do not generate a new password for initialized PostgreSQL data.')
    password=secrets.token_urlsafe(24)
    secret={'apiVersion':'v1','kind':'Secret','metadata':{'name':'database-url','namespace':'tutorial'},
            'stringData':{'DATABASE_URL':f'postgres://postgres:{password}@db-postgresql:5432/postgres',
                          'POSTGRES_PASSWORD':password}}
    run(kube_args+['apply','-f','-'], data=json.dumps(secret))

def up():
    STATE.mkdir(exist_ok=True)
    clusters=json.loads(run([K3D,'cluster','list','-o','json'],capture=True))
    if not any(c['name']==CLUSTER for c in clusters):
        run([K3D,'cluster','create',CLUSTER,'--image','rancher/k3s:v1.32.5-k3s1',
             '--port','127.0.0.1:8088:80@loadbalancer','--kubeconfig-update-default=false',
             '--kubeconfig-switch-context=false','--wait','--timeout','180s'])
    else:
        run([K3D,'cluster','start',CLUSTER,'--wait','--timeout','180s'])
    CONFIG.write_text(run([K3D,'kubeconfig','get',CLUSTER],capture=True),encoding='utf-8')
    CONFIG.chmod(0o600)
    for name,folder in APPS:
        run(['docker','build','-t',f'tutorial/{name}:1.0.0',folder])
    run([K3D,'image','import',*[f'tutorial/{n}:1.0.0' for n,_ in APPS],'-c',CLUSTER])
    kube('apply','-f','-',data=json.dumps({'apiVersion':'v1','kind':'Namespace','metadata':{'name':'tutorial'}}))
    initialize_secret()
    kube('apply','-f','k8s/app.json')
    kube('-n','tutorial','rollout','status','statefulset/postgres','--timeout=600s')
    for name,_ in APPS:
        kube('-n','tutorial','rollout','restart',f'deployment/{name}')
        kube('-n','tutorial','rollout','status',f'deployment/{name}','--timeout=600s')
    kube('wait','--for=condition=Established','crd/ingressroutes.traefik.io','--timeout=180s')
    kube('-n','kube-system','rollout','status','deployment/traefik','--timeout=180s')
    kube('apply','-f','k8s/ingress.json')
    verify()
    print('Open http://localhost:8088 — refresh or refocus to query PostgreSQL again.')

def verify():
    base='http://127.0.0.1:8088'
    for attempt in range(60):
        try:
            for api in ['golang','node']:
                with urlopen(f'{base}/api/{api}/',timeout=5) as response:
                    payload=json.load(response)
                assert payload['api']==api, payload
                stamp=datetime.fromisoformat(payload['now'].replace('Z','+00:00'))
                assert abs((datetime.now(timezone.utc)-stamp).total_seconds())<60, payload
                print(json.dumps(payload))
            with urlopen(base,timeout=5) as response:
                assert 'id="root"' in response.read().decode()
            break
        except Exception:
            if attempt==59: raise
            time.sleep(2)
    kube('-n','tutorial','exec','postgres-0','--','psql','-U','postgres','-c','SELECT NOW();')
    kube('-n','tutorial','get','pods,pvc,ingressroutes')
    print('PASS: both APIs return current PostgreSQL timestamps through ingress; React HTML accessible.')

def persistence():
    sql="CREATE TABLE IF NOT EXISTS verification (id integer PRIMARY KEY, value text); INSERT INTO verification VALUES (1, 'survives-restart') ON CONFLICT (id) DO UPDATE SET value=EXCLUDED.value;"
    kube('-n','tutorial','exec','postgres-0','--','psql','-U','postgres','-v','ON_ERROR_STOP=1','-c',sql)
    old=json.loads(kube('-n','tutorial','get','pod','postgres-0','-o','json',capture=True))['metadata']['uid']
    kube('-n','tutorial','delete','pod','postgres-0')
    deadline=time.monotonic()+240
    while time.monotonic()<deadline:
        raw=kube('-n','tutorial','get','pod','postgres-0','--ignore-not-found','-o','json',capture=True)
        if raw.strip():
            pod=json.loads(raw)
            ready=any(c['type']=='Ready' and c['status']=='True' for c in pod.get('status',{}).get('conditions',[]))
            if pod['metadata']['uid']!=old and ready:break
        time.sleep(2)
    else:raise RuntimeError('Replacement PostgreSQL pod did not become ready in 240 seconds')
    value=kube('-n','tutorial','exec','postgres-0','--','psql','-U','postgres','-tAc','SELECT value FROM verification WHERE id=1',capture=True)
    assert value.strip()=='survives-restart',value
    verify()
    print('PASS: committed data survived PostgreSQL pod replacement.')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['up','verify','persistence','stop','start','down'])
    action=parser.parse_args().action
    if action=='up':up()
    elif action=='verify':verify()
    elif action=='persistence':persistence()
    elif action in ('stop','start'):run([K3D,'cluster',action,CLUSTER])
    else:
        # Only this dedicated development cluster is deleted. Its PVC data is lost.
        run([K3D,'cluster','delete',CLUSTER])
        CONFIG.unlink(missing_ok=True)
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except (subprocess.CalledProcessError, OSError, AssertionError, RuntimeError) as exc:
        print(f'Workflow failed: {exc}',file=sys.stderr);sys.exit(1)
