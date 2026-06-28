<#
  Reproducible real-trace fetcher for CSA-ACI (Windows / PowerShell).
    Wikipedia projectviews -> downloaded automatically (small, public, no auth).
    Google Borg 2019 / Azure -> printed commands (need gsutil / git + accept terms).
  Usage:  scripts\fetch_traces.ps1 [-Date 20260609]
#>
param([string]$Date = "20260609")

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Raw  = Join-Path $Root "data\raw"
$Year = $Date.Substring(0,4); $Month = $Date.Substring(4,2)

# --- 1. Wikipedia pageviews (REAL, automated) ---------------------------------
$Wiki = Join-Path $Raw "wikipedia"
New-Item -ItemType Directory -Force -Path $Wiki | Out-Null
Write-Host "==> Wikipedia projectviews for $Date -> $Wiki"
$ok = 0
foreach ($h in 0..23) {
  $H = "{0:D2}" -f $h
  $f = "projectviews-$Date-${H}0000"
  $dest = Join-Path $Wiki $f
  if ((Test-Path $dest) -and (Get-Item $dest).Length -gt 0) { Write-Host "    have    $f"; $ok++; continue }
  $url = "https://dumps.wikimedia.org/other/pageviews/$Year/$Year-$Month/$f"
  try { Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing; Write-Host "    fetched $f"; $ok++ }
  catch { Write-Host "    MISS    $f  ($url)"; if (Test-Path $dest) { Remove-Item $dest -Force } }
}
Write-Host "    -> $ok hourly files present"

# --- 2/3. Google + Azure (REAL, manual) ---------------------------------------
@"

==> Google Cluster 2019 (manual): requires the gcloud/gsutil CLI.
    New-Item -ItemType Directory -Force -Path "$Raw\google\task_usage"
    gsutil -m cp gs://clusterdata_2019_a/task_usage/part-00000-of-00500.csv.gz "$Raw\google\task_usage\"
    # docs: https://github.com/google/cluster-data

==> Azure VM traces (manual, recommended 3rd dataset):
    git clone --depth 1 https://github.com/Azure/AzurePublicDataset "$Raw\azure\src"
    # place a per-VM CPU CSV into "$Raw\azure\", then add data\loaders\azure.py
    # (mirror google_cluster.py) and an "azure" entry in trace_loader.DATASETS.

Verify provenance after fetching:
    docker exec csa_backend python -c "from app.services.trace_loader import list_datasets; print(list_datasets())"
"@ | Write-Host
