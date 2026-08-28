"""关于对话框：作者信息 + B 站头像/粉丝数自动获取 + 一键直达 B 站主页。"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout)

import bilibili
from ui_common import (ClickableLabel, circular_pixmap, default_avatar,
                       load_app_icon, open_url)
from workers import BilibiliWorker

APP_VERSION = '1.3.0'


class AboutDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._worker = None
        self.setWindowTitle('ℹ️ 关于')
        self.setFixedWidth(430)
        ic = load_app_icon()
        if ic:
            self.setWindowIcon(ic)

        v = QVBoxLayout(self)
        v.setContentsMargins(28, 26, 28, 22)
        v.setSpacing(10)

        # 图标 + 名称 + 版本
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(72, 72)
        icon_lbl.setAlignment(Qt.AlignCenter)
        if ic:
            icon_lbl.setPixmap(ic.pixmap(72, 72))
        v.addWidget(icon_lbl, alignment=Qt.AlignHCenter)

        title = QLabel('🎮 CS2 配置备份工具')
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet('font-size:19px; font-weight:bold;')
        v.addWidget(title)

        ver = QLabel(f'版本 v{APP_VERSION}')
        ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet('color:#6b7280; font-size:12px;')
        v.addWidget(ver)

        author = QLabel('👤 作者：Chen_yang_ ｜ Deepseek V4 Pro Vibe Coding')
        author.setAlignment(Qt.AlignCenter)
        author.setWordWrap(True)
        author.setStyleSheet('color:#374151; font-size:13px;')
        v.addWidget(author)

        # B 站卡片
        card = QHBoxLayout()
        self.bili_avatar = ClickableLabel()
        self.bili_avatar.setFixedSize(56, 56)
        self.bili_avatar.setAlignment(Qt.AlignCenter)
        self.bili_avatar.setCursor(Qt.PointingHandCursor)
        self.bili_avatar.setPixmap(default_avatar('B', 56))
        self.bili_avatar.setToolTip('打开 B 站主页')
        self.bili_avatar.clicked.connect(lambda: open_url(bilibili.BILI_HOME))
        card.addWidget(self.bili_avatar)

        bcol = QVBoxLayout()
        bcol.setSpacing(2)
        self.bili_name = QLabel('正在获取 B 站信息…')
        self.bili_name.setStyleSheet('font-weight:bold;')
        bcol.addWidget(self.bili_name)
        self.bili_fans = QLabel('')
        self.bili_fans.setStyleSheet('color:#6b7280; font-size:12px;')
        bcol.addWidget(self.bili_fans)
        card.addLayout(bcol, 1)
        v.addLayout(card)

        btn_bili = QPushButton('🌐 打开 B 站主页')
        btn_bili.clicked.connect(lambda: open_url(bilibili.BILI_HOME))
        v.addWidget(btn_bili)

        btn_close = QPushButton('关闭')
        btn_close.clicked.connect(self.accept)
        v.addWidget(btn_close)

        self._start_fetch()

    def _start_fetch(self):
        proxy = self.settings.get('proxy') or ''
        w = BilibiliWorker(proxy, self)

        def on_done(info):
            self.bili_name.setText(f'{info.get("name") or "Chen_yang_LT"}  (Lv.{info.get("level", 0)})')
            self.bili_fans.setText(f'👥 粉丝：{info.get("fans", 0)}')
            p = info.get('avatar_path')
            if p:
                pm = circular_pixmap(QPixmap(p), 56)
                if pm:
                    self.bili_avatar.setPixmap(pm)
        def on_failed(msg):
            self.bili_name.setText('Chen_yang_LT')
            self.bili_fans.setText('获取粉丝数失败（可点下方按钮直达 B 站）')
        w.done.connect(on_done)
        w.failed.connect(on_failed)
        self._worker = w
        w.finished.connect(w.deleteLater)
        w.start()
