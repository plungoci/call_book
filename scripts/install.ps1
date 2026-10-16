<#
.SYNOPSIS
    Instalează și pornește Radio Logbook pe un calculator Windows.

.DESCRIPTION
    Verifică Git și Python 3.11+ (le instalează prin winget dacă lipsesc), clonează
    proiectul, creează mediul virtual .venv, instalează dependențele, verifică
    instalarea, adaugă o scurtătură pe Desktop și pornește aplicația. Rularea din
    nou repară sau actualizează o instalare existentă, în loc să o dubleze.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = 'Tls12'; irm https://raw.githubusercontent.com/plungoci/call_book/main/scripts/install.ps1 | iex"

.EXAMPLE
    & ([scriptblock]::Create((irm https://raw.githubusercontent.com/plungoci/call_book/main/scripts/install.ps1))) -InstallPath D:\radio\call_book -NoStart
#>

[CmdletBinding()]
param(
    [string]$InstallPath = (Join-Path $env:USERPROFILE 'call_book'),
    [string]$Branch = 'main',
    # Alt repository Git; folosit de CI ca să instaleze propria copie.
    [string]$Repository = 'https://github.com/plungoci/call_book.git',
    [switch]$NoShortcut,
    [switch]$NoStart
)

$ErrorActionPreference = 'Stop'
$MinimumPython = [Version]'3.11'
# Versiunile pentru care PySide6 publică roți Windows, de la cea preferată în jos.
$PreferredPythons = @('3.13', '3.12', '3.11')

# Windows PowerShell 5.1 negociază implicit TLS 1.0, pe care GitHub îl refuză.
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
} catch { }
# Diacriticele din mesaje se afișează corect doar cu ieșirea consolei în UTF-8.
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

function Write-Step {
    param([string]$Message)
    Write-Host ''
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Invoke-Native {
    # PowerShell nu oprește scriptul când un program extern eșuează, așa că
    # verificăm explicit codul de ieșire. Pe durata comenzii, preferința de eroare
    # este relaxată: în unele gazde (ISE, VS Code), Windows PowerShell transformă
    # orice rând scris de git/pip pe stderr — inclusiv progresul — într-o eroare
    # care, cu 'Stop', ar întrerupe instalarea.
    param([string]$Executable, [string[]]$Arguments, [string]$FailureMessage)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Executable @Arguments
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    if ($exitCode -ne 0) {
        throw "$FailureMessage (cod de ieșire $exitCode)"
    }
}

function Update-SessionPath {
    # Un program instalat de winget apare în PATH abia într-o sesiune nouă; îl
    # aducem în sesiunea curentă ca să putem continua fără repornire.
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = (@($machine, $user, $env:Path) | Where-Object { $_ }) -join ';'
}

function Install-WithWinget {
    param([string]$PackageId, [string]$FriendlyName)
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "$FriendlyName lipsește, iar winget nu este disponibil. Instalează manual $FriendlyName și rulează scriptul din nou."
    }
    Write-Step "Instalez $FriendlyName (winget: $PackageId)..."
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        winget install --id $PackageId --exact --source winget --accept-package-agreements --accept-source-agreements
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    if ($exitCode -ne 0) {
        # Codurile winget diferă între versiuni (inclusiv „deja instalat”);
        # verificarea de după instalare spune oricum dacă programul există.
        Write-Warning "winget a raportat codul $exitCode la instalarea $FriendlyName."
    }
    Update-SessionPath
}

function Get-PythonVersion {
    param([string]$Executable, [string[]]$Arguments = @())
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        # Fără ghilimele duble în cod: Windows PowerShell 5.1 nu le escapează când
        # le transmite unui program extern, iar Python ar primi cod invalid.
        $output = & $Executable @($Arguments + @('-c', "import sys; print('%d.%d' % sys.version_info[:2])")) 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $output) { return $null }
        return [Version](@($output)[0]).Trim()
    } catch {
        return $null
    } finally {
        $ErrorActionPreference = $previous
    }
}

function Find-Python {
    # Ordinea contează:
    # 1. `py -3.X` alege exact o versiune suportată de PySide6, chiar dacă cea
    #    mai nouă instalată (de exemplu o versiune beta) nu are încă roți.
    # 2. Directoarele standard ale instalatorului python.org, pentru cazul în
    #    care winget l-a instalat fără să-l adauge în PATH.
    # 3. `python`/`python3` din PATH, care pot fi scurtătura din Microsoft Store
    #    — aceea nu este un Python real și nu raportează o versiune.
    $candidates = @()
    foreach ($version in $PreferredPythons) {
        $candidates += , @('py', "-$version")
    }
    foreach ($version in $PreferredPythons) {
        $folder = 'Python' + $version.Replace('.', '')
        foreach ($root in @((Join-Path $env:LOCALAPPDATA 'Programs\Python'), $env:ProgramFiles)) {
            if ($root) { $candidates += , @((Join-Path (Join-Path $root $folder) 'python.exe')) }
        }
    }
    $candidates += , @('py', '-3')
    $candidates += , @('python')
    $candidates += , @('python3')

    foreach ($candidate in $candidates) {
        $executable = $candidate[0]
        $arguments = @($candidate | Select-Object -Skip 1)
        if (-not (Get-Command $executable -ErrorAction SilentlyContinue)) { continue }
        $version = Get-PythonVersion -Executable $executable -Arguments $arguments
        if ($version -and $version -ge $MinimumPython) {
            return [pscustomobject]@{ Executable = $executable; Arguments = $arguments; Version = $version }
        }
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

function Test-VenvPython {
    # Un mediu virtual creat pe jumătate are python.exe, dar nu și pip.
    param([string]$Executable)
    if (-not (Test-Path -LiteralPath $Executable)) { return $false }
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Executable -m pip --version *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $previous
    }
}

Write-Step 'Verific Git...'
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Install-WithWinget -PackageId 'Git.Git' -FriendlyName 'Git'
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    $gitPath = Join-Path $env:ProgramFiles 'Git\cmd'
    if (Test-Path (Join-Path $gitPath 'git.exe')) { $env:Path = "$gitPath;$env:Path" }
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
    throw 'Python 3.11+ tot nu este disponibil. Instalează-l de pe https://www.python.org/downloads/ (bifează „Add python.exe to PATH”), apoi rulează scriptul din nou.'
}
Write-Host "Folosesc Python $($python.Version): $($python.Executable) $($python.Arguments -join ' ')"

if (Test-Path (Join-Path $InstallPath '.git')) {
    Write-Step "Actualizez instalarea existentă din $InstallPath..."
    # O actualizare eșuată nu oprește instalarea: versiunea locală rămâne
    # funcțională, iar lansatorul spune la pornire de ce nu s-a actualizat.
    try {
        Invoke-Native git @('-C', $InstallPath, 'pull', '--ff-only') 'Nu am putut actualiza proiectul'
    } catch {
        Write-Warning "$($_.Exception.Message). Continui cu versiunea locală."
    }
} else {
    if ((Test-Path $InstallPath) -and (Get-ChildItem -LiteralPath $InstallPath -Force | Select-Object -First 1)) {
        throw "Directorul $InstallPath există deja și nu este o instalare Radio Logbook. Alege alt director cu -InstallPath."
    }
    Write-Step "Clonez proiectul în $InstallPath..."
    Invoke-Native git @('clone', '--branch', $Branch, $Repository, $InstallPath) 'Nu am putut clona proiectul'
}

$venvPath = Join-Path $InstallPath '.venv'
$venvPython = Join-Path $venvPath 'Scripts\python.exe'
if (-not (Test-VenvPython $venvPython)) {
    Write-Step 'Creez mediul virtual .venv...'
    if (Test-Path -LiteralPath $venvPath) { Remove-Item -LiteralPath $venvPath -Recurse -Force }
    Invoke-Native $python.Executable ($python.Arguments + @('-m', 'venv', $venvPath)) 'Nu am putut crea mediul virtual'
    if (-not (Test-VenvPython $venvPython)) { throw 'Mediul virtual a fost creat fără pip.' }
}

Write-Step 'Instalez dependențele Python (PySide6, openpyxl, curl_cffi)...'
Invoke-Native $venvPython @('-m', 'pip', 'install', '--upgrade', 'pip') 'Nu am putut actualiza pip'
Invoke-Native $venvPython @('-m', 'pip', 'install', '--upgrade', '-r', (Join-Path $InstallPath 'requirements.txt')) 'Nu am putut instala dependențele'
Invoke-Native $venvPython @('-c', 'import PySide6.QtWidgets, openpyxl, curl_cffi') 'Dependențele s-au instalat, dar nu pot fi importate. Dacă eroarea de mai sus pomenește o bibliotecă DLL, instalează Microsoft Visual C++ Redistributable (winget install Microsoft.VCRedist.2015+.x64)'

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
    & $launcher
}
