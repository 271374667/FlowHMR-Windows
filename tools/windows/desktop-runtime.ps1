function Get-FlowHMRDesktopRuntime([string]$ProjectRoot) {
    $portable = Join-Path $ProjectRoot 'runtime\pythonw.exe'
    if (Test-Path -LiteralPath $portable -PathType Leaf) { return $portable }
    $cfg = Join-Path $ProjectRoot '.venv\pyvenv.cfg'
    $homeEntry = Select-String -LiteralPath $cfg -Pattern '^home\s*=\s*(.+)$' | Select-Object -First 1
    if (-not $homeEntry) { throw 'FlowHMR Python runtime was not found.' }
    # Some uv Windows environments provide a console-subsystem pythonw.exe shim.
    # Use the real GUI-subsystem executable of the interpreter that owns the venv.
    $launcher = Join-Path $homeEntry.Matches[0].Groups[1].Value.Trim() 'pythonw.exe'
    if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw 'FlowHMR pythonw.exe is missing.' }
    return $launcher
}

function Get-FlowHMRConsoleRuntime([string]$ProjectRoot) {
    $portable = Join-Path $ProjectRoot 'runtime\python.exe'
    if (Test-Path -LiteralPath $portable -PathType Leaf) { return $portable }
    $python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'FlowHMR Python runtime was not found.' }
    return $python
}
