"""公共 UI 组件：白色主题样式、可点击标签（含右键）、圆形头像、工具函数。"""

import os
import sys
import webbrowser

from PySide6.QtCore import QPointF, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton, QSizePolicy

from steam import avatar_path


def resource_path(rel):
    base = getattr(sys, '_MEIPASS', None)
    if not base:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel)


def load_app_icon():
    for cand in (resource_path('app.ico'),):
        if os.path.isfile(cand):
            try:
                return QIcon(cand)
            except Exception:
                pass
    return None


def open_path(path, parent=None):
    """用资源管理器打开目录，失败弹提示。"""
    if not path or not os.path.isdir(path):
        if parent:
            QMessageBox.information(parent, '提示', '目录不存在：' + str(path))
        return
    try:
        os.startfile(path)
    except Exception as e:
        if parent:
            QMessageBox.warning(parent, '无法打开', str(e))


def open_url(url):
    try:
        webbrowser.open(url)
    except Exception:
        pass


def make_button(text, primary=False, danger=False, min_width=None, min_height=34):
    """统一创建按钮：保证最小尺寸，避免表格单元格里被挤压/遮挡。"""
    b = QPushButton(text)
    if primary:
        b.setObjectName('primary')
    if danger:
        b.setObjectName('danger')
    b.setMinimumHeight(min_height)
    if min_width:
        b.setMinimumWidth(min_width)
    # 水平不拉伸，垂直按内容自适应（避免 emoji 被上下裁剪）
    b.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
    return b


class ClickableLabel(QLabel):
    clicked = Signal()
    context_menu = Signal()   # 右键

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)

    def contextMenuEvent(self, e):
        self.context_menu.emit()
        e.accept()


def circular_pixmap(pm, size):
    """把头像裁切为圆形。"""
    if pm is None or pm.isNull():
        return None
    pm = pm.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    pm = pm.copy((pm.width() - size) // 2, (pm.height() - size) // 2, size, size)
    out = QPixmap(size, size)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    p.setClipPath(path)
    p.drawPixmap(0, 0, pm)
    p.setClipping(False)
    p.setPen(QPen(QColor('#e4e7ec'), 2))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(1, 1, size - 2, size - 2)
    p.end()
    return out


def default_avatar(name, size=96):
    """无头像时的占位图：浅色圆 + 名称首字符。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor('#e8eefb'))
    p.setPen(Qt.NoPen)
    p.drawEllipse(0, 0, size, size)
    p.setPen(QColor('#2563eb'))
    f = QFont()
    f.setPixelSize(int(size * 0.42))
    f.setBold(True)
    p.setFont(f)
    ch = ((name or '?').strip()[:1] or '?').upper()
    p.drawText(pm.rect(), Qt.AlignCenter, ch)
    p.end()
    return pm


def avatar_for(account, steam_path, size=96):
    p = avatar_path(steam_path, account.avatar_hash, account.steam_id64) if steam_path else None
    if p:
        try:
            pm = QPixmap(p)
            if not pm.isNull():
                return circular_pixmap(pm, size)
        except Exception:
            pass
    return default_avatar(account.display_name, size)


def _ensure_check_icon():
    """生成/获取勾选框的对钩图标，返回用 / 分隔的绝对路径。"""
    path = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')),
                        'CS2BackupTool', 'check.png')
    if os.path.isfile(path):
        return path.replace('\\', '/')
    try:
        pm = QPixmap(18, 18)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor('#ffffff'), 2.6)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.drawPolyline([QPointF(4.5, 9.5), QPointF(7.8, 12.8), QPointF(13.5, 5.5)])
        p.end()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        pm.save(path, 'PNG')
    except Exception:
        pass
    return path.replace('\\', '/')


def get_stylesheet():
    """返回注入了勾选框对钩图标路径的样式表。"""
    return STYLESHEET_TEMPLATE.replace('__CHECK__', _ensure_check_icon())


STYLESHEET_TEMPLATE = '''
QWidget { font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI"; font-size: 13px; color: #1f2430; }
QMainWindow, QDialog { background: #f4f5f7; }
QLabel { background: transparent; color: #1f2430; }
QFrame#card { background: #ffffff; border: 1px solid #e4e7ec; border-radius: 16px; }
QFrame#card:hover { border: 1px solid #2563eb; background: #f8faff; }
QPushButton { background: #ffffff; border: 1px solid #d6dbe3; border-radius: 8px; padding: 6px 14px; color: #1f2430; min-height: 26px; }
QPushButton:hover { background: #f0f4ff; border-color: #2563eb; }
QPushButton:pressed { background: #e4ecfb; }
QPushButton:disabled { color: #a3aab6; background: #f0f1f4; border-color: #e4e7ec; }
QPushButton#primary { background: #2563eb; border-color: #2563eb; color: #ffffff; font-weight: 600; }
QPushButton#primary:hover { background: #1d4fd8; }
QPushButton#danger { background: #ffffff; border-color: #f3c1c1; color: #d64545; }
QPushButton#danger:hover { background: #fdeeee; border-color: #e04747; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: #ffffff; border: 1px solid #d6dbe3; border-radius: 8px; padding: 6px 10px; color: #1f2430; selection-background-color: #2563eb; min-height: 20px; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color: #2563eb; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: #ffffff; border: 1px solid #d6dbe3; selection-background-color: #e4ecfb; selection-color: #1f2430; color: #1f2430; }
QTableWidget { background: #ffffff; alternate-background-color: #f7f8fa; gridline-color: #eef0f4; border: 1px solid #e4e7ec; border-radius: 8px; color: #1f2430; }
QTableWidget::item { padding: 2px 6px; }
QHeaderView::section { background: #f4f5f7; color: #4b5563; border: none; border-bottom: 1px solid #e4e7ec; padding: 8px; font-weight: 600; }
QTabWidget::pane { border: 1px solid #e4e7ec; border-radius: 8px; top: -1px; background: #ffffff; }
QTabBar::tab { background: #eef0f4; color: #6b7280; padding: 8px 20px; border: 1px solid #e4e7ec; border-bottom: none; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 3px; }
QTabBar::tab:selected { background: #ffffff; color: #2563eb; border-bottom: 2px solid #2563eb; }
QProgressBar { background: #e9ecf1; border: 1px solid #d6dbe3; border-radius: 8px; text-align: center; color: #1f2430; }
QProgressBar::chunk { background: #2563eb; border-radius: 7px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; }
QScrollBar::handle:vertical { background: #c9cfd8; border-radius: 5px; min-height: 28px; }
QScrollBar:horizontal { background: transparent; height: 10px; }
QScrollBar::handle:horizontal { background: #c9cfd8; border-radius: 5px; min-width: 28px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QCheckBox { color: #1f2430; spacing: 8px; }
QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #c9cfd8; border-radius: 5px; background: #ffffff; }
QCheckBox::indicator:checked { background: #2563eb; border-color: #2563eb; image: url("__CHECK__"); }
QMessageBox { background: #ffffff; }
QGroupBox { color: #1f2430; border: 1px solid #e4e7ec; border-radius: 10px; margin-top: 14px; padding-top: 10px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
QToolTip { background: #1f2430; color: #ffffff; border: none; padding: 4px 8px; }
QTextEdit, QPlainTextEdit { background: #ffffff; border: 1px solid #d6dbe3; border-radius: 8px; color: #1f2430; }
QMenu { background: #ffffff; border: 1px solid #e4e7ec; padding: 4px; }
QMenu::item { padding: 7px 26px; border-radius: 6px; }
QMenu::item:selected { background: #e4ecfb; color: #2563eb; }
QStatusBar { background: #f4f5f7; color: #6b7280; }
QSplitter::handle { background: #e4e7ec; }
'''
