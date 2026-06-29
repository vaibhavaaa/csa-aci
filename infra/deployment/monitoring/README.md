# Monitoring (Prometheus + Grafana)

In-cluster observability for the CSA-ACI backend. Self-contained — no Prometheus
Operator or CRDs required, so it runs on plain Minikube.

## What's here
- **prometheus.yaml** — Prometheus + RBAC (ServiceAccount/ClusterRole/Binding)
  for pod discovery. Scrapes any pod annotated `prometheus.io/scrape: "true"`;
  the backend Deployment sets that annotation on port `8000`, path `/metrics`.
- **grafana.yaml** — Grafana with a provisioned Prometheus datasource and a
  pre-loaded **"CSA-ACI Backend"** dashboard (request rate, p95 latency,
  per-handler rate). Exposed on NodePort `30030`.

## Metrics source
The backend exposes Prometheus metrics at `/metrics` via
`prometheus-fastapi-instrumentator` (wired in `backend/app/main.py`): HTTP
request count, duration histogram, and request/response sizes.

## Deploy
The main `deploy.sh` / `deploy.ps1` apply this directory automatically. To apply
just the monitoring stack against an existing cluster:

```bash
kubectl apply -f infra/deployment/monitoring/
```

## Access
```bash
# Grafana (anonymous viewer is enabled; admin login is admin/admin)
minikube service grafana-service          # opens the dashboard in a browser

# Prometheus (ClusterIP — port-forward to reach it locally)
kubectl port-forward svc/prometheus-service 9090:9090
#   then open http://localhost:9090/targets to confirm the backend is UP
```
