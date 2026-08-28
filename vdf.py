"""Valve VDF 文件解析器（用于 loginusers.vdf / localconfig.vdf）。"""


def _tokenize(text):
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in ' \t\r\n':
            i += 1
            continue
        if c == '/' and i + 1 < n and text[i + 1] == '/':
            j = text.find('\n', i)
            i = n if j == -1 else j + 1
            continue
        if c in '{}[]':
            tokens.append(c)
            i += 1
            continue
        if c == '"':
            j = i + 1
            buf = []
            while j < n:
                ch = text[j]
                if ch == '\\' and j + 1 < n:
                    buf.append(text[j + 1])
                    j += 2
                    continue
                if ch == '"':
                    break
                buf.append(ch)
                j += 1
            tokens.append(''.join(buf))
            i = j + 1
            continue
        j = i
        while j < n and text[j] not in ' \t\r\n{}[]':
            j += 1
        tokens.append(text[i:j])
        i = j
    return tokens


def parse_vdf(text):
    """把 VDF 文本解析为嵌套 dict。"""
    tokens = _tokenize(text)
    pos = 0
    total = len(tokens)

    def parse_value():
        nonlocal pos
        if pos >= total:
            return ''
        tok = tokens[pos]
        pos += 1
        if tok in ('{', '['):
            d = {}
            while pos < total and tokens[pos] not in ('}', ']'):
                key = tokens[pos]
                pos += 1
                d[key] = parse_value()
            if pos < total:
                pos += 1  # 跳过闭合括号
            return d
        return tok

    root = {}
    while pos < total:
        key = tokens[pos]
        pos += 1
        root[key] = parse_value()
    return root
