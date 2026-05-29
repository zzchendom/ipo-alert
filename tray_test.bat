@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo === 托盘常驻版测试 (mock 数据: 3 只新股, 含 1 只大肉签) ===
echo.
echo  右下角任务栏(时钟旁)会出现一个"申"字小图标:
echo    - 左键点它          = 打开今日报告, 然后图标消失(真实行为)
echo    - 右键 - 提示方式    = 切换 图标变色 / 弹浮窗 / 气泡通知
echo    - 右键 - 立即检查    = 按当前提示方式再演示一次弹窗
echo    - 右键 - 退出        = 结束程序
echo.
echo  想再完整测一遍: 关掉(或忽略)上一个, 重新双击本脚本即可。
echo.

REM 解析可用解释器: 本机 PATH 的 python 多为商店占位符, 优先 pythonw
set "PYEXE=pythonw"
if defined IPO_ALERT_PYTHON set "PYEXE=%IPO_ALERT_PYTHON%"

REM 每次测试先清掉"今日已看/已提示"标记, 这样能反复看到完整效果(点开->消失)
"%PYEXE%" -c "import json,pathlib;p=pathlib.Path('state.json');s=json.loads(p.read_text('utf-8')) if p.exists() else {};s.pop('last_dismissed_date',None);s.pop('last_notified_date',None);p.write_text(json.dumps(s,ensure_ascii=False,indent=2),'utf-8')"

REM 启动托盘(常驻); 结束请用托盘右键 - 退出
start "" "%PYEXE%" tray.py --mock
echo 已启动, 看右下角托盘图标。结束请右键图标选"退出"。
timeout /t 3 >nul
