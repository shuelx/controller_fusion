# setup.ps1
# Checks whether a real Python 3.9+ is available (not the Microsoft Store
# placeholder that "exists" on PATH but doesn't actually run), installs one
# via winget if not, falls back to guiding a manual install if winget isn't
# available or fails, then launches controller_fusion.py --gui.
#
# controller_fusion.py handles its OWN dependencies (pygame, vgamepad) once
# Python itself works - this script's only job is getting Python itself in
# place, since that's the one thing the app can't bootstrap for itself.

function Test-PythonWorks {
    try {
        $out = & python --version 2>&1
        if ($LASTEXITCODE -ne 0) { return $false }
        if ($out -match "Python (\d+)\.(\d+)") {
            $maj = [int]$matches[1]
            $min = [int]$matches[2]
            return ($maj -eq 3 -and $min -ge 9)
        }
        return $false
    } catch {
        return $false
    }
}

# Refresh PATH from the registry unconditionally, before the first check -
# if Python was installed in a DIFFERENT session (this script run earlier,
# or installed by hand), this process's inherited PATH can still be stale
# and wrongly report "not found", triggering a pointless reinstall attempt.
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") +
            ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

Write-Host "Checking for Python 3.9+..."

if (Test-PythonWorks) {
    Write-Host "Found a working Python. Continuing."
} else {
    Write-Host "No working Python found (or it's just the Microsoft Store placeholder)."
    $installedOk = $false

    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "Installing Python 3.12 via winget - this can take a minute..."
        winget install --id Python.Python.3.12 --source winget `
            --accept-source-agreements --accept-package-agreements -e
        if ($LASTEXITCODE -eq 0) {
            # this console session hasn't seen the PATH change winget just made -
            # re-read it from the registry instead of opening a new window
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") +
                        ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
            $installedOk = Test-PythonWorks
        }
    } else {
        Write-Host "winget isn't available on this machine."
    }

    if (-not $installedOk) {
        Write-Host ""
        Write-Host "Couldn't install Python automatically. Opening the download page -"
        Write-Host "run the installer, make sure 'Add python.exe to PATH' is checked,"
        Write-Host "then run this setup script again."
        Start-Process "https://www.python.org/downloads/"
        Read-Host "Press Enter to close"
        exit 1
    }
    Write-Host "Python installed successfully."
}

Write-Host "Starting controller_fusion..."
Set-Location -Path $PSScriptRoot
python controller_fusion.py --gui
exit $LASTEXITCODE
