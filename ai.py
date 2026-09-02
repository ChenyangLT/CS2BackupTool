"""AI 注释 / 生成：调用 OpenAI 兼容 Chat Completions API（默认 DeepSeek）。"""

import json
import os
import time
import urllib.error
import urllib.request


class AISummaryError(Exception):
    pass


def _norm_base(base):
    base = (base or '').strip().rstrip('/')
    if not base:
        raise AISummaryError('未配置 API 地址（设置 → AI 助手）')
    if not base.startswith('http'):
        base = 'https://' + base
    return base


def _opener(proxy):
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({'http': proxy, 'https': proxy}))
    return urllib.request.build_opener(*handlers) if handlers else urllib.request.build_opener()


def _post_chat(url, api_key, proxy, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'), method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', 'Bearer ' + api_key)
    req.add_header('User-Agent', 'CS2BackupTool/1.4')
    try:
        with _opener(proxy).open(req, timeout=180) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        detail = ''
        try:
            detail = e.read().decode('utf-8', 'replace')[:600]
        except Exception:
            pass
        if e.code == 401:
            raise AISummaryError('API Key 无效或已失效 (HTTP 401)，请到「设置 → AI 助手」重新填写。')
        if e.code == 429:
            raise AISummaryError(f'请求过于频繁或额度不足 (HTTP 429)。\n{detail}')
        raise AISummaryError(f'API 请求失败 (HTTP {e.code}): {detail}')
    except urllib.error.URLError as e:
        raise AISummaryError(f'网络错误: {e.reason}')
    except Exception as e:
        raise AISummaryError(f'请求异常: {e}')


def _chat(ai_cfg, messages, max_tokens=None, temperature=None):
    base = _norm_base(ai_cfg.get('base_url'))
    api_key = (ai_cfg.get('api_key') or '').strip()
    if not api_key:
        raise AISummaryError('未配置 API Key（设置 → AI 助手）')
    model = ai_cfg.get('model') or 'deepseek-chat'
    proxy = ai_cfg.get('proxy') or ''
    temp = float(temperature if temperature is not None else (ai_cfg.get('temperature') or 0.3))
    url = base + '/chat/completions'
    body = {'model': model, 'messages': messages, 'stream': False}
    if max_tokens:
        body['max_tokens'] = int(max_tokens)
    # 部分模型（如 deepseek-v4-flash / reasoner）只允许 temperature=1，
    # 遇到该错误时自动去掉 temperature 参数重试。
    for use_temp in (True, False):
        b = dict(body)
        if use_temp:
            b['temperature'] = temp
        try:
            data = _post_chat(url, api_key, proxy, b)
        except AISummaryError as e:
            if use_temp and 'temperature' in str(e).lower():
                continue
            raise
        try:
            return data['choices'][0]['message']['content'].strip()
        except Exception:
            raise AISummaryError('API 返回格式异常: ' + json.dumps(data, ensure_ascii=False)[:500])
    raise AISummaryError('AI 请求失败')


def read_cfg_text(path, retries=10, delay=0.5):
    """读取文本文件（二进制方式读取后解码），失败自动重试（应对 Steam 云同步造成的句柄失效）。"""
    last = None
    for _ in range(retries):
        try:
            with open(path, 'rb') as f:
                return f.read().decode('utf-8', 'replace')
        except Exception as e:
            last = e
            time.sleep(delay)
    raise last


def annotate_content(ai_cfg, content, filename=''):
    """让 AI 为 cfg 内容逐行添加中文注释后返回完整带注释内容。"""
    if len(content) > 50000:
        content = content[:50000] + f'\n...(内容过长已截断，共 {len(content)} 字符)'
    if not content.strip():
        raise AISummaryError('文件内容为空')

    prompt = (
        '你是《反恐精英2》(CS2) 配置文件专家。请为下面的 CS2 配置文件逐行添加中文注释：'
        '保留每一行原始内容完全不变，在其正下方（或行尾）用 // 添加该命令/绑定/参数的作用说明；'
        '若某行已有注释则在其后补充说明；对配置块（如 bind / alias / 分组）可在块前加一行 // 小节说明。'
        '只输出带注释的完整配置文件内容，不要省略任何原始行，不要输出任何解释性开场白或结尾。\n\n'
        f'文件名: {filename}\n\n'
        '文件内容如下:\n\n' + content
    )
    return _chat(ai_cfg, [{'role': 'user', 'content': prompt}])


def generate_cfg(ai_cfg, user_prompt):
    """根据用户需求直接生成一份 CS2 cfg 配置内容。"""
    prompt = (
        '你是《反恐精英2》(CS2) 配置专家。请根据用户的需求，直接生成一份完整、可用的 CS2 cfg 配置内容。'
        '只输出 cfg 配置内容本身（可用 // 添加中文注释），不要输出任何解释性开场白或结尾。\n\n'
        f'用户需求：{user_prompt}'
    )
    return _chat(ai_cfg, [{'role': 'user', 'content': prompt}])


def test_api(ai_cfg):
    """发送一条极短请求验证 API 可用性，返回模型回复。"""
    return _chat(ai_cfg,
                 [{'role': 'user', 'content': '请只回复两个字：正常'}],
                 max_tokens=16, temperature=0)
