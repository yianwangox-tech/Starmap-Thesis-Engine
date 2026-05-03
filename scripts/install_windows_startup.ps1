Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "windows_common.ps1")

$rootDir = Get-StarMapRootDir -ScriptRoot $PSScriptRoot
$null = Ensure-StarMapLogDir -RootDir $rootDir

$backendScript = Join-Path $rootDir "scripts\start_backend.ps1"
$frontendScript = Join-Path $rootDir "scripts\start_frontend.ps1"
$taskUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$backendTaskName = "StarMap Backend"
$frontendTaskName = "StarMap Frontend"

if (-not (Test-Path $backendScript)) {
    throw "Missing backend startup script at $backendScript"
}

if (-not (Test-Path $frontendScript)) {
    throw "Missing frontend startup script at $frontendScript"
}

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId $taskUser -LogonType Interactive -RunLevel Limited

$backendAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$backendScript`""

$frontendAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$frontendScript`""

$backendTrigger = New-ScheduledTaskTrigger -AtLogOn -User $taskUser
$frontendTrigger = New-ScheduledTaskTrigger -AtLogOn -User $taskUser

Unregister-ScheduledTask -TaskName $backendTaskName -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $frontendTaskName -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask `
    -TaskName $backendTaskName `
    -Description "Start the StarMap FastAPI backend at Windows logon." `
    -Action $backendAction `
    -Trigger $backendTrigger `
    -Principal $principal `
    -Settings $settings | Out-Null

Register-ScheduledTask `
    -TaskName $frontendTaskName `
    -Description "Start the StarMap frontend static server at Windows logon." `
    -Action $frontendAction `
    -Trigger $frontendTrigger `
    -Principal $principal `
    -Settings $settings | Out-Null

Start-ScheduledTask -TaskName $backendTaskName
Start-ScheduledTask -TaskName $frontendTaskName

Write-Host "Installed and started:"
Write-Host "  $backendTaskName"
Write-Host "  $frontendTaskName"
