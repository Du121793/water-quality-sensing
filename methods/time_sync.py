import time
import machine
import ntptime
import urequests
from .utils import safe_print

_MONTH = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


# 透過 HTTP Date 取得伺服器時間
def _http_head_date(host):
    try:
        url = "http://" + host
        try:
            r = urequests.request("HEAD", url)
        except Exception:
            r = urequests.get(url)
        try:
            if hasattr(r, "headers") and "Date" in r.headers:
                return r.headers["Date"]
            return None
        finally:
            try:
                r.close()
            except Exception:
                pass
    except Exception as e:
        safe_print("[HTTP-TIME] error:", e)
    return None


# 同步裝置時間，優先 NTP、失敗再用 HTTP Date
def sync_time(cfg):
    try:
        ntptime.host = cfg["time"]["ntp_host"]
        ntptime.settime()
        y, mo, d, hh, mm, ss, _, _ = time.gmtime()
        safe_print(
            "[NTP] synced:", "%04d-%02d-%02dT%02d:%02d:%02dZ" % (y, mo, d, hh, mm, ss)
        )
        return True
    except Exception as e:
        safe_print("[NTP] failed:", e)

    for host in cfg["time"]["http_hosts"]:
        ds = _http_head_date(host)
        if not ds:
            continue
        try:
            p = ds.split()
            day = int(p[1])
            mon = _MONTH[p[2]]
            year = int(p[3])
            hh, mm, ss = map(int, p[4].split(":"))
            epoch = time.mktime((year, mon, day, hh, mm, ss, 0, 0))
            y, mo, d, hh, mm, ss, wd, yd = time.gmtime(epoch)
            machine.RTC().datetime((y, mo, d, wd, hh, mm, ss, 0))
            safe_print(
                "[HTTP-TIME] synced via",
                host,
                "%04d-%02d-%02dT%02d:%02d:%02dZ" % (y, mo, d, hh, mm, ss),
            )
            return True
        except Exception as e:
            safe_print("[HTTP-TIME] parse failed:", e)

    safe_print("[TIME] sync failed")
    return False
