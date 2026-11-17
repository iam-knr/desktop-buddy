# Shika for Windows 10 and 11. Safe to run again: it updates in place and never touches your notes or reminders.
#   Right-click this file > Run with PowerShell      (or double-click install-windows.bat)
#   Add -WithOllama to install Shika AI (local language model) without asking, or -NoAI to skip it.
param([switch]$WithOllama, [switch]$NoAI)
$ErrorActionPreference = "Stop"
$Dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$App = Join-Path $env:LOCALAPPDATA "ShikaApp"
$Venv = Join-Path $App "venv"

Write-Host "==> 1/5  Python"
function Find-Python {
    foreach ($c in @("py -3", "python", "python3")) {
        $parts = $c.Split(" ")
        try {
            $ok = & $parts[0] $parts[1..9] -c "import sys; print(int(sys.version_info >= (3, 10)))" 2>$null
            if ($ok -eq "1") { return $parts }
        } catch { }
    }
    return $null
}
$py = Find-Python
if (-not $py) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "    installing Python with winget"
        winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        $py = Find-Python
    }
}
if (-not $py) { Write-Host "Python 3.10 or newer is needed. Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH') and run this again."; exit 1 }

Write-Host "==> 2/5  Shika's private Python environment (one-time download, a few hundred MB)"
New-Item -ItemType Directory -Force -Path $App | Out-Null
if (-not (Test-Path (Join-Path $Venv "Scripts\python.exe"))) { & $py[0] $py[1..9] -m venv $Venv }
$vpy = Join-Path $Venv "Scripts\python.exe"
& $vpy -m pip install --quiet --upgrade pip
& $vpy -m pip install --quiet --upgrade -r (Join-Path $Dir "requirements-desktop.txt")
if ($LASTEXITCODE -ne 0) { Write-Host "PROBLEM: the packages did not install. Check your internet and run this again."; exit 1 }

Write-Host "==> 3/5  Offline speech model (one-time, about 500 MB)"
Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*ShikaApp*" } | Stop-Process -Force
Start-Sleep -Seconds 1
Copy-Item (Join-Path $Dir "shika\shika.py") (Join-Path $App "shika.py") -Force
Copy-Item (Join-Path $Dir "shika\bark.wav") (Join-Path $App "bark.wav") -Force
Copy-Item (Join-Path $Dir "shika\shika-icon.svg") (Join-Path $App "shika-icon.svg") -Force
$model = (Select-String -Path (Join-Path $Dir "shika\shika.py") -Pattern '^WHISPER_MODEL = "([^"]+)"').Matches[0].Groups[1].Value
& $vpy -c "from faster_whisper import WhisperModel; WhisperModel('$model', device='cpu', compute_type='int8')"
if ($LASTEXITCODE -ne 0) { Write-Host "    WARNING: could not download $model now. Shika will try again the first time you talk to him." }

Write-Host "==> 4/5  Start Menu entry and start at sign-in"
$pyw = Join-Path $Venv "Scripts\pythonw.exe"
$script = Join-Path $App "shika.py"
$sh = New-Object -ComObject WScript.Shell
function New-Link($path, $arguments) {
    $l = $sh.CreateShortcut($path)
    $l.TargetPath = $pyw
    $l.Arguments = "`"$script`" $arguments"
    $l.WorkingDirectory = $App
    $l.Description = "Shika, your desktop pup"
    $l.Save()
}
New-Link (Join-Path ([Environment]::GetFolderPath("Programs")) "Shika.lnk") "--dashboard"
New-Link (Join-Path ([Environment]::GetFolderPath("Programs")) "Shika Pup.lnk") ""
New-Link (Join-Path ([Environment]::GetFolderPath("Startup")) "Shika.lnk") "--autostart"

$WantAI = $false
if ($WithOllama) { $WantAI = $true }
elseif (-not $NoAI) {
    try { $ans = Read-Host "Install Shika AI, the local language model for text cleanup (about 1 GB)? [Y/n]"; if ($ans -eq "" -or $ans -match "^[Yy]") { $WantAI = $true } } catch { }
}
if ($WantAI) {
    Write-Host "==> Optional: local AI model"
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        if (Get-Command winget -ErrorAction SilentlyContinue) { winget install -e --id Ollama.Ollama --accept-package-agreements --accept-source-agreements }
        else { Write-Host "    Install Ollama from https://ollama.com" }
    }
    $om = (Select-String -Path (Join-Path $Dir "shika\shika.py") -Pattern '^OLLAMA_MODEL = "([^"]+)"').Matches[0].Groups[1].Value
    if (Get-Command ollama -ErrorAction SilentlyContinue) { ollama pull $om }
}

Write-Host "==> 5/5  Starting Shika"
Start-Process $pyw -ArgumentList "`"$script`" --autostart" -WorkingDirectory $App
Start-Sleep -Seconds 3
if (Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*ShikaApp*" }) { Write-Host "`nDone: Shika is running." }
else { Write-Host "`nPROBLEM: Shika did not start. Look at: $env:APPDATA\Shika\error.log" }
Write-Host "Hold Right Ctrl to dictate, Right Alt to give a command. Windows may ask to allow the microphone: say yes."
