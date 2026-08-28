"""开发者辅助：渲染主界面与用户管理界面（CFG 文件页 + AI 面板）并截图，便于视觉校验布局。"""

import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, here)

app = QApplication(sys.argv)
app.setStyle('Fusion')
from ui_common import get_stylesheet
app.setStyleSheet(get_stylesheet())

from ui_main import MainWindow
win = MainWindow()
win.show()

if win.accounts:
    win._open_user(win.accounts[0])


def shot():
    try:
        win.grab().save(os.path.join(here, 'main_shot.png'))
    except Exception as e:
        print('main shot fail', e)
    if win._user_windows:
        try:
            uw = list(win._user_windows.values())[0]
            uw.resize(1240, 780)
            uw.tabs.setCurrentIndex(1)          # 切到 CFG 文件页
            uw.chk_expand.setChecked(True)      # 展开 AI 面板
            uw.grab().save(os.path.join(here, 'user_shot.png'))
        except Exception as e:
            print('user shot fail', e)
    app.quit()


QTimer.singleShot(1800, shot)
app.exec()
print('screenshots saved')
