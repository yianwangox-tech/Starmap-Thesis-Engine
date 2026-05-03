Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "windows_common.ps1")

$rootDir = Get-StarMapRootDir -ScriptRoot $PSScriptRoot
$logDir = Ensure-StarMapLogDir -RootDir $rootDir
$stdoutLog = Join-Path $logDir "backend.stdout.log"
$stderrLog = Join-Path $logDir "backend.stderr.log"
$python = Get-StarMapPythonCommand -RootDir $rootDir

Push-Location (Join-Path $rootDir "backend")
try {
    & $python.FilePath @($python.Arguments + @("main.py")) 1>> $stdoutLog 2>> $stderrLog
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
