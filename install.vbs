' 安装到 Windows 启动项 (静默, 无黑窗)
' 双击运行即可注册; 再次双击会覆盖更新
Option Explicit
Dim sh, fso, scriptPath, startup, target, ws, lnk
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptPath = fso.GetParentFolderName(WScript.ScriptFullName)
startup = sh.SpecialFolders("Startup")
target = startup & "\IPO_Alert.vbs"

' 写入启动器: 静默调用 pythonw 跑 main.py
Dim launcher
launcher = "Set sh = CreateObject(""WScript.Shell"")" & vbCrLf & _
           "sh.CurrentDirectory = """ & scriptPath & """" & vbCrLf & _
           "sh.Run ""pythonw.exe main.py"", 0, False" & vbCrLf

Dim outFile
Set outFile = fso.CreateTextFile(target, True)
outFile.Write launcher
outFile.Close

WScript.Echo "已注册开机启动: " & target & vbCrLf & vbCrLf & _
             "下次开机会自动检查新股,有则在右下角弹出浮窗。" & vbCrLf & _
             "立即测试请双击: test.bat"
