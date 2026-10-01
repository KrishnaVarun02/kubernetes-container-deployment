# Civo deployment: original and adapted

The video creates a 3-node small Civo K3s cluster, disables its preinstalled ingress controller, retrieves kubeconfig, then installs Traefik and PostgreSQL through Helm. The companion Makefile pins Traefik chart **20.8.0** and Bitnami PostgreSQL **12.1.15**, then applies the API/frontend/IngressRoute resources. Historical image tags are Go `:8`, Node `:9`, React/nginx `:5` under `sidpalas/devops-directive-docker-course-*`. These record provenance; this implementation builds its own images. Historical manifests use `traefik.containo.us/v1alpha1`.

The adaptation uses Traefik chart **35.0.0** (Traefik **3.3.5**), modern `traefik.io/v1alpha1` routes, and a PostgreSQL **17.5** StatefulSet with a 1 GiB PVC. This avoids the historical Bitnami image dependency. Local k3d uses the Traefik bundled with pinned K3s instead of Helm. The sample displays current database timestamps; it has no user content, authentication or CRUD. Chart version, CRDs and default LoadBalancer service were checked by rendering the [official pinned chart](https://github.com/traefik/traefik-helm-chart/tree/v35.0.0/traefik). Cloud deployment has not been executed.

## Prerequisites and cluster selection

Run commands from the repository root. Install Python 3.12.13, Docker Desktop with Linux containers and Buildx, Helm 3, and kubectl matching the cluster's Kubernetes minor version. Windows uses PowerShell and Docker Desktop's WSL2 backend; macOS supports Apple Silicon and Intel. Builds below publish both Linux arm64 and amd64 images. Cloud nodes run Linux regardless of the developer's operating system.

After obtaining spending approval, create a dedicated Civo K3s cluster, explicitly choose its region/node sizes, and disable the bundled Traefik option. The custom Helm release will create its LoadBalancer. Cluster, storage and load balancer resources may be billable. Follow [Civo's cluster instructions](https://www.civo.com/docs/kubernetes/create-a-cluster).

Create the ignored `.local` directory with `mkdir -p .local` on macOS or `New-Item -ItemType Directory -Force .local` in PowerShell. Download the cluster kubeconfig into `.local/civo.yaml`. List its context names:

```text
kubectl --kubeconfig .local/civo.yaml config get-contexts
```

Replace `CIVO_CONTEXT` in every command below with the exact intended context name; quote it if it contains spaces. Every cluster command supplies both file and context, without changing your global current context.

```text
kubectl --kubeconfig .local/civo.yaml --context CIVO_CONTEXT get nodes
kubectl --kubeconfig .local/civo.yaml --context CIVO_CONTEXT get storageclass
```

## Build and publish images

Replace `your-account` with your **lowercase** registry namespace. For GHCR, authenticate locally using `docker login ghcr.io --username your-account` and a personal access token with `write:packages` at its password prompt. See [GitHub's registry authentication and visibility instructions](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry). Never add the token to this repository.

These commands work in both PowerShell and macOS shells. The explicitly selected temporary builder supports multi-platform output without changing your selected Docker builder. See [Docker's multi-platform build instructions](https://docs.docker.com/build/building/multi-platform/).

```text
docker buildx create --name tutorial-builder --driver docker-container
docker buildx build --builder tutorial-builder --platform linux/amd64,linux/arm64 -t ghcr.io/your-account/api-node:1.0.0 --push api-node
docker buildx build --builder tutorial-builder --platform linux/amd64,linux/arm64 -t ghcr.io/your-account/api-golang:1.0.0 --push api-golang
docker buildx build --builder tutorial-builder --platform linux/amd64,linux/arm64 -t ghcr.io/your-account/client-react-nginx:1.0.0 --push client-react
docker buildx rm tutorial-builder
```

GHCR packages are initially **private**, even when the source repository is public. For the default anonymous cluster pulls, open each of the three packages' settings in GitHub and change its visibility to public. Verify all three packages show public visibility before deploying. Local Docker login does not authenticate Kubernetes nodes.

For private images instead, create namespace `tutorial` in the selected cluster, then create a Docker registry Secret there following [Kubernetes' private registry instructions](https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/). Add `--image-pull-secret registry-auth` to the deployment command, using your actual Secret name. The script requires an existing `kubernetes.io/dockerconfigjson` or `kubernetes.io/dockercfg` Secret and attaches it to all three application Deployments. It does not create or print registry credentials.

## Install ingress and deploy

Use the dedicated cluster with its bundled ingress disabled. These Helm commands work in PowerShell and macOS:

```text
helm repo add traefik https://traefik.github.io/charts
helm repo update
helm upgrade --install traefik traefik/traefik --version 35.0.0 --namespace traefik --create-namespace --kubeconfig .local/civo.yaml --kube-context CIVO_CONTEXT --wait --timeout 10m
```

Deploy on macOS, substituting your registry namespace and real DNS host:

```sh
python3 scripts/cloud.py --kubeconfig .local/civo.yaml --context CIVO_CONTEXT --registry ghcr.io/your-account --host demo.example.com
```

PowerShell:

```powershell
py -3.12 scripts/cloud.py --kubeconfig .local/civo.yaml --context CIVO_CONTEXT --registry ghcr.io/your-account --host demo.example.com
```

The script checks Traefik's CRDs and controller rollout, preserves an existing database Secret, or generates a random password for a fresh database and applies it through stdin. It never prints credentials or saves them in project files. Back up the Secret securely: an existing PVC retains its original password. If the PVC exists but the Secret is missing, deployment stops with a recovery message instead of replacing credentials.

Add `--storage-class CLASS` for a fresh installation if there is no default StorageClass. Changing an existing StatefulSet/PVC's storage class requires a separate data migration. Add `--tag VERSION` if you pushed another tag. Deployment waits for PostgreSQL, explicitly restarts each application and waits for rollout, so rebuilding the same tag also updates running pods. Prefer a new version tag when retaining rollback history.

## Verify the cloud application

```text
kubectl --kubeconfig .local/civo.yaml --context CIVO_CONTEXT -n traefik get service traefik
kubectl --kubeconfig .local/civo.yaml --context CIVO_CONTEXT -n tutorial get pods,pvc,ingressroutes
kubectl --kubeconfig .local/civo.yaml --context CIVO_CONTEXT -n tutorial exec postgres-0 -- psql -U postgres -c "SELECT NOW();"
```

Wait for Traefik's external IP and set the host's DNS A record to that IP. Open `http://demo.example.com/` and refresh to see both PostgreSQL timestamps update. Test each API on macOS:

```sh
curl --fail http://demo.example.com/api/node/
curl --fail http://demo.example.com/api/golang/
```

PowerShell uses `curl.exe --fail` with the same URLs. Both API responses must contain their API name and a current `now` timestamp. Before DNS propagates, add `--resolve demo.example.com:80:LOAD_BALANCER_IP` to curl, replacing the IP placeholder. The host header must match the host passed to the script.

To reproduce API scaling:

```text
kubectl --kubeconfig .local/civo.yaml --context CIVO_CONTEXT -n tutorial scale deployment/api-node --replicas=3
kubectl --kubeconfig .local/civo.yaml --context CIVO_CONTEXT -n tutorial rollout status deployment/api-node --timeout=600s
```

The video demonstrates HTTP. Configure Traefik TLS and a certificate before adding sensitive data. No API key, real domain or cloud credentials are embedded here.

## Cleanup

These commands delete the application's database data and remove the Helm load balancer in the selected dedicated cluster:

```text
kubectl --kubeconfig .local/civo.yaml --context CIVO_CONTEXT delete namespace tutorial
helm uninstall traefik --namespace traefik --kubeconfig .local/civo.yaml --kube-context CIVO_CONTEXT
```

Then delete the dedicated cluster and any remaining volumes/load balancers in Civo and verify billing resources are gone. Do not delete an unrelated shared cluster. If an image build was interrupted, remove only its temporary builder with `docker buildx rm tutorial-builder`. Local cleanup is documented in the main README.

Cloud status: configuration supplied and offline tests passed; no Civo cluster or load balancer created, no spending authorized, no cloud rollout or registry authentication verified.
