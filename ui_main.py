"""主窗口（白色主题）：识别 Steam 账户，自适应居中分页显示卡片，右键头像快捷菜单。"""

import os
import time
from math import ceil

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QMainWindow, QMenu, QMessageBox, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from settings import Settings, default_backup_dir
from steam import avatar_path as steam_avatar_path
from steam import Account, detect_steam_path, find_csgo_cfg_dir, load_accounts
from ui_common import (ClickableLabel, avatar_for, load_app_icon, open_path,
                       open_url)
from ui_dialogs import SettingsDialog
from ui_user import UserWindow
from workers import AvatarWorker

CARD_W = 200
GAP = 16


class UserCard(QFrame):
    clicked = Signal(object)
    context_menu = Signal(object)

    def __init__(self, account, avatar, parent=None):
        super().__init__(parent)
        self.account = account
        self.setObjectName('card')
        self.setFixedSize(CARD_W, 236)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip('单击进入备份管理 · 右键头像快捷菜单')
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 16, 12, 12)
        v.setSpacing(4)

        self.avatar_label = ClickableLabel()
        self.avatar_label.setFixedSize(96, 96)
        self.avatar_label.setPixmap(avatar)
        self.avatar_label.setAlignment(Qt.AlignCenter)
        self.avatar_label.setCursor(Qt.PointingHandCursor)
        self.avatar_label.setToolTip('右键：打开 Steam 主页 / 730 文件夹 / cfg 文件夹')
        self.avatar_label.clicked.connect(lambda: self.clicked.emit(self.account))
        self.avatar_label.context_menu.connect(lambda: self.context_menu.emit(self.account))

        name = QLabel(account.display_name)
        name.setAlignment(Qt.AlignCenter)
        name.setWordWrap(True)
        name.setStyleSheet('font-size:15px; font-weight:bold;')
        id_lbl = QLabel(f'🆔 {account.account_id or "-"}')
        id_lbl.setAlignment(Qt.AlignCenter)
        id_lbl.setStyleSheet('color:#6b7280; font-size:12px;')

        if getattr(account, 'not_found', False):
            status = QLabel('<span style="color:#dc2626; font-weight:600;">未发现</span>')
            self.setToolTip('该账户已在别处备份，但当前电脑未检测到（Steam 未登录此账户）')
        else:
            exists = account.has_730 and not account.is_730_empty()
            if exists:
                status = QLabel('📦 730：<span style="color:#16a34a; font-weight:600;">存在</span>')
            else:
                status = QLabel('📦 730：<span style="color:#dc2626; font-weight:600;">不存在</span>')
        status.setAlignment(Qt.AlignCenter)
        status.setTextFormat(Qt.RichText)
        status.setStyleSheet('font-size:12px;')

        # 显式水平居中，避免头像/文字偏移
        v.addWidget(self.avatar_label, 0, Qt.AlignHCenter)
        v.addWidget(name, 0, Qt.AlignHCenter)
        v.addWidget(id_lbl, 0, Qt.AlignHCenter)
        v.addWidget(status, 0, Qt.AlignHCenter)
        v.addStretch(1)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self.account)
        super().mousePressEvent(e)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = Settings()
        if not self.settings.get('backup_dir'):
            try:
                self.settings.set('backup_dir', default_backup_dir())
                self.settings.save()
            except Exception:
                pass
        self.accounts = []
        self.steam_path = None
        self.csgo_cfg_dir = None
        self.max_per_page = int(self.settings.get('max_per_page') or 6)
        self.page = 0
        self._user_windows = {}      # 账户key -> UserWindow（去重）
        self._open_cooldown = {}     # 账户key -> 上次打开时间戳
        self._avatar_workers = []
        self._avatar_fetched = set()

        self.setWindowTitle('CS2 配置备份工具')
        self.resize(1060, 720)
        ic = load_app_icon()
        if ic:
            self.setWindowIcon(ic)

        self._build_ui()

        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(150)
        self._resize_timer.timeout.connect(self._rebuild)

        self.refresh_accounts()

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 14, 16, 10)

        bar = QHBoxLayout()
        title = QLabel('🎮 CS2 配置备份工具')
        title.setStyleSheet('font-size:20px; font-weight:bold; color:#1f2430;')
        sub = QLabel('Steam 730 / CFG 备份 · 恢复 · AI 注释')
        sub.setStyleSheet('color:#6b7280; font-size:12px;')
        tcol = QVBoxLayout()
        tcol.setSpacing(0)
        tcol.addWidget(title)
        tcol.addWidget(sub)
        bar.addLayout(tcol)
        bar.addStretch(1)

        self.dir_lbl = QLabel('')
        self.dir_lbl.setStyleSheet('color:#6b7280; font-size:12px;')
        self.dir_lbl.setMaximumWidth(240)
        bar.addWidget(self.dir_lbl)
        btn_dir = QPushButton('📁 备份目录')
        btn_dir.clicked.connect(self._open_backup_dir)
        btn_set = QPushButton('⚙️ 设置')
        btn_set.clicked.connect(self._open_settings)
        btn_about = QPushButton('ℹ️ 关于')
        btn_about.clicked.connect(self._open_about)
        btn_refresh = QPushButton('🔄 刷新')
        btn_refresh.clicked.connect(self.refresh_accounts)
        bar.addWidget(btn_dir)
        bar.addWidget(btn_set)
        bar.addWidget(btn_about)
        bar.addWidget(btn_refresh)
        root.addLayout(bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.card_host = QWidget()
        self.grid = QGridLayout(self.card_host)
        self.grid.setContentsMargins(8, 8, 8, 8)
        self.grid.setHorizontalSpacing(GAP)
        self.grid.setVerticalSpacing(GAP)
        self.scroll.setWidget(self.card_host)
        root.addWidget(self.scroll, 1)

        # 分页导航
        nav = QHBoxLayout()
        self.btn_prev = QPushButton('◀ 上一页')
        self.btn_prev.clicked.connect(self._prev_page)
        self.lbl_page = QLabel('第 1 / 1 页')
        self.lbl_page.setAlignment(Qt.AlignCenter)
        self.lbl_page.setStyleSheet('color:#4b5563;')
        self.btn_next = QPushButton('下一页 ▶')
        self.btn_next.clicked.connect(self._next_page)
        nav.addStretch(1)
        nav.addWidget(self.btn_prev)
        nav.addWidget(self.lbl_page)
        nav.addWidget(self.btn_next)
        nav.addStretch(1)
        self.nav_widget = QWidget()
        self.nav_widget.setLayout(nav)
        root.addWidget(self.nav_widget)

        self.status = QLabel('')
        self.status.setWordWrap(True)
        self.status.setStyleSheet('color:#6b7280;')
        root.addWidget(self.status)

    # ------------------------------------------------------------- 账户
    def refresh_accounts(self):
        steam_path = self.settings.get('steam_path') or detect_steam_path()
        if steam_path and self.settings.get('steam_path') != steam_path:
            self.settings.set('steam_path', steam_path)
            self.settings.save()
        self.steam_path = steam_path
        self.csgo_cfg_dir = find_csgo_cfg_dir(steam_path) if steam_path else None
        self.accounts = []
        if steam_path and os.path.isdir(steam_path):
            try:
                self.accounts = load_accounts(steam_path)
            except Exception as e:
                self.status.setText(f'读取 Steam 账户失败: {e}')
        # 合并已备份但当前未检测到的账户（换机场景）
        known = self.settings.data.get('known_accounts') or {}
        if known:
            detected_ids = {a.account_id for a in self.accounts if a.account_id is not None}
            detected_sids = {a.steam_id64 for a in self.accounts if a.steam_id64}
            for _key, info in known.items():
                aid = info.get('account_id')
                sid = info.get('steam_id64') or ''
                if aid is not None and aid in detected_ids:
                    continue
                if sid and sid in detected_sids:
                    continue
                ghost = Account(account_name=info.get('account_name') or '',
                                persona_name=info.get('persona_name') or '',
                                steam_id64=sid or None,
                                avatar_hash=info.get('avatar_hash') or '',
                                userdata_dir=None)
                ghost.not_found = True
                self.accounts.append(ghost)
            self.accounts.sort(key=lambda a: a.display_name.lower())
        self.max_per_page = int(self.settings.get('max_per_page') or 6)
        self.page = 0
        self._rebuild()
        self._update_nav()
        self._update_status()
        self._kick_avatar_fetch()

    def _page_accounts(self):
        size = max(1, self.max_per_page)
        start = self.page * size
        return self.accounts[start:start + size]

    def _total_pages(self):
        size = max(1, self.max_per_page)
        return max(1, int(ceil(len(self.accounts) / size)))

    def _rebuild(self):
        while self.grid.count():
            it = self.grid.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
        for c in range(20):
            self.grid.setColumnStretch(c, 0)
            self.grid.setRowStretch(c, 0)

        page_accs = self._page_accounts()
        n = len(page_accs)
        if n == 0:
            hint = QLabel(
                '🎮 未检测到 Steam 用户账户\n\n'
                '请确认 Steam 已安装并至少登录过 1 个账户；\n'
                '也可以点击右上角「⚙️ 设置」手动指定 Steam 安装目录后点「🔄 刷新」。')
            hint.setAlignment(Qt.AlignCenter)
            hint.setStyleSheet('color:#6b7280; font-size:14px;')
            hint.setMinimumSize(420, 220)
            self.grid.addWidget(hint, 1, 1, Qt.AlignCenter)
            self.grid.setColumnStretch(0, 1)
            self.grid.setColumnStretch(2, 1)
            self.grid.setRowStretch(0, 1)
            self.grid.setRowStretch(2, 1)
            return

        avail = max(240, self.scroll.viewport().width() - 24)
        cols = int(avail // (CARD_W + GAP))
        cols = max(1, min(cols, n))
        rows = (n + cols - 1) // cols
        for i, acct in enumerate(page_accs):
            pm = avatar_for(acct, self.steam_path, 96)
            card = UserCard(acct, pm)
            card.clicked.connect(self._open_user)
            card.context_menu.connect(self._show_card_menu)
            r = i // cols + 1
            c = i % cols + 1
            self.grid.addWidget(card, r, c, Qt.AlignCenter)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(cols + 1, 1)
        self.grid.setRowStretch(0, 1)
        self.grid.setRowStretch(rows + 1, 1)

    def _update_nav(self):
        total = self._total_pages()
        self.nav_widget.setVisible(total > 1)
        self.lbl_page.setText(f'第 {self.page + 1} / {total} 页')
        self.btn_prev.setEnabled(self.page > 0)
        self.btn_next.setEnabled(self.page < total - 1)

    def _update_status(self):
        bdir = self.settings.get('backup_dir')
        short = os.path.basename(bdir) if bdir else '(未设置)'
        self.dir_lbl.setText(f'📁 备份目录：{short}')
        self.dir_lbl.setToolTip(bdir or '未设置备份目录')
        cfg = '✅' if self.csgo_cfg_dir else '❌'
        self.status.setText(
            f'🔍 Steam: {self.steam_path or "未找到"} · '
            f'👥 账户 {len(self.accounts)} 个 · '
            f'🎮 游戏cfg {cfg} · '
            f'每页最多 {self.max_per_page} 个 · 点击头像进入备份管理，右键头像打开快捷菜单')

    def _prev_page(self):
        if self.page > 0:
            self.page -= 1
            self._rebuild()
            self._update_nav()

    def _next_page(self):
        if self.page < self._total_pages() - 1:
            self.page += 1
            self._rebuild()
            self._update_nav()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._resize_timer.start()

    # --------------------------------------------------------- 头像抓取
    def _kick_avatar_fetch(self):
        proxy = self.settings.get('proxy') or ''
        for acct in self.accounts:
            if not acct.steam_id64 or acct.steam_id64 in self._avatar_fetched:
                continue
            if steam_avatar_path(self.steam_path, acct.avatar_hash, acct.steam_id64):
                continue
            self._avatar_fetched.add(acct.steam_id64)
            w = AvatarWorker(acct.steam_id64, proxy, self)

            def on_done(result, _w=w):
                sid, path = result
                if path:
                    self._rebuild()
                self._avatar_workers = [x for x in self._avatar_workers if x is not _w]
            w.done.connect(on_done)
            w.finished.connect(w.deleteLater)
            self._avatar_workers.append(w)
            w.start()

    # ------------------------------------------------------------ 动作
    @staticmethod
    def _account_key(account):
        if account.account_id is not None:
            return f'id:{account.account_id}'
        return f'sid:{account.steam_id64 or account.account_name or account.persona_name}'

    def _open_user(self, account):
        """打开用户窗口：带冷却 + 去重，已打开则置顶（不弹提示）。"""
        key = self._account_key(account)
        now = time.time()
        if key in self._open_cooldown and now - self._open_cooldown[key] < 0.5:
            return
        self._open_cooldown[key] = now
        win = self._user_windows.get(key)
        if win is not None and win.isVisible():
            win.raise_()
            win.activateWindow()
            return
        win = UserWindow(account, self.settings, self.accounts, self.csgo_cfg_dir)
        self._user_windows[key] = win
        win.setAttribute(Qt.WA_DeleteOnClose)
        win.destroyed.connect(lambda _=None, k=key: self._user_windows.pop(k, None))
        win.show()
        win.raise_()
        win.activateWindow()

    def _show_card_menu(self, account):
        m = QMenu(self)
        a1 = m.addAction('🌐 打开 Steam 主页')
        a2 = m.addAction('📦 打开 730 文件夹')
        a3 = m.addAction('📁 打开 cfg 文件夹')
        chosen = m.exec(QCursor.pos())
        if chosen == a1:
            if account.steam_id64:
                open_url(f'https://steamcommunity.com/profiles/{account.steam_id64}')
            else:
                QMessageBox.information(self, '提示', '该账户没有 SteamID，无法打开主页')
        elif chosen == a2:
            open_path(account.data730_dir, self)
        elif chosen == a3:
            open_path(self.csgo_cfg_dir, self)

    def _open_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec() == SettingsDialog.Accepted:
            self.refresh_accounts()

    def _open_about(self):
        from ui_about import AboutDialog
        dlg = AboutDialog(self.settings, self)
        dlg.exec()

    def _open_backup_dir(self):
        bdir = self.settings.get('backup_dir')
        if not bdir:
            QMessageBox.information(self, '提示', '尚未设置备份目录，请先在「⚙️ 设置」中指定。')
            return
        try:
            os.makedirs(bdir, exist_ok=True)
            os.startfile(bdir)
        except Exception as e:
            QMessageBox.warning(self, '无法打开', str(e))
