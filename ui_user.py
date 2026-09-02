"""单个用户的备份管理窗口：完整个人信息、备份 730 / 游戏 cfg、跨用户恢复、右侧 AI 注释面板。"""

import os
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox,
                               QComboBox, QFileDialog, QHBoxLayout, QHeaderView,
                               QLabel, QMessageBox, QProgressDialog, QPushButton,
                               QSplitter, QTabWidget, QTableWidget, QTableWidgetItem,
                               QTextEdit, QVBoxLayout, QWidget)

import ai as ai_mod
import ai_cache
import backup as bk
import logger as logutil
from ui_common import avatar_for, load_app_icon, make_button, open_path
from ui_dialogs import RestoreDialog
from workers import AIWorker, BackupWorker, GenerateWorker, RestoreWorker


class UserWindow(QWidget):
    def __init__(self, account, settings, accounts, csgo_cfg_dir, parent=None):
        super().__init__(parent)
        self.account = account
        self.settings = settings
        self.accounts = accounts
        self.csgo_cfg_dir = csgo_cfg_dir
        self._backup_worker = None
        self._restore_worker = None
        self._ai_worker = None
        self._gen_worker = None
        self._ai_saved_path = None
        self.backup_infos = []
        self._current_rows = []
        self.cfg_files = []   # (name, size, mtime, fullpath)
        self.setWindowTitle(f'{account.display_name} - 备份管理')
        self.resize(1240, 760)
        ic = load_app_icon()
        if ic:
            self.setWindowIcon(ic)
        self._build_ui()
        self.refresh_backups()
        self.refresh_cfg_files()

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)

        # 顶部：返回 + 标题
        bar = QHBoxLayout()
        btn_back = QPushButton('🏠 返回')
        btn_back.clicked.connect(self.close)
        bar.addWidget(btn_back)
        av = QLabel()
        av.setFixedSize(40, 40)
        av.setPixmap(avatar_for(self.account, self.settings.get('steam_path'), 40))
        bar.addWidget(av)
        title = QLabel(f'{self.account.display_name} 的备份管理')
        title.setStyleSheet('font-size:17px; font-weight:bold;')
        bar.addWidget(title)
        bar.addStretch(1)
        root.addLayout(bar)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(self._build_left())
        split.addWidget(self._build_middle())
        split.addWidget(self._build_ai_panel())
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setStretchFactor(2, 0)
        split.setSizes([300, 560, 360])
        root.addWidget(split, 1)

        if not self.account.has_730:
            self.btn_730.setEnabled(False)
            self.status.setText('⚠️ 未找到该用户的 730 数据目录，730 备份/恢复不可用。')

    def _build_left(self):
        left = QWidget()
        left.setMinimumWidth(300)
        left.setMaximumWidth(380)
        v = QVBoxLayout(left)
        v.setContentsMargins(4, 4, 4, 4)

        av = QLabel()
        av.setFixedSize(100, 100)
        av.setPixmap(avatar_for(self.account, self.settings.get('steam_path'), 100))
        av.setAlignment(Qt.AlignCenter)
        v.addWidget(av, alignment=Qt.AlignHCenter)

        name = QLabel(self.account.display_name)
        name.setAlignment(Qt.AlignCenter)
        name.setWordWrap(True)
        name.setStyleSheet('font-size:18px; font-weight:bold;')
        v.addWidget(name)

        info_lines = [
            f'👤 昵称：{self.account.display_name}',
            f'🔑 账号：{self.account.account_name or "—"}',
            f'🆔 账户ID：{self.account.account_id or "—"}',
            f'🌐 SteamID64：{self.account.steam_id64 or "—"}',
            f'📦 730 目录：{self.account.data730_dir or "—"}',
            f'📁 cfg 目录(游戏)：{self.csgo_cfg_dir or "未找到 CS2"}',
        ]
        for line in info_lines:
            lbl = QLabel(line)
            lbl.setWordWrap(True)
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            lbl.setStyleSheet('color:#374151; font-size:12px;')
            v.addWidget(lbl)

        self.btn_730 = QPushButton('📦 备份 730 全部数据')
        self.btn_730.setObjectName('primary')
        self.btn_730.clicked.connect(lambda: self._run_backup('730'))
        self.btn_cfg = QPushButton('📁 备份 CFG 配置')
        self.btn_cfg.setObjectName('primary')
        self.btn_cfg.clicked.connect(lambda: self._run_backup('cfg'))
        btn_open730 = QPushButton('📂 打开 730 目录')
        btn_open730.clicked.connect(lambda: open_path(self.account.data730_dir, self))
        btn_opencfg = QPushButton('📂 打开 cfg 目录')
        btn_opencfg.clicked.connect(lambda: open_path(self.csgo_cfg_dir, self))
        v.addWidget(self.btn_730)
        v.addWidget(self.btn_cfg)
        v.addWidget(btn_open730)
        v.addWidget(btn_opencfg)

        self.status = QLabel('')
        self.status.setWordWrap(True)
        self.status.setStyleSheet('color:#4b5563; font-size:12px;')
        v.addWidget(self.status)
        v.addStretch(1)
        return left

    def _build_middle(self):
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_backups_tab(), '📦 备份记录')
        self.tabs.addTab(self._build_cfg_tab(), '📁 CFG 文件')
        return self.tabs

    def _build_backups_tab(self):
        tab = QWidget()
        v = QVBoxLayout(tab)
        row = QHBoxLayout()
        self.chk_all = QCheckBox('显示所有用户的备份')
        self.chk_all.stateChanged.connect(lambda _: self._apply_filter())
        row.addWidget(self.chk_all)
        row.addWidget(QLabel('类型:'))
        self.cmb_type = QComboBox()
        self.cmb_type.addItem('全部类型', 'all')
        self.cmb_type.addItem('仅 730', '730')
        self.cmb_type.addItem('仅 CFG', 'cfg')
        self.cmb_type.currentIndexChanged.connect(lambda _: self._apply_filter())
        row.addWidget(self.cmb_type)
        row.addStretch(1)
        btn_restore = QPushButton('📥 恢复所选')
        btn_restore.setObjectName('primary')
        btn_restore.clicked.connect(self._restore_selected)
        btn_del = QPushButton('🗑 删除所选')
        btn_del.setObjectName('danger')
        btn_del.clicked.connect(self._delete_selected)
        btn_ref = QPushButton('🔄 刷新')
        btn_ref.clicked.connect(self.refresh_backups)
        row.addWidget(btn_restore)
        row.addWidget(btn_del)
        row.addWidget(btn_ref)
        v.addLayout(row)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(['类型', '原用户', '备注', '时间', '大小', '文件数', '操作'])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.table.setAlternatingRowColors(True)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setSectionResizeMode(6, QHeaderView.Stretch)   # 最右列填充剩余，避免拖动方向反向
        self.table.setColumnWidth(0, 110)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 200)
        self.table.setColumnWidth(3, 140)
        self.table.setColumnWidth(4, 80)
        self.table.setColumnWidth(5, 70)
        self.table.itemChanged.connect(self._on_note_edited)
        v.addWidget(self.table, 1)
        return tab

    def _build_cfg_tab(self):
        tab = QWidget()
        v = QVBoxLayout(tab)
        row = QHBoxLayout()
        row.addWidget(QLabel('🎮 游戏 cfg 目录（global）：'))
        self.cfg_dir_lbl = QLabel(self.csgo_cfg_dir or '未找到')
        self.cfg_dir_lbl.setStyleSheet('color:#2563eb;')
        self.cfg_dir_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(self.cfg_dir_lbl, 1)
        btn_open = QPushButton('📂 打开目录')
        btn_open.clicked.connect(lambda: open_path(self.csgo_cfg_dir, self))
        btn_ref = QPushButton('🔄 刷新')
        btn_ref.clicked.connect(self.refresh_cfg_files)
        row.addWidget(btn_open)
        row.addWidget(btn_ref)
        v.addLayout(row)

        self.cfg_table = QTableWidget(0, 4)
        self.cfg_table.setHorizontalHeaderLabels(['文件名', '大小', '修改时间', 'AI 注释'])
        self.cfg_table.verticalHeader().setVisible(False)
        self.cfg_table.verticalHeader().setDefaultSectionSize(48)
        self.cfg_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.cfg_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.cfg_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.cfg_table.setAlternatingRowColors(True)
        hh = self.cfg_table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)   # 最右列填充剩余，避免拖动方向反向
        self.cfg_table.setColumnWidth(0, 240)
        self.cfg_table.setColumnWidth(1, 80)
        self.cfg_table.setColumnWidth(2, 145)
        v.addWidget(self.cfg_table, 1)
        return tab

    def _build_ai_panel(self):
        panel = QWidget()
        panel.setMinimumWidth(340)
        panel.setMaximumWidth(460)
        v = QVBoxLayout(panel)
        v.setContentsMargins(4, 4, 4, 4)

        hdr = QHBoxLayout()
        title = QLabel('🤖 AI 助手')
        title.setStyleSheet('font-size:15px; font-weight:bold;')
        hdr.addWidget(title)
        hdr.addStretch(1)
        self.chk_expand = QCheckBox('📂 展开显示')
        self.chk_expand.setChecked(True)
        self.chk_expand.toggled.connect(self._toggle_ai_panel)
        hdr.addWidget(self.chk_expand)
        v.addLayout(hdr)

        selrow = QHBoxLayout()
        selrow.addWidget(QLabel('文件:'))
        self.cmb_cfg = QComboBox()
        self.cmb_cfg.currentIndexChanged.connect(self._on_cfg_selected)
        selrow.addWidget(self.cmb_cfg, 1)
        self.btn_ai = QPushButton('🤖 开始注释')
        self.btn_ai.setObjectName('primary')
        self.btn_ai.clicked.connect(self._run_ai)
        selrow.addWidget(self.btn_ai)
        v.addLayout(selrow)

        self.ai_text = QTextEdit()
        self.ai_text.setReadOnly(True)
        self.ai_text.setPlaceholderText('选择 cfg 文件后可查看原始内容；点击「开始注释」让 AI 逐行添加中文注释；也可在下方直接提问生成 cfg。')
        self.ai_text.setVisible(True)
        v.addWidget(self.ai_text, 1)

        srow = QHBoxLayout()
        self.btn_save = QPushButton('💾 保存')
        self.btn_save.clicked.connect(self._save_ai)
        self.btn_saveas = QPushButton('📄 另存为')
        self.btn_saveas.clicked.connect(self._save_as_ai)
        self.btn_copy = QPushButton('📋 复制')
        self.btn_copy.clicked.connect(self._copy_ai)
        srow.addWidget(self.btn_save)
        srow.addWidget(self.btn_saveas)
        srow.addWidget(self.btn_copy)
        v.addLayout(srow)

        chat_lbl = QLabel('💬 向 AI 提问，直接生成 cfg')
        chat_lbl.setStyleSheet('color:#6b7280; font-size:12px; margin-top:6px;')
        v.addWidget(chat_lbl)
        self.chat_input = QTextEdit()
        self.chat_input.setFixedHeight(72)
        self.chat_input.setPlaceholderText('例如：生成一个练枪 autoexec.cfg，含蹲跳绑定、灵敏度 2.5、一键清血迹')
        v.addWidget(self.chat_input)
        self.btn_generate = QPushButton('🤖 生成 cfg')
        self.btn_generate.setObjectName('primary')
        self.btn_generate.clicked.connect(self._generate_cfg)
        v.addWidget(self.btn_generate)
        return panel

    # ------------------------------------------------------------ 备份列表
    def _is_owner(self, info):
        aid = self.account.account_id
        if aid is not None and info.account_id is not None:
            try:
                if int(info.account_id) == int(aid):
                    return True
            except (TypeError, ValueError):
                pass
        if info.persona and info.persona == self.account.persona_name:
            return True
        if info.account_name and info.account_name == self.account.account_name:
            return True
        return False

    def refresh_backups(self):
        bdir = self.settings.get('backup_dir')
        self.backup_infos = bk.list_backups(bdir) if bdir else []
        self._apply_filter()

    def _apply_filter(self):
        rows = []
        for info in self.backup_infos:
            if not self.chk_all.isChecked() and not self._is_owner(info):
                continue
            t = self.cmb_type.currentData()
            if t != 'all' and info.btype != t:
                continue
            rows.append(info)
        self._current_rows = rows
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        for r, info in enumerate(rows):
            it_type = QTableWidgetItem(info.type_label)
            it_owner = QTableWidgetItem(info.owner_label)
            it_note = QTableWidgetItem(info.note or '暂无备注')
            it_note.setFlags(it_note.flags() | Qt.ItemIsEditable)
            if not info.note:
                it_note.setForeground(Qt.gray)
            it_time = QTableWidgetItem(info.created)
            it_size = QTableWidgetItem(bk._human_size(info.size))
            it_count = QTableWidgetItem(str(info.file_count))
            for it in (it_type, it_owner, it_time, it_size, it_count):
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(r, 0, it_type)
            self.table.setItem(r, 1, it_owner)
            self.table.setItem(r, 2, it_note)
            self.table.setItem(r, 3, it_time)
            self.table.setItem(r, 4, it_size)
            self.table.setItem(r, 5, it_count)
            cell = QWidget()
            hl = QHBoxLayout(cell)
            hl.setContentsMargins(4, 3, 4, 3)
            hl.setSpacing(6)
            b1 = make_button('恢复', primary=True, min_width=54)
            b1.clicked.connect(lambda checked=False, inf=info: self._restore(inf))
            b2 = make_button('删除', danger=True, min_width=54)
            b2.clicked.connect(lambda checked=False, inf=info: self._delete(inf))
            hl.addWidget(b1)
            hl.addWidget(b2)
            hl.addStretch(1)
            self.table.setCellWidget(r, 6, cell)
        self.table.blockSignals(False)

    def _on_note_edited(self, item):
        """备注列自由编辑：把新备注写回 zip 内的 manifest.json。"""
        if item.column() != 2:
            return
        r = item.row()
        if r < 0 or r >= len(self._current_rows):
            return
        info = self._current_rows[r]
        txt = (item.text() or '').strip()
        new_note = '' if txt in ('', '暂无备注') else txt
        if new_note == info.note:
            return
        try:
            bk.update_note(info.path, new_note)
            info.note = new_note
        except bk.BackupError as e:
            QMessageBox.warning(self, '更新备注失败', str(e))
        self.table.blockSignals(True)
        try:
            if not new_note:
                item.setText('暂无备注')
                item.setForeground(Qt.gray)
            else:
                item.setForeground(Qt.black)
        finally:
            self.table.blockSignals(False)

    # -------------------------------------------------------------- 备份
    def _run_backup(self, btype):
        if self._backup_worker is not None and self._backup_worker.isRunning():
            QMessageBox.information(self, '提示', '已有备份任务进行中')
            return
        bdir = self.settings.get('backup_dir')
        if not bdir:
            QMessageBox.warning(self, '提示', '尚未设置备份目录，请先在主界面「⚙️ 设置」中指定。')
            return
        compress = int(self.settings.get('zip_compress') or 6)
        if btype == '730':
            src = self.account.data730_dir
            label = '730 全部数据'
            if not src or not os.path.isdir(src):
                QMessageBox.warning(self, '提示', '未找到该用户的 730 数据目录。')
                return
        else:
            src = self.csgo_cfg_dir
            label = 'CFG 配置（游戏 csgo\\cfg）'
            if not src or not os.path.isdir(src):
                QMessageBox.warning(self, '提示', '未找到 CS2 游戏 cfg 目录（steamapps\\common\\Counter-Strike Global Offensive\\game\\csgo\\cfg）。')
                return

        worker = BackupWorker(src, bdir, btype, self.account.persona_name,
                              self.account.account_name, self.account.account_id,
                              None, compress, self)
        dlg = QProgressDialog(f'正在备份 {label}…', '取消', 0, 100, self)
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)

        def on_progress(cur, total, name):
            if total > 0:
                dlg.setMaximum(total)
                dlg.setValue(cur)
            dlg.setLabelText(f'正在备份 {label}（{cur}/{total}）\n{name}')

        def on_done(info):
            dlg.close()
            self._backup_worker = None
            self.settings.remember_account(self.account)
            self.status.setText(
                f'✅ 备份完成\n📦 文件: {os.path.basename(info.path)}\n'
                f'🕒 时间: {info.created}\n📏 大小: {bk._human_size(info.size)} · 文件数: {info.file_count}')
            self.refresh_backups()

        def on_failed(msg):
            dlg.close()
            self._backup_worker = None
            if msg.startswith('已取消'):
                return
            QMessageBox.warning(self, '备份失败', msg)

        def on_canceled():
            worker.cancel()

        worker.progress.connect(on_progress)
        worker.done.connect(on_done)
        worker.failed.connect(on_failed)
        dlg.canceled.connect(on_canceled)
        self._backup_worker = worker
        worker.finished.connect(worker.deleteLater)
        worker.start()

    # -------------------------------------------------------------- 恢复
    def _restore_selected(self):
        r = self.table.currentRow()
        if r < 0 or r >= len(self._current_rows):
            QMessageBox.information(self, '提示', '请先在列表中选择一个备份')
            return
        self._restore(self._current_rows[r])

    def _restore(self, info):
        if self._restore_worker is not None and self._restore_worker.isRunning():
            QMessageBox.information(self, '提示', '已有恢复任务进行中')
            return
        dlg = RestoreDialog(self, info, self.accounts, self.account, self.csgo_cfg_dir)
        if dlg.exec() != RestoreDialog.Accepted:
            return
        if info.btype == '730':
            target = dlg.target_account
            dest = target.data730_dir
            auto_meta = {'persona': target.persona_name, 'account_name': target.account_name,
                         'account_id': target.account_id}
            target_label = target.display_name
        else:
            dest = self.csgo_cfg_dir
            auto_meta = {'persona': '游戏全局cfg', 'account_name': self.account.account_name,
                         'account_id': None}
            target_label = '游戏 cfg 目录'
        self._run_restore(info, dest, dlg.backup_existing, auto_meta, target_label)

    def _run_restore(self, info, dest, backup_existing, auto_meta, target_label):
        if not dest or not os.path.isdir(os.path.dirname(dest)):
            QMessageBox.warning(self, '提示', '目标目录无效，无法恢复。')
            return
        compress = int(self.settings.get('zip_compress') or 6)
        worker = RestoreWorker(info, dest, self.settings.get('backup_dir'),
                               backup_existing, auto_meta, compress, self)
        dlg = QProgressDialog('正在恢复…', '取消', 0, 100, self)
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)

        def on_progress(cur, total, name):
            if total > 0:
                dlg.setMaximum(total)
                dlg.setValue(cur)
            dlg.setLabelText(f'正在恢复（{cur}/{total}）\n{name}')

        def on_done(result):
            dlg.close()
            self._restore_worker = None
            dest_dir, auto_info = result
            msg = f'✅ 已将「{info.type_label}」恢复到「{target_label}」\n\n📂 目标: {dest_dir}\n'
            if auto_info:
                msg += (f'\n🛡️ 已自动备份恢复前的现有配置:\n'
                        f'{os.path.basename(auto_info.path)}\n'
                        f'（来源: {auto_info.persona}）')
            QMessageBox.information(self, '恢复完成', msg)
            self.refresh_backups()

        def on_failed(msg):
            dlg.close()
            self._restore_worker = None
            if msg.startswith('已取消'):
                return
            QMessageBox.warning(self, '恢复失败', msg)

        def on_canceled():
            worker.cancel()

        worker.progress.connect(on_progress)
        worker.done.connect(on_done)
        worker.failed.connect(on_failed)
        dlg.canceled.connect(on_canceled)
        self._restore_worker = worker
        worker.finished.connect(worker.deleteLater)
        worker.start()

    # -------------------------------------------------------------- 删除
    def _delete_selected(self):
        r = self.table.currentRow()
        if 0 <= r < len(self._current_rows):
            self._delete(self._current_rows[r])

    def _delete(self, info):
        ret = QMessageBox.question(
            self, '确认删除',
            f'确定要删除这个备份文件吗？\n{os.path.basename(info.path)}',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        try:
            os.remove(info.path)
            self.refresh_backups()
        except Exception as e:
            QMessageBox.warning(self, '删除失败', str(e))

    # ----------------------------------------------------------- CFG 文件
    def refresh_cfg_files(self):
        cfg = self.csgo_cfg_dir
        files = []
        if cfg and os.path.isdir(cfg):
            for fn in sorted(os.listdir(cfg)):
                fp = os.path.join(cfg, fn)
                if not os.path.isfile(fp):
                    continue
                try:
                    st = os.stat(fp)
                except OSError:
                    continue
                files.append((fn, st.st_size,
                              time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime)),
                              fp))
        self.cfg_files = files
        self.cfg_table.setRowCount(len(files))
        for r, (fn, size, mtime, fp) in enumerate(files):
            self.cfg_table.setItem(r, 0, QTableWidgetItem(fn))
            self.cfg_table.setItem(r, 1, QTableWidgetItem(bk._human_size(size)))
            self.cfg_table.setItem(r, 2, QTableWidgetItem(mtime))
            cell = QWidget()
            hl = QHBoxLayout(cell)
            hl.setContentsMargins(4, 3, 4, 3)
            b = make_button('🤖 AI 注释', primary=True, min_width=92)
            b.clicked.connect(lambda checked=False, f=fp: self._annotate_from_list(f))
            hl.addWidget(b)
            hl.addStretch(1)
            self.cfg_table.setCellWidget(r, 3, cell)
        if not files:
            self.cfg_table.setRowCount(1)
            self.cfg_table.setItem(0, 0, QTableWidgetItem('（未找到 cfg 文件）'))
        self._populate_ai_combo()

    def _populate_ai_combo(self):
        self.cmb_cfg.blockSignals(True)
        self.cmb_cfg.clear()
        for fn, _, _, _ in self.cfg_files:
            self.cmb_cfg.addItem(fn)
        self.cmb_cfg.blockSignals(False)
        if self.cfg_files:
            self.cmb_cfg.setCurrentIndex(0)
        self._on_cfg_selected(self.cmb_cfg.currentIndex())

    # ------------------------------------------------------------- AI 注释
    def _toggle_ai_panel(self, checked):
        self.ai_text.setVisible(checked)

    def _on_cfg_selected(self, idx):
        if 0 <= idx < len(self.cfg_files):
            fp = self.cfg_files[idx][3]
            try:
                with open(fp, 'r', encoding='utf-8', errors='replace') as f:
                    self.ai_text.setPlainText(f.read())
            except Exception as e:
                self.ai_text.setPlainText('读取失败: ' + str(e))
            self._ai_saved_path = None
        else:
            self.ai_text.clear()

    def _select_cfg_in_combo(self, file_path):
        for i, (_, _, _, fp) in enumerate(self.cfg_files):
            if fp == file_path:
                self.cmb_cfg.setCurrentIndex(i)
                return

    def _annotate_from_list(self, file_path):
        self._select_cfg_in_combo(file_path)
        self.chk_expand.setChecked(True)
        self._run_ai(file_path)

    def _run_ai(self, file_path=None):
        if file_path is None:
            idx = self.cmb_cfg.currentIndex()
            if idx < 0 or idx >= len(self.cfg_files):
                QMessageBox.information(self, '提示', '请先选择一个 cfg 文件')
                return
            file_path = self.cfg_files[idx][3]
        ai = self.settings.data.get('ai', {})
        if not ai.get('enabled', True):
            QMessageBox.information(self, '提示', 'AI 注释功能未启用，请在「⚙️ 设置」中开启并填写 API Key。')
            return
        if not (ai.get('api_key') or '').strip():
            QMessageBox.information(self, '提示', '未配置 API Key，请在「⚙️ 设置 → AI 注释」中填写。')
            return
        try:
            busy = self._ai_worker is not None and self._ai_worker.isRunning()
        except RuntimeError:
            busy = False
            self._ai_worker = None
        if busy:
            QMessageBox.information(self, '提示', 'AI 注释任务进行中，请稍候')
            return
        # 命中本地缓存则直接复用，节约 token
        cached = ai_cache.get_cached(file_path)
        if cached:
            self.ai_text.setPlainText(cached)
            self.chk_expand.setChecked(True)
            self.status.setText('📦 命中本地缓存（cfg 文件未变更，未消耗 token）')
            return
        # 在主线程读取文件内容（带重试、二进制方式），避免线程中读文件偶发「句柄无效」
        try:
            content = ai_mod.read_cfg_text(file_path)
        except Exception as e:
            logutil.get_logger().error('读取 cfg 失败: %s -> %s', file_path, e)
            self.ai_text.setPlainText(f'❌ 读取文件失败：\n{file_path}\n\n{e}\n\n（若持续失败，请关闭 CS2 / Steam 后重试）')
            return
        filename = os.path.basename(file_path)
        cfg = dict(ai)
        cfg['proxy'] = self.settings.get('proxy') or ''
        self.ai_text.setPlainText('🤖 正在请求 AI 逐行注释，请稍候…\n（根据文件大小与网络，通常需要几秒到几十秒）')
        self.chk_expand.setChecked(True)
        self._set_ai_busy(True)
        w = AIWorker(cfg, content, filename, self)

        def on_done(text):
            self._ai_worker = None
            ai_cache.put_cached(file_path, text)
            self.ai_text.setPlainText(text)
            self._set_ai_busy(False)
            self.status.setText('✅ AI 注释完成，可在右侧查看，并可 💾 保存 / 📄 另存为。')
        def on_failed(msg):
            self._ai_worker = None
            self.ai_text.setPlainText('❌ 注释失败：\n' + msg)
            self._set_ai_busy(False)
        w.done.connect(on_done)
        w.failed.connect(on_failed)
        self._ai_worker = w
        w.finished.connect(w.deleteLater)
        w.start()

    def _set_ai_busy(self, busy):
        self.btn_ai.setEnabled(not busy)
        self.btn_save.setEnabled(not busy)
        self.btn_saveas.setEnabled(not busy)
        self.btn_generate.setEnabled(not busy)

    def _ai_content_ok(self):
        text = self.ai_text.toPlainText()
        if not text.strip():
            QMessageBox.information(self, '提示', '内容为空')
            return False
        if text.startswith('❌') or '正在请求 AI' in text:
            QMessageBox.information(self, '提示', '当前没有可保存的 AI 注释结果')
            return False
        return True

    def _save_ai(self):
        if not self._ai_content_ok():
            return
        text = self.ai_text.toPlainText()
        path = self._ai_saved_path
        if not path:
            idx = self.cmb_cfg.currentIndex()
            if 0 <= idx < len(self.cfg_files):
                base = os.path.basename(self.cfg_files[idx][3])
                path = os.path.join(self.csgo_cfg_dir or '',
                                    os.path.splitext(base)[0] + '_annotated.cfg')
            else:
                path = os.path.join(self.csgo_cfg_dir or '.', 'annotated.cfg')
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(text)
            self._ai_saved_path = path
            QMessageBox.information(self, '💾 已保存', '已保存到:\n' + path)
        except Exception as e:
            QMessageBox.warning(self, '保存失败', str(e))

    def _save_as_ai(self):
        if not self._ai_content_ok():
            return
        text = self.ai_text.toPlainText()
        path, _ = QFileDialog.getSaveFileName(self, '另存为', 'annotated.cfg',
                                              'CFG 文件 (*.cfg);;所有文件 (*.*)')
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(text)
            self._ai_saved_path = path
            QMessageBox.information(self, '💾 已保存', '已保存到:\n' + path)
        except Exception as e:
            QMessageBox.warning(self, '保存失败', str(e))

    def _copy_ai(self):
        QApplication.clipboard().setText(self.ai_text.toPlainText())

    def _generate_cfg(self):
        """向 AI 提问，直接生成一份 cfg。"""
        prompt = self.chat_input.toPlainText().strip()
        if not prompt:
            QMessageBox.information(self, '提示', '请先输入你的需求，例如：生成一个练枪 autoexec.cfg')
            return
        ai = self.settings.data.get('ai', {})
        if not ai.get('enabled', True):
            QMessageBox.information(self, '提示', 'AI 功能未启用，请在「⚙️ 设置」中开启并填写 API Key。')
            return
        if not (ai.get('api_key') or '').strip():
            QMessageBox.information(self, '提示', '未配置 API Key，请在「⚙️ 设置 → AI 助手」中填写。')
            return
        try:
            busy = self._gen_worker is not None and self._gen_worker.isRunning()
        except RuntimeError:
            busy = False
            self._gen_worker = None
        if busy:
            QMessageBox.information(self, '提示', 'AI 生成任务进行中，请稍候')
            return
        cfg = dict(ai)
        cfg['proxy'] = self.settings.get('proxy') or ''
        self.ai_text.setPlainText('🤖 正在生成 cfg，请稍候…')
        self.chk_expand.setChecked(True)
        self._set_ai_busy(True)
        w = GenerateWorker(cfg, prompt, self)

        def on_done(text):
            self._gen_worker = None
            self.ai_text.setPlainText(text)
            self._set_ai_busy(False)
            self.status.setText('✅ cfg 已生成，可 💾 保存 / 📄 另存为。')
        def on_failed(msg):
            self._gen_worker = None
            self.ai_text.setPlainText('❌ 生成失败：\n' + msg)
            self._set_ai_busy(False)
        w.done.connect(on_done)
        w.failed.connect(on_failed)
        self._gen_worker = w
        w.finished.connect(w.deleteLater)
        w.start()
