"""Deploy built images to an existing, explicitly selected Civo cluster."""
import argparse
import json
import re
from pathlib import Path
from local import ROOT, APPS, initialize_secret, run

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--kubeconfig',required=True)
p.add_argument('--registry',required=True,help='Registry path, e.g. ghcr.io/your-account')
p.add_argument('--host',required=True,help='Your DNS hostname without scheme')
p.add_argument('--tag',default='1.0.0')
p.add_argument('--storage-class',default='',help='Empty uses the cluster default')
args=p.parse_args()
if not re.fullmatch(r'[a-zA-Z0-9.-]+',args.host):p.error('Invalid DNS hostname')
kube=['kubectl','--kubeconfig',str(Path(args.kubeconfig).resolve())]
run(kube+['apply','-f','-'],data=json.dumps({'apiVersion':'v1','kind':'Namespace','metadata':{'name':'tutorial'}}))
initialize_secret(kube)
app=json.loads((ROOT/'k8s/app.json').read_text())
for item in app['items']:
    if item['kind']=='Deployment':
        for c in item['spec']['template']['spec']['containers']:
            c['image']=f"{args.registry}/{c['name']}:{args.tag}";c['imagePullPolicy']='Always'
    if item['kind']=='StatefulSet' and args.storage_class:
        item['spec']['volumeClaimTemplates'][0]['spec']['storageClassName']=args.storage_class
run(kube+['apply','-f','-'],data=json.dumps(app))
ingress=json.loads((ROOT/'k8s/ingress.json').read_text())
for item in ingress['items']:
    if item['kind']=='IngressRoute':
        for r in item['spec']['routes']:r['match']=f"Host(`{args.host}`) && ({r['match']})"
run(kube+['apply','-f','-'],data=json.dumps(ingress))
for name,_ in APPS:run(kube+['-n','tutorial','rollout','status',f'deployment/{name}','--timeout=600s'])
print('Configure DNS to the Traefik load balancer address. See docs/CIVO.md for TLS and cleanup.')
