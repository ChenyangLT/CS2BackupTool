"""对话框：设置（白色主题）、恢复目标选择。"""

import os
import shutil

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QProgressDialog,
                               QPushButton, QSpinBox, QVBoxLayout)

import backup as bk
from ui_common import load_app_icon
from workers import AITestWorker


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle('⚙️ 设置')
        self.resize(600, 640)
        ic = load_app_icon()
        if ic:
            self.setWindowIcon(ic)
        v = QVBoxLayout(self)

        g1 = QGroupBox('🗄️ Steam 与备份目录')
        f1 = QFormLayout(g1)
        self.ed_steam = QLineEdit(settings.get('steam_path') or '')
        self.ed_backup = QLineEdit(settings.get('backup_dir') or '')
        f1.addRow('Steam 安装目录:', self._browse_row(self.ed_steam, '选择 Steam 安装目录'))
        f1.addRow('备份存储目录:', self._browse_row(self.ed_backup, '选择备份目录'))

        g2 = QGroupBox('⚙️ 显示与压缩')
        f2 = QFormLayout(g2)
        self.sp_page = QSpinBox()
        self.sp_page.setRange(1, 9)
        self.sp_page.setValue(int(settings.get('max_per_page') or 6))
        self.sp_page.setSuffix(' 个/页')
        self.sp_zip = QSpinBox()
        self.sp_zip.setRange(0, 9)
        self.sp_zip.setValue(int(settings.get('zip_compress') or 6))
        self.sp_zip.setSuffix(' 级（0 最快 / 9 最小）')
        f2.addRow('每页最多显示用户数:', self.sp_page)
        f2.addRow('zip 压缩等级:', self.sp_zip)

        g3 = QGroupBox('🌐 网络（用于快速获取头像 / AI 请求）')
        f3 = QFormLayout(g3)
        self.ed_proxy = QLineEdit(settings.get('proxy') or '')
        self.ed_proxy.setPlaceholderText('例如 http://127.0.0.1:7890（留空表示直连）')
        f3.addRow('代理服务器:', self.ed_proxy)

        g4 = QGroupBox('🤖 AI 注释')
        f4 = QFormLayout(g4)
        ai = settings.data['ai']
        self.chk_ai = QCheckBox('启用 AI 注释功能')
        self.chk_ai.setChecked(bool(ai.get('enabled', True)))
        self.ed_base = QLineEdit(ai.get('base_url') or '')
        self.ed_key = QLineEdit(ai.get('api_key') or '')
        self.ed_key.setEchoMode(QLineEdit.Password)
        self.ed_model = QLineEdit(ai.get('model') or '')
        self.sp_temp = QDoubleSpinBox()
        self.sp_temp.setRange(0.0, 2.0)
        self.sp_temp.setSingleStep(0.1)
        self.sp_temp.setValue(float(ai.get('temperature') or 0.3))
        f4.addRow(self.chk_ai)
        f4.addRow('API 地址:', self.ed_base)
        f4.addRow('API Key:', self.ed_key)
        f4.addRow('模型:', self.ed_model)
        f4.addRow('温度:', self.sp_temp)
        tip = QLabel('支持 OpenAI 兼容接口。示例（DeepSeek）：\n地址 https://api.deepseek.com/v1 ，模型 deepseek-chat')
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#6b7280; font-size:12px;')
        f4.addRow(tip)
        self._ai_fields = [self.ed_base, self.ed_key, self.ed_model, self.sp_temp]
        self.chk_ai.toggled.connect(self._toggle_ai)

        g5 = QGroupBox('🐞 调试与日志')
        f5 = QFormLayout(g5)
        self.chk_debug = QCheckBox('开启调试日志（记录到 %APPDATA%\\CS2BackupTool\\logs）')
        self.chk_debug.setChecked(bool(settings.get('debug_log', False)))
        f5.addRow(self.chk_debug)

        v.addWidget(g1)
        v.addWidget(g2)
        v.addWidget(g3)
        v.addWidget(g4)
        v.addWidget(g5)

        btns = QHBoxLayout()
        self.btn_test = QPushButton('🔌 测试 AI 连接')
        self.btn_test.clicked.connect(self._test)
        self.btn_reset = QPushButton('🔄 恢复默认')
        self.btn_reset.clicked.connect(self._reset_defaults)
        btns.addWidget(self.btn_test)
        btns.addWidget(self.btn_reset)
        # 在 btn_test 创建之后再同步 AI 字段启用状态，避免初始化顺序导致的崩溃
        self._toggle_ai(self.chk_ai.isChecked())
        btns.addStretch(1)
        btn_back = QPushButton('🏠 返回')
        btn_back.clicked.connect(self.reject)
        btn_ok = QPushButton('💾 保存')
        btn_ok.setObjectName('primary')
        btn_ok.clicked.connect(self._save)
        btns.addWidget(btn_back)
        btns.addWidget(btn_ok)
        v.addLayout(btns)

    def _browse_row(self, edit, title):
        h = QHBoxLayout()
        h.addWidget(edit, 1)
        b = QPushButton('📂 浏览…')
        def browse():
            start = edit.text() or os.path.expanduser('~')
            d = QFileDialog.getExistingDirectory(self, title, start)
            if d:
                edit.setText(d)
        b.clicked.connect(browse)
        h.addWidget(b)
        return h

    def _toggle_ai(self, enabled):
        for w in self._ai_fields:
            w.setEnabled(enabled)
        btn = getattr(self, 'btn_test', None)
        if btn:
            btn.setEnabled(enabled)

    def _collect_ai(self):
        return {
            'enabled': self.chk_ai.isChecked(),
            'base_url': self.ed_base.text().strip(),
            'api_key': self.ed_key.text().strip(),
            'model': self.ed_model.text().strip() or 'deepseek-chat',
            'temperature': self.sp_temp.value(),
            'proxy': self.ed_proxy.text().strip(),
        }

    def _save(self):
        old_dir = self.settings.get('backup_dir') or ''
        new_dir = self.ed_backup.text().strip()
        self.settings.data['steam_path'] = self.ed_steam.text().strip()
        self.settings.data['backup_dir'] = new_dir
        self.settings.data['max_per_page'] = self.sp_page.value()
        self.settings.data['zip_compress'] = self.sp_zip.value()
        self.settings.data['proxy'] = self.ed_proxy.text().strip()
        self.settings.data['debug_log'] = self.chk_debug.isChecked()
        self.settings.data['ai'] = self._collect_ai()
        try:
            self.settings.save()
        except Exception as e:
            QMessageBox.warning(self, '保存失败', str(e))
            return
        self._migrate_backups(old_dir, new_dir)
        self._apply_logging()
        self.accept()

    def _migrate_backups(self, old_dir, new_dir):
        """备份目录变更时，询问是否一键迁移已有备份。"""
        if not new_dir or not old_dir:
            return
        if os.path.normcase(os.path.normpath(old_dir)) == os.path.normcase(os.path.normpath(new_dir)):
            return
        if not os.path.isdir(old_dir):
            return
        zips = [f for f in os.listdir(old_dir) if f.lower().endswith('.zip')]
        if not zips:
            return
        ret = QMessageBox.question(
            self, '📦 迁移备份',
            f'原备份目录中有 {len(zips)} 个备份文件。\n是否一键迁移到新目录？\n\n{old_dir}\n⬇\n{new_dir}',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if ret != QMessageBox.Yes:
            return
        try:
            os.makedirs(new_dir, exist_ok=True)
        except Exception as e:
            QMessageBox.warning(self, '迁移失败', f'无法创建新目录: {e}')
            return
        moved = 0
        for f in zips:
            try:
                shutil.move(os.path.join(old_dir, f), os.path.join(new_dir, f))
                moved += 1
            except Exception:
                pass
        QMessageBox.information(self, '✅ 迁移完成', f'已迁移 {moved}/{len(zips)} 个备份文件到新目录。')

    def _apply_values(self):
        """把 settings 里的值同步到界面控件。"""
        self.ed_steam.setText(self.settings.get('steam_path') or '')
        self.ed_backup.setText(self.settings.get('backup_dir') or '')
        self.sp_page.setValue(int(self.settings.get('max_per_page') or 6))
        self.sp_zip.setValue(int(self.settings.get('zip_compress') or 6))
        self.ed_proxy.setText(self.settings.get('proxy') or '')
        ai = self.settings.data['ai']
        self.chk_ai.setChecked(bool(ai.get('enabled', True)))
        self.ed_base.setText(ai.get('base_url') or '')
        self.ed_key.setText(ai.get('api_key') or '')
        self.ed_model.setText(ai.get('model') or '')
        self.sp_temp.setValue(float(ai.get('temperature') or 0.3))
        self.chk_debug.setChecked(bool(self.settings.get('debug_log', False)))
        self._toggle_ai(self.chk_ai.isChecked())

    def _apply_logging(self):
        """根据 debug_log 设置即时启用/关闭日志。"""
        import logger as logutil
        logutil.setup_logging(enabled=bool(self.settings.get('debug_log', False)))

    def _reset_defaults(self):
        """恢复所有默认配置。"""
        ret = QMessageBox.question(
            self, '恢复默认配置',
            '确定要恢复所有设置为默认值吗？\n（将覆盖当前配置并立即保存）',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        self.settings.reset_defaults()
        try:
            self.settings.save()
        except Exception as e:
            QMessageBox.warning(self, '保存失败', str(e))
            return
        self._apply_values()
        self._apply_logging()
        QMessageBox.information(self, '✅ 已恢复', '已恢复所有默认配置。')

    def _test(self):
        ai_cfg = self._collect_ai()
        if not (ai_cfg.get('api_key') or '').strip():
            QMessageBox.warning(self, '测试失败', '请先填写 API Key')
            return
        dlg = QProgressDialog('正在测试 AI 连接…', None, 0, 0, self)
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setCancelButton(None)
        w = AITestWorker(ai_cfg, self)

        def on_done(text):
            dlg.close()
            QMessageBox.information(self, '✅ 测试成功', f'AI 连接正常，模型回复：\n{text[:300]}')
        def on_failed(msg):
            dlg.close()
            QMessageBox.warning(self, '测试失败', msg)
        w.done.connect(on_done)
        w.failed.connect(on_failed)
        self._test_worker = w
        w.finished.connect(w.deleteLater)
        w.start()
        dlg.exec()


class RestoreDialog(QDialog):
    """恢复备份：730 可跨用户恢复；cfg 恢复到游戏 csgo\\cfg 目录。"""

    def __init__(self, parent, info, accounts, current_account, csgo_cfg_dir):
        super().__init__(parent)
        self.info = info
        self.target_account = None
        self.backup_existing = True
        self.setWindowTitle('📥 恢复备份')
        self.resize(540, 360)
        ic = load_app_icon()
        if ic:
            self.setWindowIcon(ic)
        v = QVBoxLayout(self)

        info_lbl = QLabel(
            f'类型: {info.type_label}\n'
            f'原用户: {info.owner_label}\n'
            f'时间: {info.created}\n'
            f'大小: {bk._human_size(info.size)} · 文件数: {info.file_count}\n'
            f'文件: {os.path.basename(info.path)}'
        )
        info_lbl.setStyleSheet('color:#4b5563;')
        info_lbl.setWordWrap(True)
        v.addWidget(info_lbl)

        if info.btype == '730':
            v.addWidget(QLabel('📥 恢复到用户：'))
            self.cmb = QComboBox()
            default_idx = 0
            for i, a in enumerate(accounts):
                self.cmb.addItem(f'{a.display_name}  （账号: {a.account_name or "无"} · ID: {a.account_id}）', a)
                if a.account_id is not None and current_account.account_id is not None \
                        and a.account_id == current_account.account_id:
                    default_idx = i
            for i, a in enumerate(accounts):
                if a.account_id is not None and info.account_id is not None \
                        and a.account_id == info.account_id:
                    default_idx = i
            self.cmb.setCurrentIndex(default_idx)
            v.addWidget(self.cmb)
            tip = QLabel('可选择其他用户，把当前备份的 730 配置恢复到该用户。')
            tip.setWordWrap(True)
            tip.setStyleSheet('color:#6b7280; font-size:12px;')
            v.addWidget(tip)
        else:
            v.addWidget(QLabel('📥 恢复到：游戏 cfg 目录（全局）'))
            tgt = QLabel(csgo_cfg_dir or '未找到 CS2 游戏 cfg 目录')
            tgt.setWordWrap(True)
            tgt.setStyleSheet('color:#2563eb;')
            tgt.setTextInteractionFlags(Qt.TextSelectableByMouse)
            v.addWidget(tgt)

        self.chk = QCheckBox('🛡️ 恢复前自动备份目标现有配置（会在备份列表标注来源）')
        self.chk.setChecked(True)
        v.addWidget(self.chk)

        btns = QHBoxLayout()
        btn_back = QPushButton('🏠 返回')
        btn_back.clicked.connect(self.reject)
        ok = QPushButton('▶ 开始恢复')
        ok.setObjectName('primary')

        def on_ok():
            if self.info.btype == '730':
                if self.cmb.count() == 0:
                    QMessageBox.warning(self, '提示', '没有可恢复的目标用户')
                    return
                self.target_account = self.cmb.currentData()
            else:
                self.target_account = None
            self.backup_existing = self.chk.isChecked()
            self.accept()
        ok.clicked.connect(on_ok)
        btns.addStretch(1)
        btns.addWidget(btn_back)
        btns.addWidget(ok)
        v.addLayout(btns)
