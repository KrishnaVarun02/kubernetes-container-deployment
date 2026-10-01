# Kubernetes container deployment

Independent implementation of DevOps Directive's database-time sample: React + nginx → Traefik → Node/Go APIs → PostgreSQL. The page displays **Hey Team! 👋**, each API name and **Time from DB**. The APIs query `SELECT NOW()` on every request. There is no invented CRUD application.

## Prerequisites

- Docker Desktop (Linux containers; Windows requires WSL2) or a compatible Docker engine. Allocate at least 4 CPUs, 6 GB RAM and 10 GB disk. Start it first.
- Python 3.11+, kubectl 1.32.x and k3d **5.8.3** on PATH. [k3d releases](https://github.com/k3d-io/k3d/releases/tag/v5.8.3) provide Windows amd64 and macOS arm64/amd64 executables; rename to `k3d.exe`/`k3d` and put on PATH. On macOS `chmod +x k3d` after downloading.
- Native component tests additionally use Node **22.x** (tested 22.22.0) and Go **1.24.4**.

All application and base images used locally support Linux arm64 and amd64. On Apple Silicon use native arm64; on Windows x86 use amd64. Do not force amd64 emulation on Apple Silicon. Windows ARM64 is not verified. Each Dockerfile pins a version; npm and Go lockfiles pin application dependencies.

## Start and demonstrate (macOS zsh/bash)

```sh
python3 scripts/local.py up
python3 scripts/local.py verify
python3 scripts/local.py persistence
open http://localhost:8088
```

## Start and demonstrate (Windows PowerShell)

```powershell
py -3 scripts/local.py up
py -3 scripts/local.py verify
py -3 scripts/local.py persistence
Start-Process http://localhost:8088
```

Both procedures build three images, create the dedicated `tutorial-containers` k3d cluster, import images, generate a random database Secret (stored only in the cluster), deploy PostgreSQL with a PVC, wait for rollouts and install Traefik routes. Existing credentials are reused on subsequent runs. K3s `v1.32.5-k3s1` supplies Traefik and local-path storage. No cloud account is needed. All kubectl calls explicitly use `.local/kubeconfig.yaml`; your current cluster context is not used or changed.

`verify` checks both API responses through ingress against UTC time, fetches the real HTML and queries PostgreSQL directly. `persistence` creates a verification row, replaces the database pod, then checks the row survived. Refresh/refocus the page to request new database timestamps (TanStack Query behavior).

Sample routes: `http://localhost:8088/api/node/`, `/api/golang/`, `/api/node/ping`, `/api/golang/ping`. Go `/ping` returns JSON `"pong"` and checks the database, matching the source. Node `/ping` returns plain `pong`; the added `/ready` checks the database. Failures return a clear 503 instead of terminating the Go process.

## Tests

The following work in PowerShell and macOS shells after installing Node and Go:

```text
cd api-node
npm ci
npm test
cd ../api-golang
go test ./...
cd ../client-react
npm ci
npm test
npm run build
cd ..
```

Tests use injected database functions and mocked HTTP for deterministic cases; local Kubernetes verification always uses real PostgreSQL. CI runs component tests on Windows, macOS and Linux, plus the complete k3d rollout and persistence workflow on Linux. See [VERIFICATION.md](VERIFICATION.md) for actual results, distinct from configured jobs.

Credential workflow tests: `python3 -m unittest discover -s tests -v` (macOS), or `py -3 -m unittest discover -s tests -v` (PowerShell). These ensure re-deployment preserves database credentials and refuses to replace missing credentials for retained data.

For native API debugging, set `DATABASE_URL` (or `DATABASE_URL_FILE`) to your own PostgreSQL, then run `npm start` in `api-node` or `go run .` in `api-golang`. Go defaults to 8080 and Node to 3000. The primary runnable tutorial workflow is Kubernetes; frontend dev requires a reverse proxy for `/api/*` or the deployed nginx/Traefik path.

## Stop and cleanup

macOS: `python3 scripts/local.py stop` suspends the cluster; `python3 scripts/local.py start` resumes it. Windows: replace `python3` with `py -3`.

`python3 scripts/local.py down` / `py -3 scripts/local.py down` **deletes this cluster and its database data**. It does not affect other clusters. Optionally remove the images using `docker image rm tutorial/api-node:1.0.0 tutorial/api-golang:1.0.0 tutorial/client-react-nginx:1.0.0`. Remove ignored `.local` with `rm -rf .local` (macOS) or `Remove-Item -Recurse -Force .local` (PowerShell). `node_modules`, `dist` and Go caches can also be removed after testing.

## Original cloud workflow

[docs/CIVO.md](docs/CIVO.md) distinguishes the original Civo/Helm versions from the runnable current configuration. Deploying Civo infrastructure incurs charges and is a separate manual action. No cloud deployment is claimed. [REFERENCE.md](REFERENCE.md) records captions, source locations, access and licensing.
