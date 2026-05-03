Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "windows_common.ps1")

$rootDir = Get-StarMapRootDir -ScriptRoot $PSScriptRoot
$logDir = Ensure-StarMapLogDir -RootDir $rootDir
$stdoutLog = Join-Path $logDir "frontend.stdout.log"
$stderrLog = Join-Path $logDir "frontend.stderr.log"
$python = Get-StarMapPythonCommand -RootDir $rootDir

Push-Location $rootDir
try {
    & $python.FilePath @($python.Arguments + @("-m", "http.server", "8000", "--bind", "127.0.0.1", "--directory", "frontend")) 1>> $stdoutLog 2>> $stderrLog
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
