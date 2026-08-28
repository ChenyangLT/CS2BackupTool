"""AI 注释结果本地缓存：cfg 文件内容未变化时复用缓存，节约 token。

缓存目录位于「软件根目录」下的 ai_cache/。
检测变更算法：对文件内容做 SHA-256 哈希，逐次比对；同时记录文件大小与修改时间。
"""

import hashlib
import json
import os
import sys
import time


def app_root():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.dirname(os.path.abspath(__file__))


CACHE_DIR = os.path.join(app_root(), 'ai_cache')
_INDEX = os.path.join(CACHE_DIR, 'index.json')


def _load_index():
    try:
        with open(_INDEX, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_index(idx):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(_INDEX, 'w', encoding='utf-8') as f:
            json.dump(idx, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _safe_key(file_path):
    return hashlib.md5(file_path.encode('utf-8', 'replace')).hexdigest()


def _content_hash(file_path):
    h = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def get_cached(file_path):
    """若文件内容未变化且存在缓存，返回缓存文本；否则返回 None。"""
    try:
        idx = _load_index()
        ent = idx.get(_safe_key(file_path))
        if not ent:
            return None
        if ent.get('hash') != _content_hash(file_path):
            return None
        out = os.path.join(CACHE_DIR, ent.get('out', ''))
        if not out or not os.path.isfile(out):
            return None
        with open(out, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return None


def put_cached(file_path, annotated_text):
    """缓存注释结果，返回是否成功。"""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        h = _content_hash(file_path)
        key = _safe_key(file_path)
        out_name = f'{key}_{h[:16]}.txt'
        out = os.path.join(CACHE_DIR, out_name)
        with open(out, 'w', encoding='utf-8') as f:
            f.write(annotated_text)
        idx = _load_index()
        idx[key] = {'hash': h, 'out': out_name,
                    'file': os.path.basename(file_path),
                    'size': os.path.getsize(file_path),
                    'time': time.strftime('%Y-%m-%d %H:%M:%S')}
        _save_index(idx)
        return True
    except Exception:
        return False
