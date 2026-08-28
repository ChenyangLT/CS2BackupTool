"""备份 / 恢复 / 备份列表管理（zip + manifest.json）。

- 备份: 任意目录打包为 zip，manifest 记录类型/来源用户/备注等元数据。
- 恢复: 解压到目标目录，恢复前可自动备份目标现有配置（在备份列表标明来源）。
"""

import json
import os
import re
import shutil
import time
import zipfile


class BackupError(Exception):
    pass


MANIFEST_NAME = 'manifest.json'


def _safe_name(s):
    s = re.sub(r'[\\/:*?"<>|\r\n\t]', '_', str(s)).strip()
    return s[:60] or '备份'


def _ts_str(t=None):
    return time.strftime('%Y%m%d_%H%M%S', time.localtime(t or time.time()))


def _human_size(n):
    n = float(n)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return f'{int(n)} B' if unit == 'B' else f'{n:.1f} {unit}'
        n /= 1024
    return f'{n:.1f} GB'


class BackupInfo:
    __slots__ = ('path', 'btype', 'persona', 'account_name', 'account_id',
                 'created', 'size', 'file_count', 'created_raw', 'note')

    def __init__(self, path, btype, persona, account_name, account_id,
                 created, size, file_count, created_raw=0, note=''):
        self.path = path
        self.btype = btype
        self.persona = persona or ''
        self.account_name = account_name or ''
        self.account_id = account_id
        self.created = created
        self.size = size
        self.file_count = file_count
        self.created_raw = created_raw
        self.note = note or ''

    @property
    def type_label(self):
        return '730 全部数据' if self.btype == '730' else 'CFG 配置'

    @property
    def owner_label(self):
        return self.persona or self.account_name or '未知用户'


def _build_manifest(btype, persona, account_name, account_id, created, file_count, note):
    return {
        'app': 'CS2BackupTool',
        'version': 1,
        'type': btype,
        'account_name': account_name or '',
        'persona_name': persona or '',
        'account_id': account_id,
        'created': created,
        'file_count': file_count,
        'note': note or '',
    }


def backup_directory(src, backup_dir, btype, persona, account_name, account_id,
                     note=None, compress=6, progress=None, cancel=None):
    """把任意目录打包为 zip 备份，返回 BackupInfo。"""
    if not src or not os.path.isdir(src):
        raise BackupError(f'目录不存在: {src}')
    try:
        os.makedirs(backup_dir, exist_ok=True)
    except Exception as e:
        raise BackupError(f'无法创建备份目录: {e}')

    try:
        compress = max(0, min(9, int(compress if compress is not None else 6)))
    except (TypeError, ValueError):
        compress = 6

    stamp = _ts_str()
    name = f'{_safe_name(persona or "备份")}_{btype}_{stamp}.zip'
    path = os.path.join(backup_dir, name)

    files = []
    for root, dirs, fnames in os.walk(src):
        dirs.sort()
        for fn in sorted(fnames):
            files.append(os.path.join(root, fn))

    total = len(files) + 1
    created = time.strftime('%Y-%m-%d %H:%M:%S')

    try:
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, compresslevel=compress) as zf:
            manifest = _build_manifest(btype, persona, account_name, account_id,
                                       created, len(files), note)
            zf.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))
            for i, fp in enumerate(files, 1):
                if cancel and cancel():
                    raise BackupError('已取消备份')
                zf.write(fp, os.path.relpath(fp, src))
                if progress:
                    progress(i, total, os.path.basename(fp))
    except BackupError:
        try:
            os.remove(path)
        except Exception:
            pass
        raise
    except Exception as e:
        try:
            os.remove(path)
        except Exception:
            pass
        raise BackupError(f'备份失败: {e}')

    size = os.path.getsize(path)
    return BackupInfo(path, btype, persona, account_name, account_id,
                      created, size, len(files), note=note)


def backup_user(account, backup_dir, btype, note=None, compress=6, progress=None, cancel=None):
    """备份用户的 730 目录（或旧版用户级 cfg 目录）。"""
    if btype == 'cfg':
        src = account.cfg_dir
    elif btype == '730':
        src = account.data730_dir
    else:
        raise BackupError('未知备份类型: %s' % btype)
    return backup_directory(src, backup_dir, btype, account.persona_name,
                            account.account_name, account.account_id,
                            note, compress, progress, cancel)


def backup_cfg_dir(cfg_src_dir, backup_dir, account, note=None, compress=6,
                   progress=None, cancel=None):
    """备份游戏安装目录的 cfg 文件夹（全局，以当前账户名义命名）。"""
    return backup_directory(cfg_src_dir, backup_dir, 'cfg', account.persona_name,
                            account.account_name, account.account_id,
                            note, compress, progress, cancel)


def _read_backup_info(path):
    try:
        size = os.path.getsize(path)
        mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(path)))
        created_raw = os.path.getmtime(path)
    except Exception:
        return None

    btype, persona, acct_name, acct_id, created, file_count, note = None, '', '', None, mtime, 0, ''
    try:
        with zipfile.ZipFile(path) as zf:
            if MANIFEST_NAME in zf.namelist():
                data = json.loads(zf.read(MANIFEST_NAME).decode('utf-8'))
                btype = data.get('type')
                persona = data.get('persona_name') or ''
                acct_name = data.get('account_name') or ''
                acct_id = data.get('account_id')
                created = data.get('created') or mtime
                note = data.get('note') or ''
                try:
                    created_raw = time.mktime(time.strptime(created, '%Y-%m-%d %H:%M:%S'))
                except Exception:
                    created_raw = os.path.getmtime(path)
                try:
                    file_count = int(data.get('file_count') or (len(zf.namelist()) - 1))
                except Exception:
                    file_count = 0
            else:
                file_count = len([n for n in zf.namelist() if not n.endswith('/')])
    except Exception:
        pass

    if not btype:
        m = re.match(r'^(.+?)_(cfg|730)_(\d{8}_\d{6})\.zip$', os.path.basename(path))
        if m:
            btype = m.group(2)
            persona = m.group(1)
            created = time.strftime('%Y-%m-%d %H:%M:%S',
                                    time.strptime(m.group(3), '%Y%m%d_%H%M%S'))
            created_raw = time.mktime(time.strptime(m.group(3), '%Y%m%d_%H%M%S'))
    if not btype:
        return None
    return BackupInfo(path, btype, persona, acct_name, acct_id,
                      created, size, file_count, created_raw, note)


def list_backups(backup_dir):
    infos = []
    if not backup_dir or not os.path.isdir(backup_dir):
        return infos
    for fn in sorted(os.listdir(backup_dir)):
        if not fn.lower().endswith('.zip'):
            continue
        info = _read_backup_info(os.path.join(backup_dir, fn))
        if info:
            infos.append(info)
    infos.sort(key=lambda i: i.created_raw, reverse=True)
    return infos


def restore_backup(info, dest_dir, backup_dir, backup_existing=True, auto_meta=None,
                   compress=6, progress=None, cancel=None):
    """把备份恢复到目标目录。

    若 backup_existing=True 且目标目录已有文件，会先自动把目标现有配置打包成
    一个新的 zip 备份（manifest 的备注标明「恢复前自动备份」及恢复来源），
    再解压覆盖。返回 (目标目录, 自动备份信息或 None)。
    """
    auto_info = None
    if backup_existing and os.path.isdir(dest_dir):
        am = auto_meta or {}
        persona = am.get('persona') or '未知来源'
        account_name = am.get('account_name') or ''
        account_id = am.get('account_id')
        note = f'🛡️ 恢复前自动备份（恢复来源: {info.owner_label}）'
        if progress:
            progress(0, 1, '正在自动备份目标现有配置…')
        auto_info = backup_directory(dest_dir, backup_dir, info.btype, persona,
                                     account_name, account_id, note, compress,
                                     progress, cancel)

    os.makedirs(dest_dir, exist_ok=True)
    try:
        with zipfile.ZipFile(info.path) as zf:
            members = [m for m in zf.infolist()
                       if not m.is_dir() and m.filename != MANIFEST_NAME]
            total = len(members)
            for i, m in enumerate(members, 1):
                if cancel and cancel():
                    raise BackupError('已取消恢复')
                if m.filename.startswith('/') or '..' in m.filename.split('/'):
                    raise BackupError(f'压缩包内包含非法路径: {m.filename}')
                target = os.path.join(dest_dir, m.filename)
                real_dest = os.path.realpath(dest_dir)
                if not os.path.realpath(target).startswith(real_dest + os.sep):
                    raise BackupError(f'压缩包内包含越界路径: {m.filename}')
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(m) as sf, open(target, 'wb') as df:
                    shutil.copyfileobj(sf, df)
                if progress:
                    progress(i, total, os.path.basename(m.filename))
    except BackupError:
        raise
    except zipfile.BadZipFile as e:
        raise BackupError(f'压缩包损坏或格式不正确: {e}')
    except OSError as e:
        raise BackupError(f'恢复失败（文件可能被占用，请先退出 Steam）: {e}')
    except Exception as e:
        raise BackupError(f'恢复失败: {e}')
    return dest_dir, auto_info


def update_note(path, new_note):
    """修改 zip 内 manifest.json 的 note 字段（备注自由编辑）。"""
    tmp = path + '.tmp'
    try:
        with zipfile.ZipFile(path, 'r') as zin, \
                zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == MANIFEST_NAME:
                    try:
                        manifest = json.loads(data.decode('utf-8'))
                        manifest['note'] = new_note or ''
                        data = json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8')
                    except Exception:
                        pass
                zout.writestr(item, data)
        os.replace(tmp, path)
        return True
    except Exception as e:
        try:
            if os.path.isfile(tmp):
                os.remove(tmp)
        except Exception:
            pass
        raise BackupError(f'更新备注失败: {e}')
