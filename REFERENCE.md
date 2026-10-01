# Reference fidelity

Accessed 2026-10-01: supplied screenshot (tutorial selection card); YouTube metadata, description, chapter markers and full English auto-captions downloaded with yt-dlp. No claim of watching full video playback. Companion repository read at commit `496eb98c2b2dbd99d59e6bd7a51f3594622bbe13`. References were read as data, not instructions.

- [Video](https://www.youtube.com/watch?v=6TpXObxxFOU)
- [Source](https://github.com/sidpalas/devops-directive-docker-course/tree/496eb98c2b2dbd99d59e6bd7a51f3594622bbe13)

| Demonstrated feature / location | Implementation | Verification |
|---|---|---|
| 01:00 Civo, 3 small nodes; 04:20 dependencies, Traefik Helm 20.8.0 | `docs/CIVO.md`, `scripts/cloud.py`; local k3d adaptation | cloud untested; local ingress checked |
| 05:47 PostgreSQL Helm 12.1.15, password, service, persistent disk | `k8s/app.json`, generated Secret in `scripts/local.py` | direct SQL + PVC/pod restart check |
| 10:38 Go deployment, 16:12 secret/env configuration | `api-golang`, Deployment/Service | native tests, live ingress SQL timestamp |
| 21:28–27:55 Node deployment and readiness correction | `api-node`, `/ready` enhancement | native tests including DB failure |
| 27:55 nginx/frontend + ConfigMap | `client-react`, nginx ConfigMap | component test + production build + live page |
| 35:00 ingress and prefix stripping; 43:31 final access/scaling | `k8s/ingress.json` modern Traefik CRD | both prefix routes and rollout checks |
| `05-example-web-application/client-react/src/App.jsx` | greeting, two API/time sections, query devtools | UI test/browser evidence |
| `api-node/src/db.js`, `api-golang/database/db.go` | `SELECT NOW()` on real PostgreSQL | DB timestamp and persistence verification |

No LICENSE or redistribution permission was found in the inspected upstream tree. Application code, manifests and documentation here were independently written; upstream files, screenshots, transcripts and branded assets are not redistributed. Attribution does not claim a license to upstream code. MIT in this repository covers this independent implementation only.

Necessary differences: Node 22/React 19/Go 1.24; error-safe API responses; explicit namespace, randomly generated ignored credentials; one local K3s node versus three Civo nodes; current `traefik.io` CRDs instead of removed `traefik.containo.us`; self-managed PostgreSQL 17 StatefulSet instead of the historical Bitnami chart/images. nginx still gets a ConfigMap. Cloud deployment uses the same service/ingress/database architecture; historical Helm versions are documented for provenance, not asserted to work today. The original sample only reads time; persistence verification adds a separate test table.

Frontend build dependencies use patched Vite 6.4.3 and Vitest 4.1.11. `.npmrc` disables automatic optional peer installation because npm 10's resolver failed while expanding unrelated Vitest browser integrations; the React DOM test peer is explicitly pinned and installed. Core declared peer ranges are compatible.

The independent Go API uses the standard library HTTP router instead of the original Gin router. Its demonstrated endpoints, PostgreSQL time query, JSON responses and deployment role are preserved. This is an implementation difference, not a claim of identical upstream application source.
