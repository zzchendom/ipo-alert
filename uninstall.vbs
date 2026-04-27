' 从启动项移除
Option Explicit
Dim sh, fso, startup, target
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
startup = sh.SpecialFolders("Startup")
target = startup & "\IPO_Alert.vbs"
If fso.FileExists(target) Then
    fso.DeleteFile target
    WScript.Echo "已移除开机启动: " & target
Else
    WScript.Echo "未找到启动项,可能尚未安装。"
End If
