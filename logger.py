"""日志与全局报错捕获（调试日志可在设置中开关，默认关闭；报错始终写 crash.log）。"""

import logging
import os
import sys
import time
import traceback

APP_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'CS2BackupTool')
LOG_DIR = os.path.join(APP_DIR, 'logs')
_log = None


def log_file():
    os.makedirs(LOG_DIR, exist_ok=True)
    return os.path.join(LOG_DIR, f'app_{time.strftime("%Y%m%d")}.log')


def crash_file():
    os.makedirs(LOG_DIR, exist_ok=True)
    return os.path.join(LOG_DIR, 'crash.log')


def setup_logging(enabled=False, console=False):
    """配置日志。enabled=False 时不写文件（默认关闭）。"""
    global _log
    logger = logging.getLogger('CS2BackupTool')
    for h in list(logger.handlers):
        logger.removeHandler(h)
    logger.setLevel(logging.DEBUG if enabled else logging.CRITICAL)
    if enabled:
        fh = logging.FileHandler(log_file(), encoding='utf-8')
        fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        logger.addHandler(fh)
        if console and not getattr(sys, 'frozen', False):
            sh = logging.StreamHandler()
            sh.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
            logger.addHandler(sh)
    else:
        logger.addHandler(logging.NullHandler())
    _log = logger
    return logger


def get_logger():
    global _log
    if _log is None:
        _log = setup_logging(False)
    return _log


def install_excepthook(logger=None):
    """捕获未处理异常：始终写入 crash.log 并弹窗（报错功能，不受调试开关影响）。"""
    log = logger or get_logger()

    def hook(exc_type, exc, tb):
        msg = ''.join(traceback.format_exception(exc_type, exc, tb))
        try:
            with open(crash_file(), 'a', encoding='utf-8') as f:
                f.write(f'\n===== {time.strftime("%Y-%m-%d %H:%M:%S")} =====\n{msg}\n')
        except Exception:
            pass
        log.error('未捕获异常:\n%s', msg)
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            if QApplication.instance() is not None:
                QMessageBox.critical(
                    None, '❌ 程序出错',
                    f'发生未捕获异常：\n{exc}\n\n详情见:\n{crash_file()}')
        except Exception:
            pass
    sys.excepthook = hook


def install_qt_handler(logger=None):
    """捕获 Qt 内部消息到日志（DEBUG 级别）。"""
    log = logger or get_logger()
    try:
        from PySide6.QtCore import qInstallMessageHandler

        def handler(mode, ctx, msg):
            log.debug('[Qt] %s', msg)
        qInstallMessageHandler(handler)
    except Exception:
        pass
