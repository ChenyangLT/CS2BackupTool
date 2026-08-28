"""Steam 安装目录/库目录检测、账户识别、CS2 cfg 目录定位、头像获取（本地 + 网络动态头像）。"""

import os
import shutil
import urllib.request
import xml.etree.ElementTree as ET

from vdf import parse_vdf

STEAM_ID_OFFSET = 76561197960265728

# 网络头像本地缓存目录
_AVATAR_CACHE_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')),
                                 'CS2BackupTool', 'avatars')


class Account:
    """一个 Steam 账户（可能没有 userdata / 730 数据）。"""

    def __init__(self, account_name='', persona_name='', steam_id64=None, avatar_hash='', userdata_dir=None):
        self.account_name = account_name or ''
        self.persona_name = persona_name or ''
        self.steam_id64 = steam_id64
        self.avatar_hash = avatar_hash or ''
        self.userdata_dir = userdata_dir

    @property
    def display_name(self):
        return self.persona_name or self.account_name or '未知用户'

    @property
    def account_id(self):
        if self.steam_id64:
            try:
                return int(self.steam_id64) - STEAM_ID_OFFSET
            except (TypeError, ValueError):
                pass
        if self.userdata_dir:
            try:
                return int(os.path.basename(os.path.normpath(self.userdata_dir)))
            except ValueError:
                pass
        return None

    @property
    def cfg_dir(self):
        """730 内的 cfg 目录（userdata/<id>/730/remote/cfg，保留给兼容/自检用）。"""
        if self.userdata_dir:
            return os.path.join(self.userdata_dir, '730', 'remote', 'cfg')
        return None

    @property
    def data730_dir(self):
        if self.userdata_dir:
            return os.path.join(self.userdata_dir, '730')
        return None

    @property
    def has_730(self):
        return bool(self.data730_dir and os.path.isdir(self.data730_dir))

    def is_730_empty(self):
        """730 目录是否为空（目录不存在视为空）。"""
        d = self.data730_dir
        if not d or not os.path.isdir(d):
            return True
        try:
            return not any(os.scandir(d))
        except Exception:
            return True


def detect_steam_path():
    """从注册表或常见路径探测 Steam 安装目录。"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as key:
            val, _ = winreg.QueryValueEx(key, 'SteamPath')
            if val and os.path.isdir(val):
                return val
    except Exception:
        pass
    for p in (r'C:\Program Files (x86)\Steam', r'C:\Program Files\Steam',
              r'D:\Steam', r'D:\Program Files (x86)\Steam', r'E:\Steam'):
        if os.path.isdir(p):
            return p
    return None


def _norm(p):
    return os.path.normcase(os.path.normpath(p))


def find_library_paths(steam_path):
    """返回所有 Steam 库目录（主目录 + libraryfolders.vdf 中的其它库）。"""
    libs = [steam_path]
    lf = os.path.join(steam_path, 'steamapps', 'libraryfolders.vdf')
    if os.path.isfile(lf):
        try:
            with open(lf, 'r', encoding='utf-8', errors='replace') as f:
                tree = parse_vdf(f.read())
            folders = tree.get('libraryfolders', {})
            if isinstance(folders, dict):
                for v in folders.values():
                    if isinstance(v, dict) and v.get('path'):
                        p = os.path.normpath(v['path'])
                        if p and not any(_norm(p) == _norm(x) for x in libs):
                            libs.append(p)
        except Exception:
            pass
    return libs


def find_csgo_dir(steam_path):
    """定位 CS2 安装目录 game\\csgo（在所有库中查找）。"""
    for lib in find_library_paths(steam_path):
        p = os.path.join(lib, 'steamapps', 'common',
                         'Counter-Strike Global Offensive', 'game', 'csgo')
        if os.path.isdir(p):
            return p
    return None


def find_csgo_cfg_dir(steam_path):
    """定位游戏安装目录的 cfg 文件夹：
    <库>\\steamapps\\common\\Counter-Strike Global Offensive\\game\\csgo\\cfg
    """
    d = find_csgo_dir(steam_path)
    if d:
        return os.path.join(d, 'cfg')
    return None


def cached_avatar_path(steam_id64):
    if not steam_id64:
        return None
    return os.path.join(_AVATAR_CACHE_DIR, f'{steam_id64}.jpg')


def avatar_path(steam_path, avatar_hash=None, steam_id64=None):
    """返回头像图片的绝对路径；不存在则返回 None。

    优先级: 本地 Steam 头像 -> 网络下载缓存头像。
    """
    candidates = []
    if steam_path and avatar_hash:
        name = avatar_hash + ('' if avatar_hash.lower().endswith('.png') else '.png')
        candidates.append(os.path.join(steam_path, 'config', 'avatars', name))
        candidates.append(os.path.join(steam_path, 'config', 'avatarcache', name))
    if steam_path and steam_id64:
        candidates.append(os.path.join(steam_path, 'config', 'avatarcache', f'{steam_id64}.png'))
        candidates.append(os.path.join(steam_path, 'config', 'avatars', f'{steam_id64}.png'))
    cached = cached_avatar_path(steam_id64)
    if cached:
        candidates.append(cached)
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


def _opener(proxy):
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({'http': proxy, 'https': proxy}))
    return urllib.request.build_opener(*handlers) if handlers else urllib.request.build_opener()


def get_steam_avatar_url(steam_id64, proxy='', timeout=10):
    """通过 Steam 社区 XML 获取头像直链（动态头像，尽力而为）。"""
    url = f'https://steamcommunity.com/profiles/{steam_id64}/?xml=1'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with _opener(proxy).open(req, timeout=timeout) as r:
            data = r.read().decode('utf-8', 'replace')
    except Exception:
        return None
    try:
        root = ET.fromstring(data)
    except Exception:
        return None
    for tag in ('avatarFull', 'avatarMedium', 'avatarIcon'):
        el = root.find(tag)
        if el is not None and el.text and el.text.startswith('http'):
            return el.text
    return None


def fetch_steam_avatar(steam_id64, proxy='', timeout=12):
    """抓取并缓存 Steam 动态头像，成功返回本地缓存路径，失败返回 None。"""
    try:
        url = get_steam_avatar_url(steam_id64, proxy, timeout)
        if not url:
            return None
        dest = cached_avatar_path(steam_id64)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with _opener(proxy).open(req, timeout=timeout) as r, open(dest, 'wb') as f:
            shutil.copyfileobj(r, f)
        if os.path.isfile(dest) and os.path.getsize(dest) > 0:
            return dest
    except Exception:
        pass
    return None


def _read_persona_from_localconfig(userdata_dir):
    """从 userdata/<id>/config/localconfig.vdf 读取昵称（备用关联手段）。"""
    lc = os.path.join(userdata_dir, 'config', 'localconfig.vdf')
    try:
        with open(lc, 'r', encoding='utf-8', errors='replace') as f:
            tree = parse_vdf(f.read())
        friends = tree.get('UserLocalConfigStore', {}).get('friends', {})
        if isinstance(friends, dict):
            return friends.get('PersonaName', '') or ''
    except Exception:
        pass
    return ''


def load_accounts(steam_path):
    """识别 Steam 下的所有账户，返回 Account 列表。"""
    accounts = []
    if not steam_path or not os.path.isdir(steam_path):
        return accounts

    login_map = {}
    login_path = os.path.join(steam_path, 'config', 'loginusers.vdf')
    if os.path.isfile(login_path):
        try:
            with open(login_path, 'r', encoding='utf-8', errors='replace') as f:
                tree = parse_vdf(f.read())
            users = tree.get('users', {})
            if isinstance(users, dict):
                for name, info in users.items():
                    if isinstance(info, dict):
                        login_map[name] = info
        except Exception:
            pass

    ud_root = os.path.join(steam_path, 'userdata')
    userdata_ids = set()
    if os.path.isdir(ud_root):
        try:
            for name in os.listdir(ud_root):
                if name.isdigit() and os.path.isdir(os.path.join(ud_root, name)):
                    userdata_ids.add(int(name))
        except Exception:
            pass

    seen_ids = set()
    seen_personas = set()

    def is_new_format(key, info):
        try:
            return key.isdigit() and int(key) > STEAM_ID_OFFSET
        except (TypeError, ValueError):
            return False

    for key, info in login_map.items():
        if is_new_format(key, info):
            sid = key
            account_name = info.get('AccountName', '') or ''
        else:
            sid = info.get('SteamID', '') or ''
            account_name = key
        persona = info.get('PersonaName', '') or ''
        acct = Account(account_name=account_name, persona_name=persona,
                       steam_id64=sid, avatar_hash=info.get('avatar', '') or '')
        aid = acct.account_id
        if aid is not None and aid in userdata_ids:
            acct.userdata_dir = os.path.join(ud_root, str(aid))
        if aid is not None:
            seen_ids.add(aid)
        if persona:
            seen_personas.add(persona)
        accounts.append(acct)

    for aid in sorted(userdata_ids):
        if aid in seen_ids:
            continue
        ud = os.path.join(ud_root, str(aid))
        persona = _read_persona_from_localconfig(ud)
        if persona and persona in seen_personas:
            continue
        acct = Account(persona_name=persona, userdata_dir=ud, steam_id64=STEAM_ID_OFFSET + aid)
        for name, info in login_map.items():
            if (info.get('PersonaName') or '') == persona \
                    and not is_new_format(name, info) and not info.get('SteamID'):
                acct.account_name = name
                acct.avatar_hash = info.get('avatar', '') or ''
                break
        if persona:
            seen_personas.add(persona)
        accounts.append(acct)

    accounts.sort(key=lambda a: a.display_name.lower())
    return accounts
