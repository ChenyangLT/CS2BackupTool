"""程序配置读写（存放在 %APPDATA%\\CS2BackupTool\\config.json）。"""

import json
import os
import sys

APP_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'CS2BackupTool')

DEFAULT_AI = {
    'enabled': True,
    'base_url': 'https://api.deepseek.com/v1',
    'api_key': '',
    'model': 'deepseek-chat',
    'temperature': 0.3,
}

DEFAULTS = {
    'steam_path': '',
    'backup_dir': '',
    'max_per_page': 6,      # 每页最多显示用户数 (1-9)
    'zip_compress': 6,      # zip 压缩等级 (0-9)
    'proxy': '',            # 代理 (http://127.0.0.1:7890)，用于头像抓取 / AI 请求
    'debug_log': False,     # 调试日志开关（默认关闭）
    'ai': dict(DEFAULT_AI),
}


def _clamp_int(v, lo, hi, default):
    try:
        v = int(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


class Settings:
    def __init__(self, path=None):
        self.path = path or os.path.join(APP_DIR, 'config.json')
        self.data = json.loads(json.dumps(DEFAULTS))  # 深拷贝
        self.load()

    def load(self):
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            for k, v in raw.items():
                if k == 'ai' and isinstance(v, dict):
                    for kk, vv in v.items():
                        if kk in DEFAULT_AI:
                            self.data['ai'][kk] = vv
                elif k in self.data:
                    self.data[k] = v
        except Exception:
            pass
        # 校正数值字段
        self.data['max_per_page'] = _clamp_int(self.data.get('max_per_page'), 1, 9, 6)
        self.data['zip_compress'] = _clamp_int(self.data.get('zip_compress'), 0, 9, 6)

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path) or '.', exist_ok=True)
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise IOError(f'保存设置失败: {e}')

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    def reset_defaults(self):
        """恢复所有默认配置。"""
        self.data = json.loads(json.dumps(DEFAULTS))


def default_backup_dir():
    """返回一个可写的默认备份目录。"""
    if getattr(sys, 'frozen', False):
        here = os.path.dirname(os.path.abspath(sys.argv[0]))
    else:
        here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, 'Backups'),
        os.path.join(os.path.expanduser('~'), 'Documents', 'CS2BackupTool', 'Backups'),
        os.path.join(APP_DIR, 'Backups'),
    ]
    for c in candidates:
        try:
            os.makedirs(c, exist_ok=True)
            t = os.path.join(c, '.wtest')
            with open(t, 'w', encoding='utf-8') as f:
                f.write('x')
            os.remove(t)
            return c
        except Exception:
            continue
    return candidates[-1]
