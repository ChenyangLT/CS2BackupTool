"""Bilibili 信息获取：头像 / 昵称 / 粉丝数（用 cookie 会话绕过风控，尽力而为）。"""

import http.cookiejar
import json
import os
import shutil
import urllib.request

BILI_UID = '3461567773411503'
BILI_HOME = 'https://space.bilibili.com/' + BILI_UID

_AVATAR_CACHE_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')),
                                 'CS2BackupTool', 'avatars')

_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
       '(KHTML, like Gecko) Chrome/120.0 Safari/537.36')


def _opener(proxy):
    handlers = [urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())]
    if proxy:
        handlers.append(urllib.request.ProxyHandler({'http': proxy, 'https': proxy}))
    return urllib.request.build_opener(*handlers)


def _get(opener, url, timeout=12):
    req = urllib.request.Request(url, headers={
        'User-Agent': _UA,
        'Referer': 'https://www.bilibili.com/',
    })
    with opener.open(req, timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')


def get_bilibili_info(uid=None, proxy='', timeout=12):
    """获取 B 站用户信息，返回 dict(name, face, fans, sign, level)。失败抛异常。"""
    uid = uid or BILI_UID
    opener = _opener(proxy)
    try:
        _get(opener, 'https://www.bilibili.com/', timeout=timeout)  # 先获取 buvid3 等 cookie
    except Exception:
        pass
    data = _get(opener, f'https://api.bilibili.com/x/web-interface/card?mid={uid}', timeout=timeout)
    obj = json.loads(data)
    if obj.get('code') != 0:
        raise RuntimeError(f'Bilibili 接口返回 code={obj.get("code")}')
    card = obj['data']['card']
    return {
        'name': card.get('name', ''),
        'face': card.get('face', ''),
        'fans': card.get('fans', 0),
        'sign': card.get('sign', ''),
        'level': (card.get('level_info') or {}).get('current_level', 0),
    }


def fetch_avatar(face_url, uid=None, proxy='', timeout=15):
    """下载 B 站头像到本地缓存，返回缓存路径；失败返回 None。"""
    uid = uid or BILI_UID
    if not face_url:
        return None
    dest = os.path.join(_AVATAR_CACHE_DIR, f'bili_{uid}.jpg')
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        req = urllib.request.Request(face_url, headers={
            'User-Agent': _UA,
            'Referer': 'https://www.bilibili.com/',
        })
        with _opener(proxy).open(req, timeout=timeout) as r, open(dest, 'wb') as f:
            shutil.copyfileobj(r, f)
        if os.path.isfile(dest) and os.path.getsize(dest) > 0:
            return dest
    except Exception:
        pass
    return None
