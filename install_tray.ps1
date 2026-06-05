# 安装"新股申购提醒"托盘版为开机自启(计划任务方式, 比 Startup 文件夹可靠)
# 用法: 右键 install_tray.bat -> 直接运行(无需管理员); 或在本目录 PowerShell 执行 .\install_tray.ps1
# 卸载: uninstall_tray.ps1

$ErrorActionPreference = "Stop"
$TaskName = "IPO_Alert_Tray"

# 1. 仓库目录 = 本脚本所在目录
$dir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# 2. 探测 pythonw.exe: 优先 PATH, 其次常见安装位置
$exe = $null
$cmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
if ($cmd) { $exe = $cmd.Source }
if (-not $exe) {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python3*\pythonw.exe",
        "$env:USERPROFILE\python3*\pythonw.exe",
        "C:\Python3*\pythonw.exe"
    )
    foreach ($pat in $candidates) {
        $hit = Get-ChildItem -Path $pat -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($hit) { $exe = $hit.FullName; break }
    }
}
if (-not $exe) {
    Write-Host "未找到 pythonw.exe, 请先安装 Python (勾选 Add to PATH), 或手动改本脚本的 `$exe 变量。" -ForegroundColor Red
    exit 1
}

Write-Host "Python:   $exe"
Write-Host "脚本目录: $dir"

# 3. 注册计划任务: 登录后延迟 30 秒启动 (避开开机时托盘区未就绪的竞态)
$action  = New-ScheduledTaskAction -Execute $exe -Argument "tray.py" -WorkingDirectory $dir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$trigger.Delay = "PT30S"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description "新股申购提醒托盘 - 登录30秒后启动" -Force | Out-Null

# 4. 清理旧的 Startup 文件夹启动项(若存在), 避免双开
$oldVbs = Join-Path ([Environment]::GetFolderPath("Startup")) "IPO_Alert.vbs"
if (Test-Path -LiteralPath $oldVbs) {
    Remove-Item -LiteralPath $oldVbs -Force
    Write-Host "已移除旧的 Startup 启动项: $oldVbs" -ForegroundColor Yellow
}

# 5. 立即启动一次, 让托盘图标马上出现
Start-ScheduledTask -TaskName $TaskName

Write-Host ""
Write-Host "安装完成! 计划任务 [$TaskName] 已注册, 下次登录会自动启动。" -ForegroundColor Green
Write-Host "托盘图标'申'已启动 —— 若没看到, 点任务栏的 ^ 展开, 把它拖到时钟旁常显。"
