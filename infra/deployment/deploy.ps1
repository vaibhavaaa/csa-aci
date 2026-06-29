# deploy.ps1
# CSA-ACI Minikube deployment for Windows
# Usage:
#   powershell -ExecutionPolicy Bypass -File infra\deployment\deploy.ps1
#   powershell -ExecutionPolicy Bypass -File infra\deployment\deploy.ps1 -Down

param([switch]$Down)

$ErrorActionPreference = "Stop"
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Get-Item "$ScriptDir\..\.." ).FullName

Write-Host "CSA-ACI Minikube Deployment" -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot"

# Tear down
if ($Down) {
    Write-Host "Removing all CSA-ACI resources..." -ForegroundColor Yellow
    kubectl delete -f "$ScriptDir\monitoring\" --ignore-not-found
    kubectl delete -f "$ScriptDir\" --ignore-not-found
    Write-Host "Done." -ForegroundColor Green
    exit 0
}

# Step 1 - Pre-flight
Write-Host ""
Write-Host "[1/6] Pre-flight checks..." -ForegroundColor White

$status = minikube status --format="{{.Host}}" 2>$null
if ($status -ne "Running") {
    Write-Host "Starting Minikube..." -ForegroundColor Yellow
    minikube start --memory=3000 --cpus=2 --driver=docker
}
Write-Host "Minikube is running" -ForegroundColor Green

minikube addons enable metrics-server 2>$null
Write-Host "metrics-server enabled" -ForegroundColor Green

# Step 2 - Build images
Write-Host ""
Write-Host "[2/6] Building Docker images inside Minikube..." -ForegroundColor White

minikube docker-env --shell powershell | Invoke-Expression

Write-Host "Building backend image..." -ForegroundColor Yellow
docker build -f "$ProjectRoot\backend\Dockerfile" -t csa-aci-backend:latest "$ProjectRoot"
Write-Host "Backend image built" -ForegroundColor Green

Write-Host "Building frontend image..." -ForegroundColor Yellow
docker build -f "$ProjectRoot\frontend\Dockerfile" -t csa-aci-frontend:latest "$ProjectRoot\frontend"
Write-Host "Frontend image built" -ForegroundColor Green

# Step 3 - Apply manifests
Write-Host ""
Write-Host "[3/6] Applying manifests..." -ForegroundColor White

kubectl apply -f "$ScriptDir\secrets.yaml"
Write-Host "secrets applied" -ForegroundColor Green

kubectl apply -f "$ScriptDir\postgres.yaml"
Write-Host "postgres applied" -ForegroundColor Green

kubectl apply -f "$ScriptDir\redis.yaml"
Write-Host "redis applied" -ForegroundColor Green

kubectl apply -f "$ScriptDir\backend.yaml"
Write-Host "backend applied" -ForegroundColor Green

kubectl apply -f "$ScriptDir\frontend.yaml"
Write-Host "frontend applied" -ForegroundColor Green

kubectl apply -f "$ScriptDir\nginx.yaml"
Write-Host "nginx applied" -ForegroundColor Green

kubectl apply -f "$ScriptDir\hpa.yaml"
Write-Host "hpa applied" -ForegroundColor Green

kubectl apply -f "$ScriptDir\monitoring\"
Write-Host "monitoring (Prometheus + Grafana) applied" -ForegroundColor Green

# Step 4 - Wait for pods
Write-Host ""
Write-Host "[4/6] Waiting for pods (2-3 minutes)..." -ForegroundColor White

$apps = @("postgres", "redis", "backend", "frontend", "nginx")
foreach ($app in $apps) {
    Write-Host "Waiting for $app..." -ForegroundColor Gray
    kubectl wait --for=condition=ready pod -l "app=$app" --timeout=180s
    Write-Host "$app is ready" -ForegroundColor Green
}

# Step 5 - Migration
Write-Host ""
Write-Host "[5/6] Running DB migration..." -ForegroundColor White

$pod = kubectl get pod -l app=postgres -o jsonpath='{.items[0].metadata.name}'

$sqls = @(
    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS reason VARCHAR",
    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS observed_latency FLOAT",
    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS conflict BOOLEAN DEFAULT FALSE",
    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS capacity_agent VARCHAR",
    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS network_agent VARCHAR",
    "UPDATE tasks SET conflict = FALSE WHERE conflict IS NULL"
)

foreach ($sql in $sqls) {
    kubectl exec $pod -- psql -U csa_user -d csa_db -c $sql 2>$null
}
Write-Host "Migration done" -ForegroundColor Green

# Step 6 - Done
$ip = minikube ip

Write-Host ""
Write-Host "[6/6] Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Dashboard: http://${ip}:30080" -ForegroundColor Cyan
Write-Host "Grafana:   http://${ip}:30030  (anon viewer; admin/admin)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Useful commands:"
Write-Host "  kubectl get pods"
Write-Host "  kubectl get hpa"
Write-Host "  kubectl logs -l app=backend -f"
Write-Host "  kubectl port-forward svc/prometheus-service 9090:9090"
Write-Host "  minikube dashboard"
Write-Host "  minikube service nginx-service"
Write-Host ""
Write-Host "To tear down:"
Write-Host "  powershell -ExecutionPolicy Bypass -File infra\deployment\deploy.ps1 -Down"