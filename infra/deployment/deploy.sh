#!/bin/bash
# deploy.sh
# Complete CSA-ACI deployment to Minikube
# Run from the vaibhav/ root directory
#
# Usage:
#   bash infra/deployment/deploy.sh          # full deploy
#   bash infra/deployment/deploy.sh --down   # tear down everything

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "============================================"
echo "  CSA-ACI — Minikube Deployment"
echo "  Project root: $PROJECT_ROOT"
echo "============================================"

# ── Tear down ─────────────────────────────────────────────────────────────────
if [[ "$1" == "--down" ]]; then
    echo ""
    echo "[TEARDOWN] Removing all CSA-ACI resources..."
    kubectl delete -f "$SCRIPT_DIR/" --ignore-not-found
    echo "[TEARDOWN] Done. Cluster is clean."
    exit 0
fi

# ── Pre-flight checks ──────────────────────────────────────────────────────────
echo ""
echo "[1/6] Pre-flight checks..."

# Windows Git Bash: use 'where' fallback for command detection
has_cmd() { command -v "$1" &>/dev/null || where "$1" &>/dev/null 2>&1; }

if ! has_cmd minikube; then
    echo "  ✗ minikube not found. Install from https://minikube.sigs.k8s.io"
    exit 1
fi

if ! has_cmd kubectl; then
    echo "  ✗ kubectl not found."
    exit 1
fi

MINIKUBE_STATUS=$(minikube status --format='{{.Host}}' 2>/dev/null || echo "Stopped")
if [[ "$MINIKUBE_STATUS" != "Running" ]]; then
    echo "  Starting Minikube..."
    minikube start --memory=3000 --cpus=2 --driver=docker
fi

echo "  ✓ Minikube running"

# Enable metrics-server for HPA to work
minikube addons enable metrics-server 2>/dev/null || true
echo "  ✓ metrics-server enabled (required for HPA)"

# ── Build Docker images inside Minikube ───────────────────────────────────────
echo ""
echo "[2/6] Building Docker images inside Minikube..."
echo "  (This uses Minikube's Docker daemon so images are available to pods)"

# Point Docker CLI to Minikube's daemon
eval $(minikube docker-env)

# Build backend
echo "  Building csa-aci-backend..."
docker build \
    -f "$PROJECT_ROOT/backend/Dockerfile" \
    -t csa-aci-backend:latest \
    "$PROJECT_ROOT"
echo "  ✓ csa-aci-backend:latest built"

# Build frontend
echo "  Building csa-aci-frontend..."
docker build \
    -f "$PROJECT_ROOT/frontend/Dockerfile" \
    -t csa-aci-frontend:latest \
    "$PROJECT_ROOT/frontend"
echo "  ✓ csa-aci-frontend:latest built"

# ── Apply manifests ────────────────────────────────────────────────────────────
echo ""
echo "[3/6] Applying Kubernetes manifests..."

kubectl apply -f "$SCRIPT_DIR/secrets.yaml"
echo "  ✓ secrets"

kubectl apply -f "$SCRIPT_DIR/postgres.yaml"
echo "  ✓ postgres (StatefulSet + PVC + Service)"

kubectl apply -f "$SCRIPT_DIR/redis.yaml"
echo "  ✓ redis"

kubectl apply -f "$SCRIPT_DIR/backend.yaml"
echo "  ✓ backend (2 replicas)"

kubectl apply -f "$SCRIPT_DIR/frontend.yaml"
echo "  ✓ frontend"

kubectl apply -f "$SCRIPT_DIR/nginx.yaml"
echo "  ✓ nginx (NodePort 30080)"

kubectl apply -f "$SCRIPT_DIR/hpa.yaml"
echo "  ✓ HPA (backend: 2-6 replicas, CPU 60%)"

# ── Wait for pods ──────────────────────────────────────────────────────────────
echo ""
echo "[4/6] Waiting for pods to be ready..."

kubectl wait --for=condition=ready pod \
    -l app=postgres \
    --timeout=120s

kubectl wait --for=condition=ready pod \
    -l app=redis \
    --timeout=60s

kubectl wait --for=condition=ready pod \
    -l app=backend \
    --timeout=120s

kubectl wait --for=condition=ready pod \
    -l app=frontend \
    --timeout=120s

kubectl wait --for=condition=ready pod \
    -l app=nginx \
    --timeout=60s

echo "  ✓ All pods ready"

# ── Run DB migration ───────────────────────────────────────────────────────────
echo ""
echo "[5/6] Running database migration..."

POSTGRES_POD=$(kubectl get pod -l app=postgres -o jsonpath='{.items[0].metadata.name}')

kubectl exec "$POSTGRES_POD" -- psql -U csa_user -d csa_db -c "
    ALTER TABLE tasks ADD COLUMN IF NOT EXISTS reason VARCHAR;
    ALTER TABLE tasks ADD COLUMN IF NOT EXISTS observed_latency FLOAT;
    ALTER TABLE tasks ADD COLUMN IF NOT EXISTS conflict BOOLEAN DEFAULT FALSE;
    ALTER TABLE tasks ADD COLUMN IF NOT EXISTS capacity_agent VARCHAR;
    ALTER TABLE tasks ADD COLUMN IF NOT EXISTS network_agent VARCHAR;
    UPDATE tasks SET conflict = FALSE WHERE conflict IS NULL;
" 2>/dev/null || echo "  (migration skipped — tables may not exist yet, will be created on first startup)"

echo "  ✓ Migration complete"

# ── Done ───────────────────────────────────────────────────────────────────────
echo ""
echo "[6/6] Deployment complete!"
echo ""
echo "============================================"
echo "  Access the dashboard:"
MINIKUBE_IP=$(minikube ip 2>/dev/null || echo "127.0.0.1")
echo "  http://$MINIKUBE_IP:30080"
echo ""
echo "  Or run: minikube service nginx-service"
echo ""
echo "  Check pod status:  kubectl get pods"
echo "  Check HPA:         kubectl get hpa"
echo "  Backend logs:      kubectl logs -l app=backend -f"
echo ""
echo "  To tear down:      bash deploy.sh --down"
echo "============================================"