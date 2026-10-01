if (-not ("ProofLoop.QwenNativeProcess" -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;

namespace ProofLoop {
    public sealed class QwenChildProcess {
        public IntPtr ProcessHandle;
        public IntPtr ThreadHandle;
        public IntPtr JobHandle;
        public uint ProcessId;
    }

    public static class QwenNativeProcess {
        const uint CREATE_SUSPENDED = 0x00000004;
        const uint CREATE_NEW_PROCESS_GROUP = 0x00000200;
        const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000;
        const uint STARTF_USESTDHANDLES = 0x00000100;
        const uint WAIT_OBJECT_0 = 0x00000000;
        const uint WAIT_TIMEOUT = 0x00000102;

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        struct STARTUPINFO {
            public int cb;
            public string lpReserved;
            public string lpDesktop;
            public string lpTitle;
            public int dwX;
            public int dwY;
            public int dwXSize;
            public int dwYSize;
            public int dwXCountChars;
            public int dwYCountChars;
            public int dwFillAttribute;
            public uint dwFlags;
            public short wShowWindow;
            public short cbReserved2;
            public IntPtr lpReserved2;
            public IntPtr hStdInput;
            public IntPtr hStdOutput;
            public IntPtr hStdError;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct PROCESS_INFORMATION {
            public IntPtr hProcess;
            public IntPtr hThread;
            public uint dwProcessId;
            public uint dwThreadId;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct SECURITY_ATTRIBUTES {
            public int nLength;
            public IntPtr lpSecurityDescriptor;
            public bool bInheritHandle;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct BASIC_LIMIT_INFORMATION {
            public long PerProcessUserTimeLimit;
            public long PerJobUserTimeLimit;
            public uint LimitFlags;
            public UIntPtr MinimumWorkingSetSize;
            public UIntPtr MaximumWorkingSetSize;
            public uint ActiveProcessLimit;
            public UIntPtr Affinity;
            public uint PriorityClass;
            public uint SchedulingClass;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct IO_COUNTERS {
            public ulong ReadOperationCount;
            public ulong WriteOperationCount;
            public ulong OtherOperationCount;
            public ulong ReadTransferCount;
            public ulong WriteTransferCount;
            public ulong OtherTransferCount;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct EXTENDED_LIMIT_INFORMATION {
            public BASIC_LIMIT_INFORMATION BasicLimitInformation;
            public IO_COUNTERS IoInfo;
            public UIntPtr ProcessMemoryLimit;
            public UIntPtr JobMemoryLimit;
            public UIntPtr PeakProcessMemoryUsed;
            public UIntPtr PeakJobMemoryUsed;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct BASIC_ACCOUNTING_INFORMATION {
            public long TotalUserTime;
            public long TotalKernelTime;
            public long ThisPeriodTotalUserTime;
            public long ThisPeriodTotalKernelTime;
            public uint TotalPageFaultCount;
            public uint TotalProcesses;
            public uint ActiveProcesses;
            public uint TotalTerminatedProcesses;
        }

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern IntPtr CreateJobObject(IntPtr attributes, string name);
        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool SetInformationJobObject(IntPtr job, int infoClass, ref EXTENDED_LIMIT_INFORMATION info, uint length);
        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool QueryInformationJobObject(IntPtr job, int infoClass, out BASIC_ACCOUNTING_INFORMATION info, uint length, out uint returned);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern bool CreateProcess(string application, StringBuilder commandLine, IntPtr processAttributes, IntPtr threadAttributes, bool inheritHandles, uint creationFlags, IntPtr environment, string currentDirectory, ref STARTUPINFO startup, out PROCESS_INFORMATION information);
        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
        [DllImport("kernel32.dll", SetLastError = true)]
        static extern uint ResumeThread(IntPtr thread);
        [DllImport("kernel32.dll", SetLastError = true)]
        static extern uint WaitForSingleObject(IntPtr handle, uint milliseconds);
        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool GetExitCodeProcess(IntPtr process, out uint exitCode);
        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool GenerateConsoleCtrlEvent(uint eventType, uint processGroupId);
        [DllImport("kernel32.dll")]
        static extern IntPtr GetCurrentProcess();
        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool DuplicateHandle(IntPtr sourceProcess, IntPtr sourceHandle, IntPtr targetProcess, out IntPtr targetHandle, uint desiredAccess, bool inheritHandle, uint options);
        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool TerminateJobObject(IntPtr job, uint exitCode);
        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool TerminateProcess(IntPtr process, uint exitCode);
        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool CloseHandle(IntPtr handle);
        [DllImport("kernel32.dll")]
        static extern IntPtr GetStdHandle(int handle);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern IntPtr CreateFile(string fileName, uint access, uint shareMode, ref SECURITY_ATTRIBUTES security, uint creationDisposition, uint flagsAndAttributes, IntPtr templateFile);

        static IntPtr DuplicateInheritedStandardHandle(int handleId) {
            IntPtr source = GetStdHandle(handleId);
            if (source == IntPtr.Zero || source == new IntPtr(-1)) throw new InvalidOperationException("visible console handle unavailable");
            IntPtr duplicate;
            if (!DuplicateHandle(GetCurrentProcess(), source, GetCurrentProcess(), out duplicate, 0, true, 2)) {
                throw new InvalidOperationException("visible console handle unavailable");
            }
            return duplicate;
        }

        public static string QuoteArgument(string argument) {
            if (argument == null) return "\"\"";
            if (argument.Length > 0 && argument.IndexOfAny(new char[] {' ', '\t', '\n', '\v', '"'}) < 0) return argument;
            StringBuilder result = new StringBuilder();
            result.Append('"');
            int slashes = 0;
            foreach (char value in argument) {
                if (value == '\\') { slashes++; continue; }
                if (value == '"') {
                    result.Append('\\', slashes * 2 + 1);
                    result.Append('"');
                    slashes = 0;
                    continue;
                }
                result.Append('\\', slashes);
                slashes = 0;
                result.Append(value);
            }
            result.Append('\\', slashes * 2);
            result.Append('"');
            return result.ToString();
        }

        public static string QuoteCmdArgument(string argument) {
            if (argument == null) return "\"\"";
            if (argument.IndexOf('%') < 0) return QuoteArgument(argument);
            StringBuilder result = new StringBuilder();
            int start = 0;
            for (int index = 0; index < argument.Length; index++) {
                if (argument[index] != '%') continue;
                result.Append(QuoteArgument(argument.Substring(start, index - start)));
                result.Append("^%");
                start = index + 1;
            }
            result.Append(QuoteArgument(argument.Substring(start)));
            return result.ToString();
        }

        public static QwenChildProcess Start(string executable, string commandLine, string currentDirectory, bool showOutput, string stdoutFilePath, string stderrFilePath) {
            IntPtr job = CreateJobObject(IntPtr.Zero, null);
            if (job == IntPtr.Zero) throw new InvalidOperationException("job creation failed");
            EXTENDED_LIMIT_INFORMATION limits = new EXTENDED_LIMIT_INFORMATION();
            limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            if (!SetInformationJobObject(job, 9, ref limits, (uint)Marshal.SizeOf(typeof(EXTENDED_LIMIT_INFORMATION)))) {
                CloseHandle(job);
                throw new InvalidOperationException("job configuration failed");
            }

            STARTUPINFO startup = new STARTUPINFO();
            startup.cb = Marshal.SizeOf(typeof(STARTUPINFO));
            startup.dwFlags = STARTF_USESTDHANDLES;
            IntPtr capturedOutput = IntPtr.Zero;
            IntPtr capturedError = IntPtr.Zero;
            IntPtr inheritedInput = IntPtr.Zero;
            IntPtr inheritedOutput = IntPtr.Zero;
            IntPtr inheritedError = IntPtr.Zero;
            if (showOutput) {
                try {
                    inheritedInput = DuplicateInheritedStandardHandle(-10);
                    inheritedOutput = DuplicateInheritedStandardHandle(-11);
                    inheritedError = DuplicateInheritedStandardHandle(-12);
                    startup.hStdInput = inheritedInput;
                    startup.hStdOutput = inheritedOutput;
                    startup.hStdError = inheritedError;
                }
                catch {
                    if (inheritedInput != IntPtr.Zero) CloseHandle(inheritedInput);
                    if (inheritedOutput != IntPtr.Zero) CloseHandle(inheritedOutput);
                    if (inheritedError != IntPtr.Zero) CloseHandle(inheritedError);
                    CloseHandle(job);
                    throw;
                }
            }
            else {
                startup.hStdInput = GetStdHandle(-10);
                if (String.IsNullOrWhiteSpace(stdoutFilePath) || String.IsNullOrWhiteSpace(stderrFilePath)) {
                    CloseHandle(job);
                    throw new InvalidOperationException("suppressed output capture paths unavailable");
                }
                SECURITY_ATTRIBUTES outputSecurity = new SECURITY_ATTRIBUTES();
                outputSecurity.nLength = Marshal.SizeOf(typeof(SECURITY_ATTRIBUTES));
                outputSecurity.bInheritHandle = true;
                capturedOutput = CreateFile(stdoutFilePath, 0x40000000, 0x00000003, ref outputSecurity, 3, 0x00000080, IntPtr.Zero);
                if (capturedOutput == IntPtr.Zero || capturedOutput == new IntPtr(-1)) {
                    CloseHandle(job);
                    throw new InvalidOperationException("stdout capture unavailable");
                }
                capturedError = CreateFile(stderrFilePath, 0x40000000, 0x00000003, ref outputSecurity, 3, 0x00000080, IntPtr.Zero);
                if (capturedError == IntPtr.Zero || capturedError == new IntPtr(-1)) {
                    CloseHandle(capturedOutput);
                    CloseHandle(job);
                    throw new InvalidOperationException("stderr capture unavailable");
                }
                startup.hStdOutput = capturedOutput;
                startup.hStdError = capturedError;
            }
            PROCESS_INFORMATION information;
            StringBuilder mutableCommandLine = new StringBuilder(commandLine);
            bool created = CreateProcess(
                executable, mutableCommandLine, IntPtr.Zero, IntPtr.Zero, true,
                CREATE_NEW_PROCESS_GROUP | CREATE_SUSPENDED, IntPtr.Zero,
                currentDirectory, ref startup, out information);
            if (capturedOutput != IntPtr.Zero) CloseHandle(capturedOutput);
            if (capturedError != IntPtr.Zero) CloseHandle(capturedError);
            if (inheritedInput != IntPtr.Zero) CloseHandle(inheritedInput);
            if (inheritedOutput != IntPtr.Zero) CloseHandle(inheritedOutput);
            if (inheritedError != IntPtr.Zero) CloseHandle(inheritedError);
            if (!created) {
                CloseHandle(job);
                throw new InvalidOperationException("child creation failed");
            }
            if (!AssignProcessToJobObject(job, information.hProcess)) {
                TerminateProcessAndClose(information, job);
                throw new InvalidOperationException("job assignment failed");
            }
            if (ResumeThread(information.hThread) == 0xffffffff) {
                TerminateProcessAndClose(information, job);
                throw new InvalidOperationException("child resume failed");
            }
            QwenChildProcess result = new QwenChildProcess();
            result.ProcessHandle = information.hProcess;
            result.ThreadHandle = information.hThread;
            result.JobHandle = job;
            result.ProcessId = information.dwProcessId;
            return result;
        }

        static void TerminateProcessAndClose(PROCESS_INFORMATION information, IntPtr job) {
            TerminateProcess(information.hProcess, 1);
            TerminateJobObject(job, 1);
            WaitForSingleObject(information.hProcess, 5000);
            CloseHandle(information.hThread);
            CloseHandle(information.hProcess);
            CloseHandle(job);
        }

        public static bool IsRunning(QwenChildProcess child) {
            return WaitForSingleObject(child.ProcessHandle, 0) == WAIT_TIMEOUT;
        }
        public static bool IsExited(QwenChildProcess child) {
            return WaitForSingleObject(child.ProcessHandle, 0) == WAIT_OBJECT_0;
        }
        public static bool WaitRoot(QwenChildProcess child, uint milliseconds) {
            return WaitForSingleObject(child.ProcessHandle, milliseconds) == WAIT_OBJECT_0;
        }
        public static uint ActiveProcesses(QwenChildProcess child) {
            BASIC_ACCOUNTING_INFORMATION info;
            uint returned;
            if (!QueryInformationJobObject(child.JobHandle, 1, out info, (uint)Marshal.SizeOf(typeof(BASIC_ACCOUNTING_INFORMATION)), out returned)) return UInt32.MaxValue;
            return info.ActiveProcesses;
        }
        public static bool SendBreak(QwenChildProcess child) {
            return GenerateConsoleCtrlEvent(1, child.ProcessId);
        }
        public static int ExitCode(QwenChildProcess child) {
            uint value;
            return GetExitCodeProcess(child.ProcessHandle, out value) ? unchecked((int)value) : -1;
        }
        public static void KillTree(QwenChildProcess child) {
            if (child != null && child.JobHandle != IntPtr.Zero) TerminateJobObject(child.JobHandle, 1);
        }
        public static void Close(QwenChildProcess child) {
            if (child == null) return;
            if (child.ThreadHandle != IntPtr.Zero) CloseHandle(child.ThreadHandle);
            if (child.ProcessHandle != IntPtr.Zero) CloseHandle(child.ProcessHandle);
            if (child.JobHandle != IntPtr.Zero) CloseHandle(child.JobHandle);
        }
    }
}
'@ -ErrorAction Stop
}

function Invoke-QwenProtocolChild {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$QwenCommand,
        [Parameter(Mandatory = $true)][string[]]$QwenArguments,
        [Parameter(Mandatory = $true)][string]$EventFilePath,
        [Parameter(Mandatory = $true)][string]$StdoutFilePath,
        [Parameter(Mandatory = $true)][string]$StderrFilePath,
        [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{32}$')][string]$LaunchId,
        [Parameter(Mandatory = $true)][ValidateRange(1, 40)][int]$MaxToolCalls,
        [Parameter(Mandatory = $true)][ValidateRange(1, 86400)][int]$MaxWallTimeSeconds,
        [switch]$ShowOutput
    )

    $clock = [Diagnostics.Stopwatch]::StartNew()
    $launchDiagnostic = [ordered]@{
        schema_version = 1
        supervisor_stage = 'COMMAND_RESOLUTION'
        process_state = 'NOT_STARTED'
        process_exit_code = $null
        event_file_state = 'NOT_OBSERVED'
        event_file_bytes = $null
        console_output_mode = if ($ShowOutput) { 'VISIBLE' } else { 'SUPPRESSED' }
    }
    $observation = [ordered]@{
        launch_id = $LaunchId
        child_started = $false
        process_exited = $false
        process_exit_code = $null
        host_stop_reason = $null
        host_stop_requested = $false
        host_interrupt_sent = $false
        stop_observed_while_running = $false
        session_end_seen_before_stop = $false
        event_file_bytes_at_stop = $null
        event_file_closed = $false
        elapsed_ms = 0
    }
    $child = $null
    $tail = @{
        offset = [long]0
        line_start = [long]0
        line = [Collections.Generic.List[byte]]::new()
        pending = [Collections.Generic.Dictionary[string, bool]]::new([StringComparer]::Ordinal)
        seen_tool_ids = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
        completed_tool_ids = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
        tool_calls = 0
        session_end_offset = $null
        valid = $true
    }
    $qwenExitCode = 127
    $treeComplete = $false
    $writerComplete = $false
    $eventFileFullPath = $null
    try {
        $eventFileFullPath = [IO.Path]::GetFullPath($EventFilePath)
        $extension = [IO.Path]::GetExtension($QwenCommand).ToLowerInvariant()
        $powerShellPath = (Get-Process -Id $PID -ErrorAction Stop).Path
        if ($extension -eq '.ps1') {
            $commandExecutable = $powerShellPath
            $commandArguments = @('-NoLogo', '-NoProfile', '-File', $QwenCommand) + @($QwenArguments)
        }
        elseif ($extension -eq '.exe') {
            $resolvedCommand = Get-Command -Name $QwenCommand -CommandType Application -ErrorAction Stop
            $commandExecutable = if ($resolvedCommand.Source) { $resolvedCommand.Source } else { $resolvedCommand.Path }
            $commandArguments = @($QwenArguments)
        }
        elseif ($extension -eq '.cmd') {
            $resolvedShim = Resolve-QwenCmdNodeShim -QwenCommand $QwenCommand
            if ($null -eq $resolvedShim) { throw 'unsupported Qwen command wrapper' }
            $commandExecutable = $resolvedShim.node_executable
            $commandArguments = @($resolvedShim.entrypoint) + @($QwenArguments)
        }
        else {
            throw 'unsupported Qwen command type'
        }
        $commandParts = @([ProofLoop.QwenNativeProcess]::QuoteArgument($commandExecutable))
        foreach ($argument in $commandArguments) {
            $commandParts += [ProofLoop.QwenNativeProcess]::QuoteArgument([string]$argument)
        }
        $commandLine = $commandParts -join ' '
        if ($commandLine.Length -ge 32000) { throw 'unsupported launch size' }
        $launchDiagnostic.supervisor_stage = 'PROCESS_CREATION'
        $child = [ProofLoop.QwenNativeProcess]::Start(
            $commandExecutable, $commandLine, (Get-Location).Path, [bool]$ShowOutput,
            $StdoutFilePath, $StderrFilePath
        )
        $observation.child_started = $true
        $launchDiagnostic.supervisor_stage = 'CHILD_STARTED'
        $launchDiagnostic.process_state = 'RUNNING'
        $maximumBytes = 16 * 1024 * 1024

        while ($true) {
            Update-QwenEventTail -Path $eventFileFullPath -State $tail -MaximumBytes $maximumBytes
            $active = [ProofLoop.QwenNativeProcess]::ActiveProcesses($child)
            $rootExited = [ProofLoop.QwenNativeProcess]::IsExited($child)
            if ($active -eq 0 -and $rootExited) {
                $treeComplete = $true
                $writerComplete = $true
                break
            }
            if ($rootExited -or $active -eq [uint32]::MaxValue) {
                break
            }
            if ($tail.valid -and $tail.tool_calls -ge $MaxToolCalls) {
                $observation.host_stop_reason = 'HOST_TOOL_LIMIT'
            }
            elseif ($clock.Elapsed.TotalSeconds -ge $MaxWallTimeSeconds) {
                $observation.host_stop_reason = 'HOST_WALL_LIMIT'
            }
            if ($null -ne $observation.host_stop_reason) {
                if ([ProofLoop.QwenNativeProcess]::IsRunning($child)) {
                    $observation.host_stop_requested = $true
                    $observation.stop_observed_while_running = $true
                    Update-QwenEventTail -Path $eventFileFullPath -State $tail -MaximumBytes $maximumBytes
                    $observation.session_end_seen_before_stop = $null -ne $tail.session_end_offset
                    if (-not [ProofLoop.QwenNativeProcess]::IsRunning($child)) {
                        $observation.host_stop_reason = $null
                        $observation.host_stop_requested = $false
                        $observation.stop_observed_while_running = $false
                        $observation.session_end_seen_before_stop = $false
                        continue
                    }
                    try {
                        $observation.event_file_bytes_at_stop = (Get-Item -LiteralPath $eventFileFullPath -ErrorAction Stop).Length
                    }
                    catch {
                        $observation.event_file_bytes_at_stop = -1
                    }
                    $observation.host_interrupt_sent = [ProofLoop.QwenNativeProcess]::SendBreak($child)
                    $grace = [Diagnostics.Stopwatch]::StartNew()
                    while ($grace.Elapsed.TotalSeconds -lt 5) {
                        Update-QwenEventTail -Path $eventFileFullPath -State $tail -MaximumBytes $maximumBytes
                        $active = [ProofLoop.QwenNativeProcess]::ActiveProcesses($child)
                        $rootExited = [ProofLoop.QwenNativeProcess]::IsExited($child)
                        $endAfterStop = $null -ne $tail.session_end_offset -and $tail.session_end_offset -ge $observation.event_file_bytes_at_stop
                        if ($active -eq 0 -and $rootExited) {
                            $treeComplete = $true
                            $writerComplete = $true
                            break
                        }
                        Start-Sleep -Milliseconds 100
                    }
                    if (-not $treeComplete) {
                        [ProofLoop.QwenNativeProcess]::KillTree($child)
                        [void][ProofLoop.QwenNativeProcess]::WaitRoot($child, 5000)
                        $postKill = [Diagnostics.Stopwatch]::StartNew()
                        while ($postKill.Elapsed.TotalSeconds -lt 5 -and [ProofLoop.QwenNativeProcess]::ActiveProcesses($child) -ne 0) {
                            Start-Sleep -Milliseconds 100
                        }
                        Update-QwenEventTail -Path $eventFileFullPath -State $tail -MaximumBytes $maximumBytes
                        $treeComplete = [ProofLoop.QwenNativeProcess]::ActiveProcesses($child) -eq 0
                        $writerComplete = $treeComplete
                    }
                    break
                }
                # A process that exits at the threshold wins the race; do not claim host ownership.
                $observation.host_stop_reason = $null
            }
            Start-Sleep -Milliseconds 100
        }

        if (-not $treeComplete -and $null -ne $child) {
            [ProofLoop.QwenNativeProcess]::KillTree($child)
            [void][ProofLoop.QwenNativeProcess]::WaitRoot($child, 5000)
            $postKill = [Diagnostics.Stopwatch]::StartNew()
            while ($postKill.Elapsed.TotalSeconds -lt 5 -and [ProofLoop.QwenNativeProcess]::ActiveProcesses($child) -ne 0) {
                Start-Sleep -Milliseconds 100
            }
            Update-QwenEventTail -Path $eventFileFullPath -State $tail -MaximumBytes $maximumBytes
            $treeComplete = [ProofLoop.QwenNativeProcess]::ActiveProcesses($child) -eq 0
            $writerComplete = $treeComplete
        }
        if ($null -ne $child) {
            $observation.process_exit_code = [ProofLoop.QwenNativeProcess]::ExitCode($child)
            $observation.process_exited = [bool]$treeComplete
            $observation.event_file_closed = [bool]$writerComplete
            $qwenExitCode = $observation.process_exit_code
            if ($observation.process_exited) {
                $launchDiagnostic.supervisor_stage = 'PROCESS_EXITED'
                $launchDiagnostic.process_state = 'EXITED'
                $launchDiagnostic.process_exit_code = [int]$observation.process_exit_code
            }
            else {
                $launchDiagnostic.supervisor_stage = 'PROCESS_EXIT_UNCONFIRMED'
                $launchDiagnostic.process_state = 'UNKNOWN'
            }
        }
    }
    catch {
        $launchDiagnostic.supervisor_stage = switch ([string]$launchDiagnostic.supervisor_stage) {
            'COMMAND_RESOLUTION' { 'COMMAND_RESOLUTION_FAILED' }
            'PROCESS_CREATION' { 'PROCESS_CREATION_FAILED' }
            default { 'CHILD_MONITOR_FAILED' }
        }
        if ($null -ne $child) {
            [ProofLoop.QwenNativeProcess]::KillTree($child)
            [void][ProofLoop.QwenNativeProcess]::WaitRoot($child, 5000)
            $observation.process_exit_code = [ProofLoop.QwenNativeProcess]::ExitCode($child)
            $observation.process_exited = ([ProofLoop.QwenNativeProcess]::ActiveProcesses($child) -eq 0)
            $observation.event_file_closed = $observation.process_exited
            if ($observation.process_exited) {
                $launchDiagnostic.process_state = 'EXITED'
                $launchDiagnostic.process_exit_code = [int]$observation.process_exit_code
            }
            else {
                $launchDiagnostic.process_state = 'UNKNOWN'
            }
        }
    }
    finally {
        if ($null -ne $child) { [ProofLoop.QwenNativeProcess]::Close($child) }
        $clock.Stop()
        $observation.elapsed_ms = [int][Math]::Min([int]::MaxValue, $clock.ElapsedMilliseconds)
        try {
            if ($null -eq $eventFileFullPath) {
                $launchDiagnostic.event_file_state = 'NOT_OBSERVED'
            }
            elseif (Test-Path -LiteralPath $eventFileFullPath -PathType Leaf) {
                $eventBytes = [long](Get-Item -LiteralPath $eventFileFullPath -ErrorAction Stop).Length
                $launchDiagnostic.event_file_state = if ($eventBytes -eq 0) { 'EMPTY' } else { 'PRESENT' }
                $launchDiagnostic.event_file_bytes = [long][Math]::Min($eventBytes, 2147483647)
            }
            else {
                $launchDiagnostic.event_file_state = 'MISSING'
            }
        }
        catch {
            $launchDiagnostic.event_file_state = 'UNAVAILABLE'
            $launchDiagnostic.event_file_bytes = $null
        }
        if ($launchDiagnostic.process_state -eq 'RUNNING') { $launchDiagnostic.process_state = 'UNKNOWN' }
        if ($launchDiagnostic.supervisor_stage -eq 'CHILD_STARTED') { $launchDiagnostic.supervisor_stage = 'PROCESS_EXIT_UNCONFIRMED' }
    }
    [pscustomobject]@{
        qwen_exit_code = $qwenExitCode
        process_observation = [pscustomobject]$observation
        launch_diagnostic = [pscustomobject]$launchDiagnostic
    }
}

function Resolve-QwenCmdNodeShim {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$QwenCommand)

    try {
        $command = Get-Command -Name $QwenCommand -ErrorAction Stop | Select-Object -First 1
        $wrapperPath = if ($command.Source) { [string]$command.Source } else { [string]$command.Path }
        if ([IO.Path]::GetExtension($wrapperPath) -ine '.cmd' -or
            -not (Test-Path -LiteralPath $wrapperPath -PathType Leaf)) { return $null }

        $wrapperText = [IO.File]::ReadAllText($wrapperPath)
        $wrapperLines = @($wrapperText.TrimStart([char]0xFEFF).TrimEnd("`r", "`n") -split "`r?`n")
        if ($wrapperLines.Count -ne 17) { return $null }

        $expectedFixedLines = @(
            '@ECHO off',
            'GOTO start',
            ':find_dp0',
            'SET dp0=%~dp0',
            'EXIT /b',
            ':start',
            'SETLOCAL',
            'CALL :find_dp0',
            '',
            $null,
            $null,
            ') ELSE (',
            'SET "_prog=node"',
            'SET PATHEXT=%PATHEXT:;.JS;=;%',
            ')',
            '',
            $null
        )
        for ($index = 0; $index -lt $expectedFixedLines.Count; $index++) {
            if ($null -eq $expectedFixedLines[$index]) { continue }
            if ($wrapperLines[$index].Trim() -ine $expectedFixedLines[$index]) { return $null }
        }
        if ($wrapperLines[9].Trim() -notmatch '(?i)^IF\s+EXIST\s+"%dp0%\\node\.exe"\s*\($') { return $null }
        if ($wrapperLines[10].Trim() -notmatch '(?i)^SET\s+"_prog=%dp0%\\node\.exe"$') { return $null }
        if ($wrapperLines[16].Trim() -notmatch '(?i)^endLocal\s*&\s*goto\s+#_undefined_#\s+2>NUL\s+\|\|\s+title\s+%COMSPEC%\s*&\s+"%_prog%"\s+"%dp0%\\node_modules\\@qwen-code\\qwen-code\\cli-entry\.js"\s+%\*$') { return $null }

        $wrapperDirectory = Split-Path -Parent ([IO.Path]::GetFullPath($wrapperPath))
        $entrypoint = [IO.Path]::GetFullPath((Join-Path $wrapperDirectory 'node_modules\@qwen-code\qwen-code\cli-entry.js'))
        if (-not (Test-Path -LiteralPath $entrypoint -PathType Leaf)) { return $null }

        $localNode = Join-Path $wrapperDirectory 'node.exe'
        if (Test-Path -LiteralPath $localNode -PathType Leaf) {
            $nodeExecutable = [IO.Path]::GetFullPath($localNode)
        }
        else {
            $nodeCommand = Get-Command -Name 'node.exe' -CommandType Application -ErrorAction Stop | Select-Object -First 1
            $nodeExecutable = if ($nodeCommand.Source) { [string]$nodeCommand.Source } else { [string]$nodeCommand.Path }
            if ([IO.Path]::GetExtension($nodeExecutable) -ine '.exe' -or
                -not (Test-Path -LiteralPath $nodeExecutable -PathType Leaf)) { return $null }
        }

        return [pscustomobject]@{
            node_executable = $nodeExecutable
            entrypoint = $entrypoint
        }
    }
    catch {
        return $null
    }
}

function Invoke-QwenProtocolCapabilityProbe {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$QwenCommand)

    try {
        $extension = [IO.Path]::GetExtension($QwenCommand).ToLowerInvariant()
        if ($extension -eq '.cmd') {
            $resolvedShim = Resolve-QwenCmdNodeShim -QwenCommand $QwenCommand
            if ($null -eq $resolvedShim) {
                return [pscustomobject]@{ command_supported = $false; output = ''; exit_code = 127 }
            }
            $commandExecutable = [string]$resolvedShim.node_executable
            $commandArguments = @([string]$resolvedShim.entrypoint, '--help')
        }
        elseif ($extension -eq '.ps1') {
            $commandExecutable = (Get-Process -Id $PID -ErrorAction Stop).Path
            $commandArguments = @('-NoLogo', '-NoProfile', '-File', $QwenCommand, '--help')
        }
        elseif ($extension -eq '.exe') {
            $resolvedCommand = Get-Command -Name $QwenCommand -CommandType Application -ErrorAction Stop
            $commandExecutable = if ($resolvedCommand.Source) { [string]$resolvedCommand.Source } else { [string]$resolvedCommand.Path }
            $commandArguments = @('--help')
        }
        else {
            return [pscustomobject]@{ command_supported = $false; output = ''; exit_code = 127 }
        }

        $output = (& $commandExecutable @commandArguments 2>&1 | Out-String)
        $exitCode = if (Test-Path Variable:global:LASTEXITCODE) { [int]$global:LASTEXITCODE } else { 0 }
        return [pscustomobject]@{
            command_supported = $true
            output = [string]$output
            exit_code = $exitCode
        }
    }
    catch {
        return [pscustomobject]@{ command_supported = $false; output = ''; exit_code = 127 }
    }
}

function Update-QwenEventTail {
    param([string]$Path, [hashtable]$State, [long]$MaximumBytes)
    try {
        $stream = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
        try {
            $length = $stream.Length
            if ($length -gt $MaximumBytes -or $length -lt $State.offset) {
                $State.valid = $false
                $State.reason = 'EVENT_FILE_RANGE_INVALID'
                return
            }
            $stream.Position = $State.offset
            $buffer = New-Object byte[] 65536
            while (($read = $stream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                $baseOffset = $State.offset
                for ($index = 0; $index -lt $read; $index++) {
                    if ($buffer[$index] -eq 10) {
                        $lineBytes = $State.line.ToArray()
                        $State.line.Clear()
                        if ($lineBytes.Length -gt 0 -and $lineBytes[$lineBytes.Length - 1] -eq 13) {
                            $lineBytes = $lineBytes[0..($lineBytes.Length - 2)]
                        }
                        if ($lineBytes.Length -eq 0 -or $lineBytes.Length -gt 1024 * 1024) {
                            $State.valid = $false
                            $State.reason = 'EVENT_LINE_INVALID'
                        }
                        else {
                            try {
                                $line = [Text.UTF8Encoding]::new($false, $true).GetString($lineBytes)
                                $event = ConvertFrom-Json -InputObject $line -ErrorAction Stop
                                Update-QwenEventProjection -Event $event -State $State -LineStart $State.line_start
                            }
                            catch {
                                $State.valid = $false
                                $State.reason = 'EVENT_LINE_OR_SCHEMA_INVALID'
                            }
                        }
                        $State.line_start = $baseOffset + $index + 1
                    }
                    else {
                        $State.line.Add($buffer[$index])
                        if ($State.line.Count -gt 1024 * 1024) { $State.valid = $false; $State.reason = 'EVENT_LINE_TOO_LARGE' }
                    }
                }
                $State.offset = $baseOffset + $read
            }
        }
        finally {
            $stream.Dispose()
        }
    }
    catch {
        # The event writer can briefly hold an incompatible sharing mode while appending.
        # Leave the byte cursor unchanged and retry on the next poll; final projection rereads
        # the closed file and fails closed if this was a persistent access failure.
        $State.read_error_seen = $true
    }
}

function Update-QwenEventProjection {
    param([object]$Event, [hashtable]$State, [long]$LineStart)
    $type = [string]$Event.type
    if ($State.session_end_offset -ne $null) { $State.valid = $false; $State.reason = 'EVENT_AFTER_SESSION_END'; return }
    if ($type -eq 'system' -and $Event.subtype -in @('session_start', 'init')) {
        if ($State.session_started -or [string]::IsNullOrWhiteSpace([string]$Event.session_id)) { $State.valid = $false; $State.reason = 'SESSION_START_INVALID' }
        $State.session_started = $true
        $State.session_id = [string]$Event.session_id
        return
    }
    if (-not $State.session_started) { $State.valid = $false; $State.reason = 'EVENT_BEFORE_SESSION_START'; return }
    if ($type -eq 'system' -and $Event.subtype -eq 'session_end') {
        $State.session_end_offset = $LineStart
        return
    }
    if ($type -eq 'result') {
        $errorProperty = $Event.PSObject.Properties['is_error']
        if ([string]$Event.session_id -cne [string]$State.session_id -or
            [string]::IsNullOrWhiteSpace([string]$Event.subtype) -or
            ($null -ne $errorProperty -and $errorProperty.Value -isnot [bool]) -or
            $State.pending.Count -ne 0) {
            $State.valid = $false
            $State.reason = 'TERMINAL_RESULT_INVALID'
        }
        else {
            $State.session_end_offset = $LineStart
        }
        return
    }
    if ($type -eq 'assistant') {
        $message = $Event.message
        foreach ($block in @($message.content)) {
            if ($block.type -eq 'tool_use') {
                $id = [string]$block.id
                if ([string]::IsNullOrWhiteSpace($id) -or [string]::IsNullOrWhiteSpace([string]$block.name) -or $null -eq $block.input -or -not $State.seen_tool_ids.Add($id)) {
                    $State.valid = $false
                    $State.reason = 'TOOL_USE_INVALID'
                }
                else { $State.pending[$id] = $true }
            }
            elseif ($block.type -eq 'thinking') {
                if ($block.thinking -isnot [string]) { $State.valid = $false; $State.reason = 'ASSISTANT_BLOCK_INVALID' }
            }
            elseif ($block.type -ne 'text') { $State.valid = $false; $State.reason = 'ASSISTANT_BLOCK_UNKNOWN' }
        }
        return
    }
    if ($type -eq 'user') {
        foreach ($block in @($Event.message.content)) {
            if ($block.type -eq 'tool_result') {
                $id = [string]$block.tool_use_id
                if (-not $State.pending.ContainsKey($id) -or $State.completed_tool_ids.Contains($id)) {
                    $State.valid = $false
                    $State.reason = 'TOOL_RESULT_UNPAIRED'
                }
                else {
                    [void]$State.pending.Remove($id)
                    [void]$State.completed_tool_ids.Add($id)
                    $State.tool_calls++
                }
            }
            elseif ($block.type -ne 'text') { $State.valid = $false; $State.reason = 'USER_BLOCK_UNKNOWN' }
        }
        return
    }
    if ($type -notin @('control_request', 'control_response', 'stream_event', 'result')) { $State.valid = $false; $State.reason = 'EVENT_TYPE_UNKNOWN' }
}
