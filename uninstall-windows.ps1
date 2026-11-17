# Removes Shika from Windows. Your notes, dictations, reminders and settings are KEPT unless you add -PurgeData.
param([switch]$PurgeData)
Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*ShikaApp*" } | Stop-Process -Force
Start-Sleep -Seconds 1
Remove-Item -Recurse -Force (Join-Path $env:LOCALAPPDATA "ShikaApp") -ErrorAction SilentlyContinue
foreach ($f in @((Join-Path ([Environment]::GetFolderPath("Programs")) "Shika.lnk"),
                 (Join-Path ([Environment]::GetFolderPath("Programs")) "Shika Pup.lnk"),
                 (Join-Path ([Environment]::GetFolderPath("Startup")) "Shika.lnk"))) { Remove-Item -Force $f -ErrorAction SilentlyContinue }
Write-Host "Removed the program, Start Menu entries and the start-at-sign-in entry."
if ($PurgeData) {
    $a = Read-Host "Type DELETE to also delete your notes, dictations, reminders and settings"
    if ($a -ceq "DELETE") {
        Remove-Item -Recurse -Force (Join-Path $env:APPDATA "Shika") -ErrorAction SilentlyContinue
        Remove-Item -Recurse -Force (Join-Path $env:LOCALAPPDATA "Summit") -ErrorAction SilentlyContinue
        Write-Host "Data deleted."
    } else { Write-Host "Data kept." }
} else { Write-Host "Kept your data in $env:APPDATA\Shika and $env:LOCALAPPDATA\Summit (add -PurgeData to delete it)." }
