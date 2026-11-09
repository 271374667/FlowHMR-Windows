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

function Join-FlowHMRDesktopJob([string]$Name) {
    # Join before launching Python so the interpreter and all its children inherit the job.
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;

public static class FlowHMRDesktopJob
{
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr OpenJobObject(uint access, bool inherit, string name);

    [DllImport("kernel32.dll")]
    private static extern IntPtr GetCurrentProcess();

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);

    [DllImport("kernel32.dll")]
    private static extern bool CloseHandle(IntPtr handle);

    public static void Join(string name)
    {
        IntPtr job = OpenJobObject(1, false, name); // JOB_OBJECT_ASSIGN_PROCESS
        if (job == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error());
        try
        {
            if (!AssignProcessToJobObject(job, GetCurrentProcess()))
                throw new Win32Exception(Marshal.GetLastWin32Error());
        }
        finally { CloseHandle(job); }
    }
}
'@
    [FlowHMRDesktopJob]::Join($Name)
}
