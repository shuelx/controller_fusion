# play.ps1
# Refreshes PATH from the registry before launching - if Python (or anything
# else) was installed in a DIFFERENT session (e.g. via setup.bat earlier),
# this process's own inherited PATH can still be the stale pre-install one.
# Windows only re-reads it for new processes after logoff/reboot unless
# something does it by hand, which is all this does.
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") +
            ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

Set-Location -Path $PSScriptRoot
python controller_fusion.py --gui
exit $LASTEXITCODE
