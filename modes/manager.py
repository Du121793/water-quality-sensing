# 取得模式設定
def get_mode_settings(cfg):
    web_cfg = cfg.get("web", {})
    web_mode = web_cfg.get("mode", "normal")
    dev_interval_s = int(web_cfg.get("dev_interval_s", 1))
    dev_refresh_s = int(web_cfg.get("dev_refresh_s", 1))
    send_enabled = web_mode == "normal"

    interval_s = int(cfg.get("intervals", {}).get("data_interval_s", 30))
    if web_mode in ("dev", "calibration"):
        interval_s = dev_interval_s

    refresh_s = dev_refresh_s if web_mode in ("dev", "calibration") else 0
    return {
        "mode": web_mode,
        "send_enabled": send_enabled,
        "interval_s": interval_s,
        "refresh_s": refresh_s,
    }
