# 解析 URL 編碼
def _url_decode(value):
    out = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch == "+":
            out.append(" ")
            i += 1
            continue
        if ch == "%" and i + 2 < len(value):
            try:
                out.append(chr(int(value[i + 1 : i + 3], 16)))
                i += 3
                continue
            except Exception:
                pass
        out.append(ch)
        i += 1
    return "".join(out)


# 解析表單資料



# 解析表單資料
def parse_form(body):
    result = {}
    if not body:
        return result
    for pair in body.split("&"):
        if "=" in pair:
            key, value = pair.split("=", 1)
            result[_url_decode(key)] = _url_decode(value)
    return result


# 解析整數



# 解析整數
def _to_int(value, default):
    try:
        return int(value)
    except Exception:
        return default


# 解析浮點數



# 解析浮點數
def _to_float(value, default):
    try:
        return float(value)
    except Exception:
        return default


# 解析逗號分隔字串



# 解析逗號分隔字串
def _split_csv(value):
    return [v.strip() for v in value.split(",") if v.strip()]


# 解析 IP 設定



# 解析 IP 設定
def _parse_static_ifcfg(value, fallback):
    parts = _split_csv(value)
    if len(parts) == 4:
        return parts
    return fallback


# 解析 RGB 陣列



# 解析布林值
def _to_bool(value, default):
    if value is None:
        return default
    return value in ("1", "true", "True", "on", "yes")


# 建立 Wi-Fi 表單欄位
