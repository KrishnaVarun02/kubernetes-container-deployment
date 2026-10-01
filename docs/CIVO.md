# Civo deployment: original and adapted

The video creates a 3-node small Civo K3s cluster, disables its preinstalled ingress controller, retrieves kubeconfig, then installs Traefik and PostgreSQL through Helm. The companion Makefile pins Traefik chart **20.8.0** and Bitnami PostgreSQL **12.1.15**, then applies the API/frontend/IngressRoute resources. Historical image tags are Go `:8`, Node `:9`, React/nginx `:5` under `sidpalas/devops-directive-docker-course-*`. Those are provenance, not images redistributed or required by this implementation. Historical manifest schema is `traefik.containo.us/v1alpha1`.

The runnable adaptation uses your own built images, Traefik chart **35.0.0**, modern `traefik.io/v1alpha1` routing, and a PostgreSQL **17.5** StatefulSet with a 1 GiB PVC. This avoids relying on retired Bitnami image distribution. Local k3d uses the Traefik bundled with pinned K3s instead of Helm. The sample has no user content, authentication or CRUD.

## After obtaining spending approval

1. In Civo, create a K3s cluster, choose the region/node sizes explicitly, disable the bundled Traefik option (the custom Helm release will create its LoadBalancer), download its kubeconfig into `.local/civo.yaml`, and check the nodes with `kubectl --kubeconfig .local/civo.yaml get nodes`. Use your cluster's default storage class (`kubectl --kubeconfig .local/civo.yaml get storageclass`). This step and the load balancer/storage may be billable. See [Civo's cluster instructions](https://www.civo.com/docs/kubernetes/create-a-cluster).
2. Log Docker into your chosen container registry. Build/push public images for each service. For example, on both PowerShell and macOS (substitute your registry):

```text
docker buildx build --platform linux/amd64,linux/arm64 -t ghcr.io/YOUR_ACCOUNT/api-node:1.0.0 --push api-node
docker buildx build --platform linux/amd64,linux/arm64 -t ghcr.io/YOUR_ACCOUNT/api-golang:1.0.0 --push api-golang
docker buildx build --platform linux/amd64,linux/arm64 -t ghcr.io/YOUR_ACCOUNT/client-react-nginx:1.0.0 --push client-react
helm repo add traefik https://traefik.github.io/charts
helm repo update
helm upgrade --install traefik traefik/traefik --version 35.0.0 --namespace traefik --create-namespace --kubeconfig .local/civo.yaml --wait
```

If the current Docker builder does not support multiple platforms, first run `docker buildx create --name tutorial-builder --driver docker-container` and add `--builder tutorial-builder` to each build command. This avoids changing your selected builder. After all builds, remove only that temporary builder with `docker buildx rm tutorial-builder`.

3. Deploy (macOS):

```sh
python3 scripts/cloud.py --kubeconfig .local/civo.yaml --registry ghcr.io/YOUR_ACCOUNT --host demo.YOUR_DOMAIN
kubectl --kubeconfig .local/civo.yaml -n traefik get service traefik
```

PowerShell: replace `python3` with `py -3`. The script reuses the existing database Secret or generates a random password for a fresh database and applies it through stdin. It never prints credentials or saves them in project files. Back up the Secret securely; an existing PVC retains its original password. If a PVC exists but the Secret is missing, deployment stops with a recovery message instead of replacing credentials. Add `--storage-class CLASS` if there is no default storage class.

4. Set a DNS A record for the host to Traefik's external IP. Test `http://demo.YOUR_DOMAIN/`, `/api/node/` and `/api/golang/`, confirm different current DB timestamps, and inspect `kubectl --kubeconfig .local/civo.yaml -n tutorial get pods,pvc`. Scale an API with `kubectl --kubeconfig .local/civo.yaml -n tutorial scale deployment/api-node --replicas=3` and wait for rollout.

The video demonstrates HTTP. For public use configure Traefik TLS and a certificate for your domain before adding sensitive data. No API key, actual domain or cloud credentials are embedded here.

## Cleanup

Delete the application namespace (and PVC data): `kubectl --kubeconfig .local/civo.yaml delete namespace tutorial`. Remove the Helm load balancer: `helm uninstall traefik --namespace traefik --kubeconfig .local/civo.yaml`. Then delete the dedicated cluster and any remaining volumes/load balancers in Civo and verify billing resources are gone. Do not delete an unrelated shared cluster. Local cleanup is documented in the main README.

Cloud status: configuration supplied, no Civo cluster or load balancer created, no spending authorized, no cloud rollout verified.
