Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-StarMapRootDir {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptRoot
    )

    return (Resolve-Path (Join-Path $ScriptRoot "..")).Path
}

function Ensure-StarMapLogDir {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RootDir
    )

    $logDir = Join-Path $RootDir "logs"
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    return $logDir
}

function Get-StarMapPythonCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RootDir
    )

    $venvPython = Join-Path $RootDir "backend\.venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return @{
            FilePath = $venvPython
            Arguments = @()
        }
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $pyLauncher) {
        return @{
            FilePath = $pyLauncher.Source
            Arguments = @("-3")
        }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $python) {
        return @{
            FilePath = $python.Source
            Arguments = @()
        }
    }

    throw "No Python interpreter found. Create backend\.venv\Scripts\python.exe or make 'py'/'python' available on PATH."
}
