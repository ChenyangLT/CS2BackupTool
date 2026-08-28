"""AI 注释：调用 OpenAI 兼容 Chat Completions API（默认 DeepSeek），为 cfg 文件逐行添加中文注释。"""

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
        raise AISummaryError('未配置 API 地址（设置 → AI 注释）')
    if not base.startswith('http'):
        base = 'https://' + base
    return base


def _opener(proxy):
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({'http': proxy, 'https': proxy}))
    return urllib.request.build_opener(*handlers) if handlers else urllib.request.build_opener()


def _chat(ai_cfg, messages, max_tokens=None, temperature=None):
    base = _norm_base(ai_cfg.get('base_url'))
    api_key = (ai_cfg.get('api_key') or '').strip()
    if not api_key:
        raise AISummaryError('未配置 API Key（设置 → AI 注释）')
    model = ai_cfg.get('model') or 'deepseek-chat'
    body = {
        'model': model,
        'messages': messages,
        'temperature': float(temperature if temperature is not None
                             else (ai_cfg.get('temperature') or 0.3)),
        'stream': False,
    }
    if max_tokens:
        body['max_tokens'] = int(max_tokens)
    url = base + '/chat/completions'
    req = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'), method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', 'Bearer ' + api_key)
    req.add_header('User-Agent', 'CS2BackupTool/1.0')
    try:
        with _opener(ai_cfg.get('proxy') or '').open(req, timeout=180) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        detail = ''
        try:
            detail = e.read().decode('utf-8', 'replace')[:500]
        except Exception:
            pass
        raise AISummaryError(f'API 请求失败 (HTTP {e.code}): {detail}')
    except urllib.error.URLError as e:
        raise AISummaryError(f'网络错误: {e.reason}')
    except Exception as e:
        raise AISummaryError(f'请求异常: {e}')
    try:
        return data['choices'][0]['message']['content'].strip()
    except Exception:
        raise AISummaryError('API 返回格式异常: ' + json.dumps(data, ensure_ascii=False)[:500])


def _read_text_robust(path, retries=3, delay=0.3):
    """读取文本文件，失败自动重试（应对 Steam 云同步等造成的短暂占用/句柄失效）。"""
    last = None
    for _ in range(retries):
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        except Exception as e:
            last = e
            time.sleep(delay)
    raise last


def annotate_cfg(ai_cfg, file_path):
    """读取 cfg 文件，让 AI 逐行添加中文注释后返回完整带注释内容。"""
    try:
        content = _read_text_robust(file_path)
    except Exception as e:
        raise AISummaryError(f'读取文件失败: {e}')

    max_chars = 50000
    if len(content) > max_chars:
        content = content[:max_chars] + f'\n...(内容过长已截断，共 {len(content)} 字符)'
    if not content.strip():
        raise AISummaryError('文件内容为空')

    prompt = (
        '你是《反恐精英2》(CS2) 配置文件专家。请为下面的 CS2 配置文件逐行添加中文注释：'
        '保留每一行原始内容完全不变，在其正下方（或行尾）用 // 添加该命令/绑定/参数的作用说明；'
        '若某行已有注释则在其后补充说明；对配置块（如 bind / alias / 分组）可在块前加一行 // 小节说明。'
        '只输出带注释的完整配置文件内容，不要省略任何原始行，不要输出任何解释性开场白或结尾。\n\n'
        f'文件名: {os.path.basename(file_path)}\n\n'
        '文件内容如下:\n\n' + content
    )
    return _chat(ai_cfg, [{'role': 'user', 'content': prompt}])


def test_api(ai_cfg):
    """发送一条极短请求验证 API 可用性，返回模型回复。"""
    return _chat(ai_cfg,
                 [{'role': 'user', 'content': '请只回复两个字：正常'}],
                 max_tokens=16, temperature=0)
