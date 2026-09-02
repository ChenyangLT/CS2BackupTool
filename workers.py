"""后台线程（备份 / 恢复 / AI 注释 / 头像抓取），避免阻塞界面。"""

from PySide6.QtCore import QThread, Signal

import ai as ai_mod
import backup as bk
import bilibili as bilibili_mod
import logger as logutil
import steam as steam_mod


class BackupWorker(QThread):
    progress = Signal(int, int, str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, src, backup_dir, btype, persona, account_name, account_id,
                 note=None, compress=6, parent=None):
        super().__init__(parent)
        self.src = src
        self.backup_dir = backup_dir
        self.btype = btype
        self.persona = persona
        self.account_name = account_name
        self.account_id = account_id
        self.note = note
        self.compress = compress
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            info = bk.backup_directory(
                self.src, self.backup_dir, self.btype, self.persona,
                self.account_name, self.account_id, self.note, self.compress,
                progress=lambda c, t, n: self.progress.emit(c, t, n),
                cancel=lambda: self._cancel)
            self.done.emit(info)
        except bk.BackupError as e:
            logutil.get_logger().error('备份失败: %s', e)
            self.failed.emit(str(e))
        except Exception as e:
            logutil.get_logger().error('备份异常: %s', e, exc_info=True)
            self.failed.emit(str(e))


class RestoreWorker(QThread):
    progress = Signal(int, int, str)
    done = Signal(object)   # (dest_dir, auto_backup_info 或 None)
    failed = Signal(str)

    def __init__(self, info, dest_dir, backup_dir, backup_existing, auto_meta,
                 compress=6, parent=None):
        super().__init__(parent)
        self.info = info
        self.dest_dir = dest_dir
        self.backup_dir = backup_dir
        self.backup_existing = backup_existing
        self.auto_meta = auto_meta
        self.compress = compress
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            result = bk.restore_backup(
                self.info, self.dest_dir, self.backup_dir,
                backup_existing=self.backup_existing,
                auto_meta=self.auto_meta,
                compress=self.compress,
                progress=lambda c, t, n: self.progress.emit(c, t, n),
                cancel=lambda: self._cancel)
            self.done.emit(result)
        except bk.BackupError as e:
            logutil.get_logger().error('恢复失败: %s', e)
            self.failed.emit(str(e))
        except Exception as e:
            logutil.get_logger().error('恢复异常: %s', e, exc_info=True)
            self.failed.emit(str(e))


class AIWorker(QThread):
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, ai_cfg, content, filename, parent=None):
        super().__init__(parent)
        self.ai_cfg = ai_cfg
        self.content = content
        self.filename = filename

    def run(self):
        try:
            result = ai_mod.annotate_content(self.ai_cfg, self.content, self.filename)
            self.done.emit(result)
        except ai_mod.AISummaryError as e:
            logutil.get_logger().error('AI 注释失败: %s', e)
            self.failed.emit(str(e))
        except Exception as e:
            logutil.get_logger().error('AI 注释异常: %s', e, exc_info=True)
            self.failed.emit(str(e))


class AITestWorker(QThread):
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, ai_cfg, parent=None):
        super().__init__(parent)
        self.ai_cfg = ai_cfg

    def run(self):
        try:
            result = ai_mod.test_api(self.ai_cfg)
            self.done.emit(result)
        except ai_mod.AISummaryError as e:
            logutil.get_logger().error('AI 测试失败: %s', e)
            self.failed.emit(str(e))
        except Exception as e:
            logutil.get_logger().error('AI 测试异常: %s', e, exc_info=True)
            self.failed.emit(str(e))


class AvatarWorker(QThread):
    done = Signal(object)   # (steam_id64, 本地路径 或 None)

    def __init__(self, steam_id64, proxy='', parent=None):
        super().__init__(parent)
        self.steam_id64 = steam_id64
        self.proxy = proxy

    def run(self):
        path = steam_mod.fetch_steam_avatar(self.steam_id64, self.proxy)
        logutil.get_logger().debug('头像抓取 %s -> %s', self.steam_id64, path or '失败')
        self.done.emit((self.steam_id64, path))


class BilibiliWorker(QThread):
    done = Signal(object)   # dict(name, face, fans, sign, level, avatar_path)
    failed = Signal(str)

    def __init__(self, proxy='', parent=None):
        super().__init__(parent)
        self.proxy = proxy

    def run(self):
        try:
            info = bilibili_mod.get_bilibili_info(proxy=self.proxy)
            info['avatar_path'] = bilibili_mod.fetch_avatar(info.get('face'), proxy=self.proxy)
            self.done.emit(info)
        except Exception as e:
            logutil.get_logger().error('Bilibili 信息获取失败: %s', e)
            self.failed.emit(str(e))


class GenerateWorker(QThread):
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, ai_cfg, prompt, parent=None):
        super().__init__(parent)
        self.ai_cfg = ai_cfg
        self.prompt = prompt

    def run(self):
        try:
            result = ai_mod.generate_cfg(self.ai_cfg, self.prompt)
            self.done.emit(result)
        except ai_mod.AISummaryError as e:
            logutil.get_logger().error('AI 生成失败: %s', e)
            self.failed.emit(str(e))
        except Exception as e:
            logutil.get_logger().error('AI 生成异常: %s', e, exc_info=True)
            self.failed.emit(str(e))
