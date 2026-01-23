import time


# 安全列印，避免輸出例外中斷主流程
def safe_print(*a, **kw):
    try:
        print(*a, **kw)
    except Exception:
        pass


# 取得 ISO 格式時間字串
def get_date_iso(timezone_offset_s):
    ts = time.time() + timezone_offset_s
    y, m, d, hh, mm, ss, _, _ = time.localtime(ts)
    return "%04d-%02d-%02dT%02d:%02d:%02d" % (y, m, d, hh, mm, ss)
