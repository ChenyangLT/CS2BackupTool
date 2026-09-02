"""CS2 配置备份工具入口。

用法:
    CS2BackupTool.exe            启动 GUI
    CS2BackupTool.exe --debug    启动 GUI 并记录详细日志（日志见 %APPDATA%\\CS2BackupTool\\logs）
    CS2BackupTool.exe --selftest 核心逻辑自检（无需 GUI），结果写入 selftest_result.txt
    CS2BackupTool.exe --smoke    GUI 冒烟测试（离屏启动 2.5 秒自动退出），结果写入 smoke_result.txt
"""

import os
import sys

import logger as logutil

APP_VERSION = '1.5.1'


def _out_file(name):
    here = os.path.dirname(os.path.abspath(
        sys.argv[0] if getattr(sys, 'frozen', False) else __file__))
    return os.path.join(here, name)


def run_selftest():
    import shutil
    import tempfile
    from settings import Settings
    from steam import (Account, detect_steam_path, find_csgo_cfg_dir,
                       find_csgo_dir, load_accounts)
    import backup as bk

    logutil.setup_logging(enabled=True)
    logutil.get_logger().info('selftest 开始')

    lines = []
    result = 'FAIL'

    def log(*args):
        s = ' '.join(str(a) for a in args)
        lines.append(s)
        try:
            print(s)
        except Exception:
            pass

    try:
        # 1. VDF 解析
        from vdf import parse_vdf
        sample = ('"users"\n{\n\t"76561199466815329"\n\t{\n\t\t"PersonaName" "测试用户"\n'
                  '\t\t"AccountName" "tester"\n\t}\n}')
        tree = parse_vdf(sample)
        assert tree['users']['76561199466815329']['PersonaName'] == '测试用户', 'VDF 解析失败'
        log('[OK] VDF 解析')

        # 2. Steam 检测 + CS2 定位
        p = detect_steam_path()
        log(f'[检测] Steam 路径: {p}')
        if p:
            accts = load_accounts(p)
            log(f'[检测] 账户数: {len(accts)}')
            for a in accts:
                log(f'       - {a.display_name} | id={a.account_id} | 730={a.has_730}')
            log(f'[检测] csgo 目录: {find_csgo_dir(p)}')
            log(f'[检测] csgo cfg 目录: {find_csgo_cfg_dir(p)}')

        # 3. 备份（含备注）/ 恢复（含恢复前自动备份）
        tmp = tempfile.mkdtemp(prefix='cs2bt_selftest_')
        try:
            ud = os.path.join(tmp, 'userdata', '10001')
            cfg = os.path.join(ud, '730', 'remote', 'cfg')
            os.makedirs(cfg)
            with open(os.path.join(cfg, 'config.cfg'), 'w', encoding='utf-8') as f:
                f.write('// test config\nbind "a" "+left"\nsensitivity "2.1"\n')
            with open(os.path.join(cfg, 'autoexec.cfg'), 'w', encoding='utf-8') as f:
                f.write('hostname "selftest"\n')

            acct = Account(account_name='tester', persona_name='测试员',
                           steam_id64=str(76561197960265728 + 10001), userdata_dir=ud)
            bdir = os.path.join(tmp, 'backups')

            info = bk.backup_user(acct, bdir, 'cfg', note='测试备注', compress=6)
            assert os.path.isfile(info.path) and info.file_count == 2, 'CFG 备份失败'
            log(f'[OK] CFG 备份(含备注): {os.path.basename(info.path)}')

            infos = bk.list_backups(bdir)
            assert len(infos) == 1 and infos[0].btype == 'cfg', '备份列表读取失败'
            assert infos[0].note == '测试备注', '备注回读失败'
            log('[OK] 备份列表读取（manifest 元数据 + 备注）')

            acct2 = Account(account_name='tester2', persona_name='二号机',
                            steam_id64=str(76561197960265728 + 20002),
                            userdata_dir=os.path.join(tmp, 'userdata', '20002'))
            dest, auto = bk.restore_backup(infos[0], acct2.cfg_dir, bdir,
                                           backup_existing=False, auto_meta=None)
            assert os.path.isfile(os.path.join(dest, 'config.cfg')), '恢复失败'
            log(f'[OK] 恢复到其他用户: {dest}')

            # 再次恢复，验证「恢复前自动备份」会生成带来源备注的备份
            dest2, auto2 = bk.restore_backup(
                infos[0], acct2.cfg_dir, bdir, backup_existing=True,
                auto_meta={'persona': '二号机', 'account_name': 'tester2', 'account_id': 20002},
                compress=6)
            assert auto2 is not None and os.path.isfile(auto2.path), '恢复前自动备份未生成'
            assert '恢复前自动备份' in auto2.note, '自动备份未标明来源'
            log(f'[OK] 恢复前自动备份(标明来源): {os.path.basename(auto2.path)} -> {auto2.note}')

            info730 = bk.backup_user(acct, bdir, '730')
            assert info730.btype == '730' and os.path.isfile(info730.path), '730 备份失败'
            log(f'[OK] 730 备份: {os.path.basename(info730.path)}')

            # 备注编辑回写（zip 内 manifest.json）
            bk.update_note(info.path, '改后备注')
            found = [x for x in bk.list_backups(bdir) if x.path == info.path]
            assert found and found[0].note == '改后备注', '备注回写失败'
            bk.update_note(info.path, '')
            log('[OK] 备注编辑回写（zip manifest）')

            # AI 注释缓存（内容哈希检测变更）
            import ai_cache
            ai_cache.CACHE_DIR = os.path.join(tmp, 'aicache')
            ai_cache._INDEX = os.path.join(ai_cache.CACHE_DIR, 'index.json')
            cf = os.path.join(cfg, 'config.cfg')
            ai_cache.put_cached(cf, '注释内容ABC')
            assert ai_cache.get_cached(cf) == '注释内容ABC', '缓存命中失败'
            with open(cf, 'a', encoding='utf-8') as f:
                f.write('\n// 变更')
            assert ai_cache.get_cached(cf) is None, '文件变更后缓存应失效'
            log('[OK] AI 注释缓存（SHA-256 检测变更）')

            # 4. 设置 / AI 配置
            s = Settings()
            ai = s.data['ai']
            log(f'[检测] AI 配置: enabled={ai["enabled"]} base={ai["base_url"]} '
                f'model={ai["model"]} key={"已设置" if ai["api_key"] else "未设置"}')
            log(f'[检测] 每页用户数={s.data["max_per_page"]} 压缩等级={s.data["zip_compress"]} '
                f'代理={s.data["proxy"] or "未设置"}')

            log('[RESULT] 自检通过')
            result = 'PASS'
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    except Exception as e:
        import traceback
        log('[FAIL]', repr(e))
        lines.append(traceback.format_exc())

    try:
        with open(_out_file('selftest_result.txt'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + f'\nRESULT={result}\n')
    except Exception:
        pass
    sys.exit(0 if result == 'PASS' else 1)


def run_smoke():
    """离屏启动完整 GUI，2.5 秒后自动退出，验证界面能正常构建。"""
    errors = []
    logutil.setup_logging(enabled=True)
    logutil.install_excepthook()
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    logutil.install_qt_handler()
    app.setStyle('Fusion')
    from ui_common import get_stylesheet
    app.setStyleSheet(get_stylesheet())
    from ui_main import MainWindow
    win = MainWindow()
    win.show()
    # 验证设置对话框可正常构建（曾因按钮初始化顺序导致「设置」点击无反应）
    from ui_dialogs import SettingsDialog
    dlg = SettingsDialog(win.settings)
    dlg.deleteLater()
    # 验证用户窗口 + 重复打开去重（不应崩溃 / 打开两个）
    if win.accounts:
        win._open_user(win.accounts[0])
        win._open_user(win.accounts[0])
    QTimer.singleShot(2500, app.quit)
    try:
        app.exec()
        errors.append('ok')
    except Exception as e:
        errors.append(repr(e))
    ok = errors == ['ok']
    with open(_out_file('smoke_result.txt'), 'w', encoding='utf-8') as f:
        f.write('PASS' if ok else 'FAIL: ' + repr(errors))
    sys.exit(0 if ok else 1)


def main():
    debug = '--debug' in sys.argv
    from settings import Settings
    _s = Settings()
    log_enabled = debug or bool(_s.get('debug_log', False))
    logutil.setup_logging(enabled=log_enabled, console=debug)
    logutil.install_excepthook()
    from PySide6.QtWidgets import QApplication
    from ui_common import get_stylesheet, load_app_icon
    app = QApplication(sys.argv)
    if log_enabled:
        logutil.install_qt_handler()
        logutil.get_logger().info('程序启动, 版本 %s, debug=%s', APP_VERSION, debug)
    app.setApplicationName('CS2BackupTool')
    app.setApplicationVersion(APP_VERSION)
    app.setStyle('Fusion')
    app.setStyleSheet(get_stylesheet())
    from ui_main import MainWindow
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        run_selftest()
    elif '--smoke' in sys.argv:
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        run_smoke()
    else:
        main()
