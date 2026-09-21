<#
.SYNOPSIS
    3계층 검사를 한 번에 실행한다 (TEST_PLAN.md 참고).
      L1 데이터  — validate.py     (schedule/events/seating/show-info)
      L2 정적    — check_html.py   (잔재·id 참조·외부 링크)
      L3 로직    — selftest.html   (headless Chrome 으로 실제 실행)
.EXAMPLE
    .\run_tests.ps1
#>
[CmdletBinding()]
param(
    [int]$Port = 8765
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$parent = Split-Path $root -Parent
$name = Split-Path $root -Leaf
# 파이썬 쪽만 UTF-8 로 맞추면 PowerShell 이 그 바이트를 콘솔 코드페이지(cp949)로
# 읽어 한글이 깨진다. 양쪽을 같이 맞춰야 한다.
$env:PYTHONIOENCODING = 'utf-8'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' +
            [Environment]::GetEnvironmentVariable('Path','User')

$fail = 0
function Section($t) { Write-Host "`n=== $t ===" -ForegroundColor Cyan }

Section 'L1 데이터 검증'
& python (Join-Path $root 'scripts\validate.py')
if ($LASTEXITCODE -ne 0) { $fail++ }

Section 'L2 정적 점검'
# check_html.py 는 스킬에서 그대로 실행하며 프로젝트 경로를 인자로 받는다.
# 프로젝트에 사본이 있으면 그쪽을 우선한다.
$checker = Join-Path $root 'scripts\check_html.py'
if (-not (Test-Path $checker)) {
    $checker = Join-Path $env:USERPROFILE '.claude\skills\musical-diary\scripts\check_html.py'
}
if (Test-Path $checker) {
    & python $checker $root
    if ($LASTEXITCODE -ne 0) { $fail++ }
} else {
    Write-Host "[!] check_html.py 를 찾을 수 없습니다" -ForegroundColor Yellow
    $fail++
}

Section 'L3 로직 셀프테스트'

# 로컬 서버 확보 — 배포 경로(/<repo>/)와 같은 형태로 서빙해야 sw.js BASE 와 맞는다
$serverStarted = $false
try {
    Invoke-WebRequest "http://127.0.0.1:$Port/$name/index.html" -UseBasicParsing -TimeoutSec 3 | Out-Null
    Write-Host "[*] 기존 서버 사용 (:$Port)"
} catch {
    Write-Host "[*] 로컬 서버 시작 (:$Port)"
    $server = Start-Process -FilePath 'python' -ArgumentList @('-m','http.server',$Port,'--bind','127.0.0.1') `
                            -WorkingDirectory $parent -WindowStyle Hidden -PassThru
    $serverStarted = $true
    Start-Sleep -Seconds 2
}

$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
if (-not (Test-Path $chrome)) { $chrome = "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" }

# 프로필 디렉터리를 재사용하면 이전 실행이 남긴 락 때문에 Chrome 이 무한 대기한다.
# 실행마다 새로 만들고 끝나면 지운다.
$tmp = Join-Path $env:TEMP ("ikkisup-selftest-" + [guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$dump = Join-Path $tmp 'dump.html'

try {
    if (-not (Test-Path $chrome)) { throw "Chrome 을 찾을 수 없습니다: $chrome" }
    $chromeArgs = @(
        '--headless=new','--disable-gpu','--no-sandbox','--dump-dom',
        '--no-first-run','--no-default-browser-check',
        "--user-data-dir=$tmp\profile",'--virtual-time-budget=15000',
        "http://127.0.0.1:$Port/$name/selftest.html"
    )
    $errFile = Join-Path $tmp 'err.txt'
    Start-Process -FilePath $chrome -ArgumentList $chromeArgs -RedirectStandardOutput $dump -RedirectStandardError $errFile -NoNewWindow -Wait | Out-Null

    $parser = Join-Path $root 'scripts\parse_selftest.py'
    if (-not (Test-Path $parser)) {
        $parser = Join-Path $env:USERPROFILE '.claude\skills\musical-diary\scripts\parse_selftest.py'
    }
    & python $parser $dump
    if ($LASTEXITCODE -ne 0) { $fail++ }
} catch {
    Write-Host "[!] $_" -ForegroundColor Red
    $fail++
} finally {
    if ($serverStarted -and $server -and -not $server.HasExited) {
        Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
        Write-Host "[*] 로컬 서버 종료"
    }
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}

Write-Host ''
if ($fail) {
    Write-Host "실패한 계층 $fail 개" -ForegroundColor Red
    exit 1
}
Write-Host "3계층 전부 통과" -ForegroundColor Green
