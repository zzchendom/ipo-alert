# -*- coding: utf-8 -*-
"""股票申购提醒 · 桌面透明浮窗 + 实际中签率回顾

启动行为:
  - 拉今日可申购新股 + 检查历史已申购但未"回顾"的中签率
  - 今日已点过/已忽略 -> 静默退出
  - 没今日新股 + 没待回顾 -> 静默退出
  - 否则 -> 屏幕右下角显示半透明浮窗,点击打开 HTML 报告并消失

state.json 字段:
  last_dismissed_date: 最后一次"已读"的日期
  tracked: { code: { ...info, reviewed: bool } } 追踪过的股票, reviewed=True 表示中签率已回顾过
"""
import datetime
import json
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

from PySide6 import QtCore, QtGui, QtWidgets

import fetcher
import report

STATE_FILE = ROOT / "state.json"
REPORT_FILE = ROOT / "report.html"

# tracked 中超过这个天数仍未出中签率的, 清理掉(发行失败或异常)
TRACK_TTL_DAYS = 30


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_state(s: dict) -> None:
    STATE_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def today_iso() -> str:
    return datetime.date.today().isoformat()


def _track_today(state: dict, todays: list) -> None:
    """把今日新股加入追踪 (若已存在则不覆盖)"""
    tracked = state.setdefault("tracked", {})
    for it in todays:
        code = it["code"]
        if code in tracked:
            continue
        tracked[code] = {
            "code": code,
            "name": it["name"],
            "market": it["market"],
            "apply_date": it["apply_date"],
            "result_date": it["result_date"],
            "lot_size": it["lot_size"],
            "lot_amount": it["lot_amount"],
            "issue_price": it["issue_price"],
            "predicted": fetcher.expected_winrate(it),
            "actual_winrate": None,
            "actual_es_multiple": None,
            "reviewed": False,
            "first_seen_at": today_iso(),
        }


def _collect_reviews(state: dict, use_mock: bool = False) -> list:
    """检查 tracked 中未 reviewed 的, 返回那些已出中签率的(标记 reviewed=True)
    清理超过 TTL 仍未出中签率的"""
    tracked = state.setdefault("tracked", {})
    reviews = []
    today = datetime.date.today()
    drop = []

    for code, info in list(tracked.items()):
        if info.get("reviewed"):
            continue
        # 超过 TTL 还没回顾的, 弃用
        try:
            seen = datetime.date.fromisoformat(info.get("first_seen_at", today_iso()))
            if (today - seen).days > TRACK_TTL_DAYS:
                drop.append(code)
                continue
        except ValueError:
            pass

        latest = None if use_mock else fetcher.fetch_one(code)
        # mock 模式下用 _mock_review 模拟
        if use_mock:
            latest = _mock_review_data(info)

        if not latest:
            continue
        aw = latest.get("actual_winrate")
        if not aw:  # 还没出
            continue
        info["actual_winrate"] = aw
        info["actual_es_multiple"] = latest.get("actual_es_multiple")
        info["reviewed"] = True
        reviews.append(info)

    for code in drop:
        tracked.pop(code, None)
    return reviews


def _mock_review_data(info: dict) -> dict:
    """mock 模式: 给 tracked 里第一只虚构出中签率"""
    return {
        "actual_winrate": 0.0298,
        "actual_es_multiple": 3355.7,
    }


class Floater(QtWidgets.QWidget):
    WIDTH = 260
    HEIGHT = 80

    def __init__(self, todays: list, reviews: list, state: dict):
        super().__init__()
        self.todays = todays
        self.reviews = reviews
        self.state = state
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setWindowTitle("新股申购")
        self.resize(self.WIDTH, self.HEIGHT)

        # 重要程度
        hot, must = 0, 0
        for it in todays:
            tag = fetcher.must_apply_tag(fetcher.estimate_profit(it)["mid"])
            if tag == "重点关注":
                hot += 1; must += 1
            elif tag == "建议必申":
                must += 1

        # 颜色
        if hot:
            self._bg = QtGui.QColor(192, 57, 43, 225)
        elif must:
            self._bg = QtGui.QColor(41, 128, 185, 215)
        elif todays:
            self._bg = QtGui.QColor(50, 55, 65, 195)
        else:  # 只有回顾
            self._bg = QtGui.QColor(102, 51, 153, 210)

        # 文案
        if todays and reviews:
            self._title = f"今日 {len(todays)} 只可申购"
            self._sub = f"+ 回顾 {len(reviews)} 只中签率 · 点击查看"
        elif todays:
            self._title = f"今日 {len(todays)} 只新股可申购"
            if hot:
                self._sub = f"🔥 {hot} 只大肉签 · 点击查看"
            elif must:
                self._sub = f"✅ {must} 只建议必申 · 点击查看"
            else:
                self._sub = "点击查看详情"
        else:  # 只有回顾
            self._title = f"📊 {len(reviews)} 只新股中签率已出"
            self._sub = "点击查看回顾"

        screen = QtGui.QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.WIDTH - 24, screen.bottom() - self.HEIGHT - 60)

        self._drag_pos = None
        self._press_pos = None
        self._hover = False
        self.setMouseTracking(True)

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect().adjusted(2, 2, -2, -2)

        bg = QtGui.QColor(self._bg)
        if self._hover:
            bg.setAlpha(min(255, bg.alpha() + 25))
        p.setBrush(bg)
        p.setPen(QtCore.Qt.NoPen)
        p.drawRoundedRect(rect, 14, 14)

        grad = QtGui.QLinearGradient(0, 0, 0, rect.height())
        grad.setColorAt(0, QtGui.QColor(255, 255, 255, 40))
        grad.setColorAt(0.5, QtGui.QColor(255, 255, 255, 0))
        p.setBrush(grad)
        p.drawRoundedRect(rect, 14, 14)

        p.setPen(QtGui.QColor(255, 255, 255))
        p.setFont(QtGui.QFont("Microsoft YaHei", 11, QtGui.QFont.Bold))
        p.drawText(rect.adjusted(16, 12, -16, 0), QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop, self._title)

        p.setPen(QtGui.QColor(255, 255, 255, 230))
        p.setFont(QtGui.QFont("Microsoft YaHei", 9))
        p.drawText(rect.adjusted(16, 40, -16, -8), QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop, self._sub)

    def enterEvent(self, _):
        self._hover = True
        self.update()

    def leaveEvent(self, _):
        self._hover = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._press_pos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e):
        if self._drag_pos and (e.buttons() & QtCore.Qt.LeftButton):
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton and self._drag_pos:
            moved = (e.globalPosition().toPoint() - self._press_pos).manhattanLength()
            self._drag_pos = None
            if moved < 6:
                self._open_report()

    def contextMenuEvent(self, e):
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet("QMenu{background:#222;color:#eee;border:1px solid #444;padding:4px}"
                           "QMenu::item{padding:6px 18px}QMenu::item:selected{background:#3a7bd5}")
        a_open = menu.addAction("查看报告")
        a_dismiss = menu.addAction("今日不再提醒")
        menu.addSeparator()
        a_quit = menu.addAction("退出（不标记已读）")
        action = menu.exec(e.globalPos())
        if action == a_open:
            self._open_report()
        elif action == a_dismiss:
            self._dismiss()
        elif action == a_quit:
            QtWidgets.QApplication.quit()

    def _open_report(self):
        report.build(self.todays, self.reviews, REPORT_FILE)
        webbrowser.open(REPORT_FILE.as_uri())
        self._dismiss()

    def _dismiss(self):
        self.state["last_dismissed_date"] = today_iso()
        save_state(self.state)
        QtWidgets.QApplication.quit()


def main():
    use_mock = "--mock" in sys.argv
    force = "--force" in sys.argv

    state = load_state()
    if not force and state.get("last_dismissed_date") == today_iso():
        return

    todays = fetcher.mock_today() if use_mock else fetcher.fetch_today()
    _track_today(state, todays)
    reviews = _collect_reviews(state, use_mock=use_mock)

    if not todays and not reviews:
        save_state(state)  # 持久化 tracked 中可能的 TTL 清理
        return

    save_state(state)  # 立即落盘 (即使用户不点击,reviews 也不会重复出现)

    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    f = Floater(todays, reviews, state)
    f.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
