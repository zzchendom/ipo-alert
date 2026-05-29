# -*- coding: utf-8 -*-
"""股票申购提醒 · 系统托盘常驻版

相比 main.py 的"开机弹一次"模式, 本版常驻系统托盘:
  - 内部定时器每 CHECK_INTERVAL_MIN 分钟自动检查一次
    -> 不依赖重启电脑, 根治"忘了关机第二天就没提醒"
  - 左键点击托盘图标 = 随时手动查看今日报告 (你的"小按钮")
  - 桌面保持干净, 投屏时只有右下角一个不起眼的小图标

提示方式 notify_mode (存 state.json, 右键菜单可切换):
  "icon"    : 仅托盘图标变色 + 加红点 (默认, 最克制, 投屏无干扰)
  "float"   : 有新股时弹一次半透明浮窗 (沿用 main.Floater)
  "balloon" : 系统气泡通知, 几秒后自动消失

自动提示每天只触发一次 (last_notified_date); 但图标颜色实时反映状态,
左键随时可点开报告。
"""
import datetime
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

from PySide6 import QtCore, QtGui, QtWidgets

import fetcher
import report
import main as core  # 复用 load_state/save_state/today_iso/_track_today/_collect_reviews/Floater

REPORT_FILE = ROOT / "report.html"

# 每天定时复查的时刻(打新名单开盘前就定了, 早上看一眼即可)。
# 启动时立刻查一次, 之后每天 CHECK_HOUR:CHECK_MIN 再查一次。
# 该定时器在睡眠时暂停、唤醒后立即补触发 -> 冷开机/睡眠唤醒都能在你坐下时就绪。
CHECK_HOUR = 9
CHECK_MIN = 0

NOTIFY_MODES = ("icon", "float", "balloon")
NOTIFY_LABELS = {
    "icon": "图标变色 (最克制 · 推荐)",
    "float": "弹半透明浮窗",
    "balloon": "系统气泡通知",
}


# ---------------- 图标绘制 ----------------
def _make_icon(level: str) -> QtGui.QIcon:
    """按状态画一个圆角方块图标。
    level: idle / normal / must / hot / review
    """
    palette = {
        "idle":   QtGui.QColor(90, 98, 112),    # 灰蓝: 今日无可申购
        "normal": QtGui.QColor(60, 70, 90),     # 深: 普通新股
        "must":   QtGui.QColor(41, 128, 185),   # 蓝: 建议必申
        "hot":    QtGui.QColor(192, 57, 43),    # 红: 大肉签
        "review": QtGui.QColor(102, 51, 153),   # 紫: 仅中签率回顾
    }
    bg = palette.get(level, palette["idle"])

    px = QtGui.QPixmap(64, 64)
    px.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(px)
    p.setRenderHint(QtGui.QPainter.Antialiasing)

    p.setBrush(bg)
    p.setPen(QtCore.Qt.NoPen)
    p.drawRoundedRect(QtCore.QRectF(4, 4, 56, 56), 14, 14)

    # "申" 字
    p.setPen(QtGui.QColor(255, 255, 255))
    p.setFont(QtGui.QFont("Microsoft YaHei", 30, QtGui.QFont.Bold))
    p.drawText(QtCore.QRectF(4, 2, 56, 56), QtCore.Qt.AlignCenter, "申")

    # 有内容时右上角加一个亮点角标, 即使不弹窗也能一眼看出"今天有东西"
    if level in ("normal", "must", "hot", "review"):
        p.setBrush(QtGui.QColor(255, 209, 71))  # 金色角标
        p.setPen(QtGui.QPen(QtGui.QColor(20, 20, 24), 3))
        p.drawEllipse(QtCore.QRectF(40, 6, 18, 18))

    p.end()
    return QtGui.QIcon(px)


def _level_of(todays: list, reviews: list) -> str:
    if not todays and not reviews:
        return "idle"
    if not todays and reviews:
        return "review"
    hot = must = False
    for it in todays:
        tag = fetcher.must_apply_tag(fetcher.estimate_profit(it)["mid"])
        if tag == "重点关注":
            hot = True
        elif tag == "建议必申":
            must = True
    if hot:
        return "hot"
    if must:
        return "must"
    return "normal"


# ---------------- 后台拉取 worker ----------------
class Worker(QtCore.QObject):
    """在子线程做阻塞的网络请求, 完成后用信号把结果送回 GUI 线程。"""
    done = QtCore.Signal(list, list)  # todays, reviews

    def __init__(self, use_mock: bool):
        super().__init__()
        self.use_mock = use_mock

    def run(self):
        try:
            state = core.load_state()
            todays = fetcher.mock_today() if self.use_mock else fetcher.fetch_today()
            core._track_today(state, todays)
            reviews = core._collect_reviews(state, use_mock=self.use_mock)
            core.save_state(state)
        except Exception:
            todays, reviews = [], []
        self.done.emit(todays, reviews)


# ---------------- 托盘主体 ----------------
class TrayApp(QtCore.QObject):
    def __init__(self, app: QtWidgets.QApplication, use_mock: bool, force: bool = False):
        super().__init__()
        self.app = app
        self.use_mock = use_mock
        self.force = force
        self.todays: list = []
        self.reviews: list = []
        self._floater = None
        self._threads: list = []

        self.tray = QtWidgets.QSystemTrayIcon(_make_icon("idle"))
        self.tray.setToolTip("新股申购提醒 · 正在检查…")
        self.tray.activated.connect(self._on_activated)
        self._build_menu()
        self.tray.show()

        # 启动后稍候做首次检查 (让图标先出现), 再排程每天 CHECK_HOUR:CHECK_MIN 复查
        QtCore.QTimer.singleShot(1500, lambda: self.check(auto=True))
        self._schedule_daily()

    def _schedule_daily(self):
        """排程下一次每日复查 (单次定时器, 触发后自我续约)。"""
        now = datetime.datetime.now()
        target = now.replace(hour=CHECK_HOUR, minute=CHECK_MIN, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        ms = max(1000, int((target - now).total_seconds() * 1000))
        QtCore.QTimer.singleShot(ms, self._daily_tick)

    def _daily_tick(self):
        self.check(auto=True)
        self._schedule_daily()

    # ---- 菜单 ----
    def _build_menu(self):
        menu = QtWidgets.QMenu()
        self.act_view = menu.addAction("查看今日报告")
        self.act_view.triggered.connect(self.open_report)
        self.act_check = menu.addAction("立即检查")
        self.act_check.triggered.connect(lambda: self.check(auto=False))
        menu.addSeparator()

        mode_menu = menu.addMenu("提示方式")
        self._mode_group = QtGui.QActionGroup(self)
        self._mode_group.setExclusive(True)
        cur = self._notify_mode()
        for m in NOTIFY_MODES:
            a = mode_menu.addAction(NOTIFY_LABELS[m])
            a.setCheckable(True)
            a.setChecked(m == cur)
            a.setData(m)
            self._mode_group.addAction(a)
        self._mode_group.triggered.connect(self._on_mode_changed)

        self.act_dismiss = menu.addAction("今天不再主动弹窗")
        self.act_dismiss.triggered.connect(self._dismiss_today)
        menu.addSeparator()
        act_quit = menu.addAction("退出")
        act_quit.triggered.connect(self.app.quit)

        self.tray.setContextMenu(menu)

    def _notify_mode(self) -> str:
        m = core.load_state().get("notify_mode", "icon")
        return m if m in NOTIFY_MODES else "icon"

    def _on_mode_changed(self, action: QtGui.QAction):
        m = action.data()
        state = core.load_state()
        state["notify_mode"] = m
        core.save_state(state)
        self.tray.showMessage("提示方式已切换", NOTIFY_LABELS[m],
                              QtWidgets.QSystemTrayIcon.Information, 2500)

    # ---- 交互 ----
    def _on_activated(self, reason):
        # 左键单击 / 双击 -> 打开报告
        if reason in (QtWidgets.QSystemTrayIcon.Trigger,
                      QtWidgets.QSystemTrayIcon.DoubleClick):
            self.open_report()

    def check(self, auto: bool):
        # 今天已经看过(图标已消失): 自动检查不再拉数据, 保持隐藏, 等明天自动复出
        if auto and not self.force:
            if core.load_state().get("last_dismissed_date") == core.today_iso():
                if self.tray.isVisible():
                    self.tray.hide()
                return
        worker = Worker(self.use_mock)
        thread = QtCore.QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.done.connect(lambda t, r: self._on_checked(t, r, auto))
        worker.done.connect(thread.quit)
        thread.finished.connect(lambda: self._threads.remove((thread, worker))
                                if (thread, worker) in self._threads else None)
        self._threads.append((thread, worker))
        thread.start()

    def _on_checked(self, todays: list, reviews: list, auto: bool):
        self.todays = todays
        self.reviews = reviews
        state = core.load_state()

        # 今天已看过 -> 隐藏图标(进程后台常驻), 第二天 today 变化后自动复出
        if not self.force and state.get("last_dismissed_date") == core.today_iso():
            if self.tray.isVisible():
                self.tray.hide()
            return

        level = _level_of(todays, reviews)
        self.tray.setIcon(_make_icon(level))
        self.tray.setToolTip(self._tooltip(todays, reviews))
        self.act_view.setEnabled(bool(todays or reviews))
        if not self.tray.isVisible():
            self.tray.show()

        if not (todays or reviews):
            return
        if auto:
            # 自动检查: 每天只主动提示一次 (--force 测试时绕过闸门)
            if not self.force and state.get("last_notified_date") == core.today_iso():
                return
            state["last_notified_date"] = core.today_iso()
            core.save_state(state)
        # 手动"立即检查"则每次都按当前方式演示一次
        self._notify(self._notify_mode())

    def _tooltip(self, todays: list, reviews: list) -> str:
        if not todays and not reviews:
            return "新股申购提醒 · 今日无可申购"
        parts = []
        if todays:
            parts.append(f"今日 {len(todays)} 只可申购")
        if reviews:
            parts.append(f"{len(reviews)} 只中签率已出")
        return "新股申购 · " + " · ".join(parts) + "（点击查看）"

    def _notify(self, mode: str):
        if mode == "float":
            self._show_floater()
        elif mode == "balloon":
            self.tray.showMessage("新股申购提醒",
                                  self._tooltip(self.todays, self.reviews),
                                  QtWidgets.QSystemTrayIcon.Information, 6000)
        # mode == "icon": 图标已变色 + 角标, 不再额外打扰

    def _show_floater(self):
        if self._floater is not None:
            self._floater.close()
        # 复用 main.Floater; 它点击/右键会自行 quit, 这里改成只关闭浮窗不退出整个托盘
        state = core.load_state()
        f = core.Floater(self.todays, self.reviews, state)
        # 接管浮窗的"打开报告/已读"动作, 避免它把整个进程退出
        f._open_report = lambda: self._floater_open(f)
        f._dismiss = lambda: self._floater_dismiss(f)
        self._floater = f
        f.show()

    def _floater_open(self, f):
        self.open_report()
        self._floater_dismiss(f)

    def _floater_dismiss(self, f):
        state = core.load_state()
        state["last_dismissed_date"] = core.today_iso()
        core.save_state(state)
        f.close()
        if self._floater is f:
            self._floater = None

    def _dismiss_today(self):
        # 仅压制今天的自动提示(浮窗/气泡), 图标保留, 仍可随时左键点开
        state = core.load_state()
        state["last_notified_date"] = core.today_iso()
        core.save_state(state)
        if self._floater is not None:
            self._floater.close()
            self._floater = None
        self.tray.showMessage("新股申购提醒", "今天不再主动弹窗（图标仍在，可随时点开）",
                              QtWidgets.QSystemTrayIcon.Information, 2500)

    def open_report(self):
        # 有内容则打开报告; 无内容也算"今日已看", 提示一下
        if self.todays or self.reviews:
            report.build(self.todays, self.reviews, REPORT_FILE)
            webbrowser.open(REPORT_FILE.as_uri())
        else:
            self.tray.showMessage("新股申购提醒", "今日暂无可申购新股 / 待回顾中签率",
                                  QtWidgets.QSystemTrayIcon.Information, 3000)
        # 标记今日已看 -> 图标消失 (浏览器报告留着继续看); 进程后台常驻, 明天自动复出
        state = core.load_state()
        state["last_dismissed_date"] = core.today_iso()
        core.save_state(state)
        self._hide_icon()

    def _hide_icon(self):
        if self._floater is not None:
            self._floater.close()
            self._floater = None
        if not self.force:        # 测试(--force)时保持图标, 方便反复看效果
            self.tray.hide()


def run():
    use_mock = "--mock" in sys.argv
    force = "--force" in sys.argv

    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
        QtWidgets.QMessageBox.critical(None, "新股申购提醒", "当前系统没有可用的托盘区，无法常驻。")
        return

    tray = TrayApp(app, use_mock, force)  # noqa: F841 (持有引用防回收)
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
