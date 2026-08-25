# Pre-flight check for a demo or viva.
#
# Run this BEFORE you need the app to work. It checks the four things that
# have actually broken in practice and tells you which one is wrong, rather
# than leaving you to guess from a generic "Couldn't reach Mindlens".
#
#     powershell -ExecutionPolicy Bypass -File .\check-stack.ps1
#
# ASCII only on purpose: Windows PowerShell 5.1 reads this file as ANSI, and
# non-ASCII characters break string parsing outright.
#
# Exits 0 only if everything needed is up.

$ErrorActionPreference = 'SilentlyContinue'
$script:problems = @()

function Report($ok, $label, $detail, $fix) {
    if ($ok) {
        Write-Host "  OK   $label" -ForegroundColor Green
        if ($detail) { Write-Host "       $detail" -ForegroundColor DarkGray }
    } else {
        Write-Host "  DOWN $label" -ForegroundColor Red
        if ($detail) { Write-Host "       $detail" -ForegroundColor DarkGray }
        if ($fix) { Write-Host "       fix: $fix" -ForegroundColor Yellow }
        $script:problems += $label
    }
}

Write-Host ""
Write-Host "Mindlens pre-flight" -ForegroundColor Cyan
Write-Host "-------------------"

# 1. RAM. The real cause of MongoDB's crashes on this machine: five PyTorch
#    models plus a browser on 7GB leaves MongoDB nothing, and it dies with
#    "out of memory" rather than anything that names the true problem.
$os = Get-CimInstance Win32_OperatingSystem
$freeGB = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
$totalGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
Report ($freeGB -gt 1.0) "Free RAM" "$freeGB GB free of $totalGB GB" "close Chrome tabs or other apps - under 1GB free is where MongoDB starts dying"

# 2. MongoDB.
$mongo = Get-Service MongoDB -ErrorAction SilentlyContinue
if ($mongo) { $mongoDetail = "service status: " + $mongo.Status } else { $mongoDetail = "service not found" }
Report ($mongo -and $mongo.Status -eq 'Running') "MongoDB" $mongoDetail "Start-Service MongoDB   (in an ADMIN PowerShell)"

# 3. Backend. /ready, not /health - /health only proves the process is up,
#    /ready is the one that actually checked Mongo and all five models.
$ready = $null
try { $ready = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/ready' -TimeoutSec 20 } catch {}
if ($ready) {
    $backendDetail = "ready=" + $ready.ready + ", database=" + $ready.database + ", rag chunks=" + $ready.rag.chunks
} else {
    $backendDetail = "no response on :8000"
}
Report ($null -ne $ready -and $ready.ready) "Backend" $backendDetail "cd backend; ..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

# Per-model detail: all five can be individually broken while the process
# looks perfectly healthy - that exact failure went unnoticed for days.
if ($ready -and $ready.models) {
    foreach ($prop in $ready.models.PSObject.Properties) {
        $name = $prop.Name
        $m = $prop.Value
        $bad = ($m.status -ne 'ready') -or ($m.error_count -gt 0)
        if ($bad) {
            $detail = "status=" + $m.status + " errors=" + $m.error_count
            Report $false ("  model: " + $name) $detail "check the backend log - usually a transformers/tokenizers version mismatch"
        }
    }
}

# 4. ngrok. Only matters for the deployed site, but that is what gets demoed.
$ngrokUp = $false
$tunnelUrl = $null
try {
    $t = Invoke-RestMethod -Uri 'http://127.0.0.1:4040/api/tunnels' -TimeoutSec 5
    $tunnelUrl = ($t.tunnels | Select-Object -First 1).public_url
    $ngrokUp = [bool]$tunnelUrl
} catch {}
if ($tunnelUrl) { $ngrokDetail = $tunnelUrl } else { $ngrokDetail = "no local ngrok agent on :4040" }
Report $ngrokUp "ngrok tunnel" $ngrokDetail "D:\AI Projects\mindlens\tools\ngrok.exe http 8000   (only needed for the Vercel site)"

# Defender has repeatedly quarantined the ngrok binary as a false positive,
# which presents as "not recognized as the name of a cmdlet" rather than
# anything mentioning antivirus. Check the file still exists at all.
$ngrokPath = "D:\AI Projects\mindlens\tools\ngrok.exe"
if (-not $ngrokUp) {
    Report (Test-Path $ngrokPath) "ngrok binary present" $ngrokPath "Defender likely quarantined it - see README 'The ngrok tunnel'"
}

# 5. The whole path the deployed site actually uses. Everything above can
#    pass while this still fails, so it is checked end to end rather than
#    inferred from the parts.
if ($ngrokUp) {
    $viaTunnel = $false
    try {
        $r = Invoke-RestMethod -Uri "$tunnelUrl/ready" -TimeoutSec 25 -Headers @{ 'ngrok-skip-browser-warning' = 'true' }
        $viaTunnel = [bool]$r.ready
    } catch {}
    Report $viaTunnel "Deployed site to your backend" "$tunnelUrl/ready" "tunnel is up but not reaching the backend - restart ngrok"
}

Write-Host ""
if ($script:problems.Count -eq 0) {
    Write-Host "All good. mindlens-theta.vercel.app will work." -ForegroundColor Green
    exit 0
} else {
    $joined = $script:problems -join ', '
    Write-Host "Not ready: $joined" -ForegroundColor Red
    exit 1
}
