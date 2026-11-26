# Windows: start Neo4j (Docker) and regenerate every file in partB/output except q3_profile.png.
# Usage (from this folder):  .\run_all.ps1            or  .\run_all.ps1 -DataDir D:\ml-100k
param([string]$DataDir = "..\data\ml-100k")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$py = ".\.venv\Scripts\python.exe"
$neo = @("--uri", "bolt://localhost:7687", "--user", "neo4j", "--password", "bdaGraph2026")

function Run([string[]]$cmdArgs) {
    Write-Host "`n>>> python $cmdArgs" -ForegroundColor Cyan
    & $py @cmdArgs
    if ($LASTEXITCODE -ne 0) { throw "failed: $cmdArgs" }
}

# --- Neo4j container (exact commands from the assignment, created only if missing) ---
# Terminals opened before Docker was installed have a stale PATH: reload it from the registry.
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    $env:PATH = "$env:PATH;" + [Environment]::GetEnvironmentVariable("PATH", "User") + ";" +
                [Environment]::GetEnvironmentVariable("PATH", "Machine")
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "docker not found. Start Docker Desktop, then open a NEW terminal (or restart VS Code)."
}
$ErrorActionPreference = "Continue"
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker engine not running. Open Docker Desktop and wait for 'Engine running'." }
$exists = docker ps -a --filter "name=^bda-neo4j$" --format "{{.Names}}"
if (-not $exists) {
    docker volume create bda-neo4j-data | Out-Null
    docker run -d --name bda-neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/bdaGraph2026 -v bda-neo4j-data:/data neo4j:2026.10.1
} else {
    docker start bda-neo4j | Out-Null
}
Write-Host "waiting for Neo4j bolt port 7687..."
for ($i = 0; $i -lt 90; $i++) {
    & $py -c "from neo4j import GraphDatabase as G; G.driver('bolt://localhost:7687', auth=('neo4j','bdaGraph2026')).verify_connectivity()" 2>$null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 2
}
if ($LASTEXITCODE -ne 0) { throw "Neo4j did not become ready; check: docker logs bda-neo4j" }
$ErrorActionPreference = "Stop"

Run (@("partB/load_neo4j.py", "--data-dir", $DataDir) + $neo + @("--reset"))
Run (@("partB/run_queries.py") + $neo + @("--target-user", "1", "--like-threshold", "4", "--topk", "10", "--output-dir", "partB/output"))
Run @("partB/recommend.py", "--data-dir", $DataDir, "--users", "1", "50", "100", "--like-threshold", "4", "--neighbors", "20", "--topk", "10", "--output-dir", "partB/output")
Run @("partB/test_partB.py", "--data-dir", $DataDir)
Write-Host "`nDONE - outputs in partB/output (q3_profile.png must be taken manually in Neo4j Browser)" -ForegroundColor Green
