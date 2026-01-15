$p = Start-Process python -ArgumentList "run_system.py" -PassThru -NoNewWindow
Write-Host "System started with PID $($p.Id). Waiting 30 seconds..."
Start-Sleep -Seconds 30
Write-Host "Stopping system..."
Stop-Process -Id $p.Id -Force
# Also kill children if possible (simpler to just kill all python processes started from this location, but let's try to be specific or wide)
# Since run_system spawns subprocesses, strictly killing parent might leave orphans if not careful, but run_system handles SIGTERM usually. 
# However, on Windows Stop-Process -Force is abrupt.
# Let's just cleanup all python processes in this folder context if possible, or just kill 'python' generally as user allowed before.
# For safety in this test, precise kill is better, but orphans are annoying.
# I'll rely on the previous "kill all python" strategy if needed, but here let's try to be clean.
Get-WmiObject Win32_Process | Where-Object { $_.ParentProcessId -eq $p.Id } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Write-Host "System stopped."
