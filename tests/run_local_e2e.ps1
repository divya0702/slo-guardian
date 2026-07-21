$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo '.venv\Scripts\python.exe'
$env:PYTHONPATH = "$repo;$repo\control-plane"
$env:INTERNAL_REPLAY_TOKEN = 'local-e2e-token'
$env:OTEL_SDK_DISABLED = 'true'
$env:OTEL_EXPORTER_OTLP_ENDPOINT = 'http://127.0.0.1:4317'
$env:LIVE_LATENCY_SCALE = '0.02'
$env:INVENTORY_URL = 'http://127.0.0.1:18002'
$env:PRICING_URL = 'http://127.0.0.1:18003'
$env:RECOMMENDATIONS_URL = 'http://127.0.0.1:18004'
$env:CHECKOUT_URL = 'http://127.0.0.1:18001'
$env:GATEWAY_URL = 'http://127.0.0.1:18000'
$env:SCENARIOS_DIR = Join-Path $repo 'scenarios'
$env:DATABASE_URL = 'sqlite:///./data/local-e2e.db'
$processes = @()

function Start-SloService($module, $port, $appDir = $null) {
    $arguments = @('-m', 'uvicorn', $module, '--host', '127.0.0.1', '--port', $port, '--log-level', 'error')
    if ($appDir) { $arguments += @('--app-dir', $appDir) }
    return Start-Process -FilePath $python -ArgumentList $arguments -WindowStyle Hidden -PassThru
}

try {
    $processes += Start-SloService 'services.inventory.app:app' '18002'
    $processes += Start-SloService 'services.pricing.app:app' '18003'
    $processes += Start-SloService 'services.recommendations.app:app' '18004'
    $processes += Start-SloService 'services.checkout.app:app' '18001'
    $processes += Start-SloService 'services.gateway.app:app' '18000'
    $processes += Start-SloService 'api.main:app' '18080' (Join-Path $repo 'control-plane')
    $ready = $false
    for ($index = 0; $index -lt 30; $index++) {
        try {
            Invoke-RestMethod 'http://127.0.0.1:18080/readyz' | Out-Null
            Invoke-RestMethod 'http://127.0.0.1:18000/healthz' | Out-Null
            $ready = $true
            break
        } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $ready) { throw 'Local services did not become ready.' }

    $analysis = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:18080/api/v1/analyses' -ContentType 'application/json' -Body '{"scenario_id":"slow_dependency","source":"fixture"}'
    $policy = $analysis.candidates | Where-Object state -eq 'validated' | Select-Object -First 1
    $simulationBody = @{
        policy_id = $policy.policy_id
        scenario_id = 'slow_dependency'
        mode = 'live'
        request_count = 20
        concurrency = 4
    } | ConvertTo-Json
    $simulation = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:18080/api/v1/simulations' -ContentType 'application/json' -Body $simulationBody
    Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18080/api/v1/policies/$($policy.policy_id)/approve" | Out-Null
    $checkout = Invoke-RestMethod 'http://127.0.0.1:18000/checkout?scenario=slow_dependency'
    if (-not $simulation.safe -or $simulation.observed.critical_rejected -ne 0) {
        throw 'Critical checkout safety invariant failed.'
    }
    [pscustomobject]@{
        incident = $analysis.incident_id
        policy = $policy.policy_id
        simulation = $simulation.simulation_id
        safe = $simulation.safe
        critical_rejected = $simulation.observed.critical_rejected
        active_policy = $checkout.active_policy_id
        fallback = $checkout.recommendation_fallback
    } | ConvertTo-Json
} finally {
    $processes | Where-Object { $_ -and -not $_.HasExited } | Stop-Process -Force
}
