# 卸载"新股申购提醒"托盘版的开机自启(计划任务方式)
# 用法: 右键 uninstall_tray.bat 运行; 或在本目录 PowerShell 执行 .\uninstall_tray.ps1

$ErrorActionPreference = "SilentlyContinue"
$TaskName = "IPO_Alert_Tray"

# 1. 关掉正在运行的托盘进程
Get-ScheduledTask -TaskName $TaskName | Stop-ScheduledTask
Get-Process pythonw -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like "*tray.py*" -or $_.CommandLine -like "*tray.py*" } |
    Stop-Process -Force

# 2. 删除计划任务
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "已删除计划任务: $TaskName" -ForegroundColor Green
} else {
    Write-Host "未找到计划任务 $TaskName, 可能未安装。"
}

# 3. 一并清理可能残留的旧 Startup 启动项
$oldVbs = Join-Path ([Environment]::GetFolderPath("Startup")) "IPO_Alert.vbs"
if (Test-Path -LiteralPath $oldVbs) {
    Remove-Item -LiteralPath $oldVbs -Force
    Write-Host "已移除旧的 Startup 启动项: $oldVbs" -ForegroundColor Yellow
}
