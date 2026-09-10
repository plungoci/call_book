<#
.SYNOPSIS
    Instalează și pornește Radio Logbook pe un calculator Windows nou.

.DESCRIPTION
    Verifică Git și Python 3.11+ (le instalează prin winget dacă lipsesc), clonează
    proiectul, creează mediul virtual .venv, instalează dependențele, adaugă o
    scurtătură pe Desktop și pornește aplicația. Rularea din nou a scriptului
    actualizează o instalare existentă în loc să o dubleze.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/plungoci/call_book/main/scripts/install.ps1 | iex"
#>

[CmdletBinding()]
param(
    [string]$InstallPath = (Join-Path $env:USERPROFILE 'call_book'),
    [string]$Branch = 'main',
    [switch]$NoShortcut,
    [switch]$NoStart
)

$ErrorActionPreference = 'Stop'
$RepositoryUrl = 'https://github.com/plungoci/call_book.git'
$MinimumPython = [Version]'3.11'

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Invoke-Native {
    # PowerShell nu oprește scriptul când un program extern eșuează, așa că
    # verificăm explicit codul de ieșire după fiecare comandă git/pip.
    param([string]$Executable, [string[]]$Arguments, [string]$FailureMessage)
    & $Executable $Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FailureMessage (cod de ieșire $LASTEXITCODE)"
    }
}

function Update-SessionPath {
    # Un pachet instalat de winget apare în PATH abia la o sesiune nouă; îl
    # aducem în sesiunea curentă ca să putem continua fără repornire.
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = (@($machine, $user) | Where-Object { $_ }) -join ';'
}

function Install-WithWinget {
    param([string]$PackageId, [string]$FriendlyName)
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "$FriendlyName lipsește, iar winget nu este disponibil. Instalează manual $FriendlyName și rulează scriptul din nou."
    }
    Write-Step "Instalez $FriendlyName (winget: $PackageId)..."
    winget install --id $PackageId --exact --source winget --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        # Codurile winget diferă între versiuni; verificarea de după instalare
        # spune oricum, mai clar, dacă programul a devenit disponibil.
        Write-Warning "winget a raportat codul $LASTEXITCODE la instalarea $FriendlyName."
    }
    Update-SessionPath
}

function Get-PythonVersion {
    param([string]$Executable, [string[]]$Arguments = @())
    try {
        $output = & $Executable @($Arguments + @('-c', 'import sys; print("%d.%d" % sys.version_info[:2])')) 2>$null
    } catch {
        return $null
    }
    if ($LASTEXITCODE -ne 0 -or -not $output) { return $null }
    try { return [Version]($output | Select-Object -First 1).Trim() } catch { return $null }
}

function Find-Python {
    # `py -3` primul: pe Windows selectează cea mai nouă versiune instalată și
    # ocolește scurtătura din Microsoft Store, care nu este un Python real.
    $candidates = @(
        @{ Executable = 'py'; Arguments = @('-3') },
        @{ Executable = 'python'; Arguments = @() },
        @{ Executable = 'python3'; Arguments = @() }
    )
    foreach ($candidate in $candidates) {
        if (-not (Get-Command $candidate.Executable -ErrorAction SilentlyContinue)) { continue }
        $version = Get-PythonVersion -Executable $candidate.Executable -Arguments $candidate.Arguments
        if ($version -and $version -ge $MinimumPython) { return $candidate }
    }
    return $null
}

function New-DesktopShortcut {
    param([string]$Target, [string]$WorkingDirectory)
    $path = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Radio Logbook.lnk'
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($path)
    $shortcut.TargetPath = $Target
    $shortcut.WorkingDirectory = $WorkingDirectory
    $shortcut.Description = 'Radio Logbook'
    # Fereastra de consolă a lansatorului rămâne minimizată cât timp aplicația rulează.
    $shortcut.WindowStyle = 7
    $shortcut.Save()
    return $path
}

Write-Step 'Verific Git...'
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Install-WithWinget -PackageId 'Git.Git' -FriendlyName 'Git'
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'Git tot nu este disponibil. Deschide o fereastră PowerShell nouă și rulează scriptul din nou.'
}

Write-Step "Verific Python $MinimumPython sau mai nou..."
$python = Find-Python
if (-not $python) {
    Install-WithWinget -PackageId 'Python.Python.3.12' -FriendlyName 'Python 3.12'
    $python = Find-Python
}
if (-not $python) {
    throw 'Python 3.11+ tot nu este disponibil. Deschide o fereastră PowerShell nouă și rulează scriptul din nou.'
}

if (Test-Path (Join-Path $InstallPath '.git')) {
    Write-Step "Actualizez instalarea existentă din $InstallPath..."
    Invoke-Native git @('-C', $InstallPath, 'fetch', 'origin') 'Nu am putut verifica actualizările.'
    Invoke-Native git @('-C', $InstallPath, 'pull', '--ff-only') 'Nu am putut actualiza proiectul.'
} else {
    if ((Test-Path $InstallPath) -and (Get-ChildItem -LiteralPath $InstallPath -Force | Select-Object -First 1)) {
        throw "Directorul $InstallPath există deja și nu este o instalare Radio Logbook. Alege alt director cu -InstallPath."
    }
    Write-Step "Clonez proiectul în $InstallPath..."
    Invoke-Native git @('clone', '--branch', $Branch, $RepositoryUrl, $InstallPath) 'Nu am putut clona proiectul.'
}

$venvPython = Join-Path $InstallPath '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    Write-Step 'Creez mediul virtual .venv...'
    Invoke-Native $python.Executable ($python.Arguments + @('-m', 'venv', (Join-Path $InstallPath '.venv'))) 'Nu am putut crea mediul virtual.'
}

Write-Step 'Instalez dependențele (PySide6, openpyxl, curl_cffi)...'
Invoke-Native $venvPython @('-m', 'pip', 'install', '--upgrade', 'pip') 'Nu am putut actualiza pip.'
Invoke-Native $venvPython @('-m', 'pip', 'install', '-r', (Join-Path $InstallPath 'requirements.txt')) 'Nu am putut instala dependențele.'

$launcher = Join-Path $InstallPath 'Launcher.bat'
if (-not $NoShortcut) {
    Write-Step 'Adaug scurtătura pe Desktop...'
    try {
        $shortcut = New-DesktopShortcut -Target $launcher -WorkingDirectory $InstallPath
        Write-Host "Scurtătură creată: $shortcut"
    } catch {
        Write-Warning "Nu am putut crea scurtătura: $($_.Exception.Message)"
    }
}

Write-Host ''
Write-Host 'Radio Logbook este instalat.' -ForegroundColor Green
Write-Host "Director: $InstallPath"
Write-Host "Pornire: dublu-clic pe scurtătura de pe Desktop sau pe $launcher"

if (-not $NoStart) {
    Write-Step 'Pornesc aplicația...'
    & $venvPython (Join-Path $InstallPath 'launcher.py')
}
