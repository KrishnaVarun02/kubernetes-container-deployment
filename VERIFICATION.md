# Verification

Actual local environment on 2026-10-01: macOS 26.6.2, Apple Silicon arm64; Docker 29.5.3 Linux arm64 through Rancher Desktop; k3d 5.8.3; dedicated K3s v1.32.5-k3s1 cluster. Native tests used Node 22.22.0 and Go 1.24.4 with per-project npm dependencies and isolated Go caches. Helper regression tests and final persistence/resume checks used an isolated Python 3.12.13 environment.

| Executed check | Result |
|---|---|
| `npm ci; npm test` in `api-node` | Passed database time, health, readiness and DB-error assertions |
| `go test ./...` in `api-golang` | Passed success and DB-error routes |
| `npm ci; npm test; npm run build` in `client-react` | Passed rendered API time/error cases and production build |
| npm dependency audit after patching build tools | Zero reported vulnerabilities |
| `python -m unittest discover -s tests -v` | Five credential preservation/recovery/network-error tests passed |
| `python scripts/local.py up` | Three images built/imported; four app/database pods ready; ingress configured |
| `python scripts/local.py verify` | Both API paths returned current real PostgreSQL timestamps; frontend HTML fetched; direct SQL succeeded |
| `python scripts/local.py persistence` | Inserted a test row, replaced PostgreSQL pod, waited for new UID + Ready, and confirmed row survived; both APIs still worked |
| Re-initialize existing cluster credentials | Existing Secret reused without overwriting password |
| `stop`, `start`, then `verify` | Cluster shutdown and resume succeeded; application and PostgreSQL accessible afterward |
| Headless Chrome screenshot | Actual React page displayed both API names and DB times; visually inspected [screenshot](evidence/app-macos.png) |

[Sanitized terminal evidence](evidence/kubernetes-macos.txt) records the actual SQL/ingress/persistence results. No fixture response was used in container checks. The API unit tests explicitly inject fixed database responses.

The first cold PostgreSQL image pull exceeded the original 240-second deadline while another large local download consumed bandwidth. The helper's first-rollout deadline was raised to 600 seconds and the actual workflow rerun successfully. The initial deployment used the host's existing kubectl 1.36.0; the final persistence and stop/resume checks used downloaded kubectl **1.32.5**, matching the documented prerequisite and CI configuration. Existing external Kubernetes context was unchanged. No external cluster resources were touched.

Review also repaired two concrete rerun hazards: replacing credentials for a retained PVC, and treating stale StatefulSet status as proof a replacement pod was ready. These paths have regression coverage. The app is an independent implementation; no upstream code without a license or upstream image assets were republished.

## Platform and deployment limits

Native macOS arm64 application tests and the complete local Linux-arm64-container Kubernetes workflow were actually executed. Windows/macOS/Linux native jobs and a Linux-amd64 Kubernetes job are configured in `.github/workflows/ci.yml`; their actual run result must be inspected after publication. A Linux CI container job does **not** verify Docker Desktop/WSL2 on a Windows desktop. Windows local Kubernetes setup, macOS Intel, Windows ARM64 and Civo deployment have not been tested here.

Civo configuration is supplied separately in `docs/CIVO.md` and `scripts/cloud.py`; no cloud infrastructure was provisioned, no DNS or TLS setup performed, and no cloud charges incurred.
