from .common import _parse_static_ifcfg, _to_bool, _to_int



# 建立 Wi-Fi 表單欄位
def build_wifi_fields(cfg):
    wifi = cfg.get("wifi", {})
    primary = wifi.get("primary", {})
    backup = wifi.get("backup", {})
    ap_cfg = wifi.get("ap", {})
    return [
        {"type": "section", "label": "主要 Wi-Fi"},
        {
            "label": "主要 SSID",
            "name": "wifi_primary_ssid",
            "value": primary.get("ssid", ""),
            "input": "text",
        },
        {
            "label": "主要密碼",
            "name": "wifi_primary_password",
            "value": primary.get("password", ""),
            "input": "password",
        },
        {"type": "section", "label": "備援 Wi-Fi"},
        {
            "label": "備援 SSID",
            "name": "wifi_backup_ssid",
            "value": backup.get("ssid", ""),
            "input": "text",
        },
        {
            "label": "備援密碼",
            "name": "wifi_backup_password",
            "value": backup.get("password", ""),
            "input": "password",
        },
        {"type": "section", "label": "連線設定"},
        {
            "label": "使用靜態 IP",
            "name": "wifi_use_static_ip",
            "value": "1" if wifi.get("use_static_ip") else "0",
            "input": "select",
            "options": [("1", "啟用"), ("0", "停用")],
        },
        {
            "label": "靜態 IP (ip,mask,gw,dns)",
            "name": "wifi_static_ifcfg",
            "value": ",".join(wifi.get("static_ifcfg", [])),
            "input": "text",
        },
        {
            "label": "最大失敗次數",
            "name": "wifi_max_failures",
            "value": wifi.get("max_failures", 5),
            "input": "number",
        },
        {
            "label": "最大連線嘗試",
            "name": "wifi_max_connection_attempts",
            "value": wifi.get("max_connection_attempts", 10),
            "input": "number",
        },
        {
            "label": "重設門檻",
            "name": "wifi_reset_after_failures",
            "value": wifi.get("reset_after_failures", 3),
            "input": "number",
        },
        {"type": "section", "label": "AP 模式"},
        {
            "label": "AP SSID",
            "name": "wifi_ap_ssid",
            "value": ap_cfg.get("ssid", ""),
            "input": "text",
        },
        {
            "label": "AP 密碼",
            "name": "wifi_ap_password",
            "value": ap_cfg.get("password", ""),
            "input": "password",
            "help": "密碼需 8 字以上，否則為開放模式",
        },
        {
            "label": "AP 頻道",
            "name": "wifi_ap_channel",
            "value": ap_cfg.get("channel", 6),
            "input": "number",
        },
        {
            "label": "AP 隱藏",
            "name": "wifi_ap_hidden",
            "value": "1" if ap_cfg.get("hidden") else "0",
            "input": "select",
            "options": [("1", "啟用"), ("0", "停用")],
        },
        {
            "label": "AP 強制開放",
            "name": "wifi_ap_force_open",
            "value": "1" if ap_cfg.get("force_open") else "0",
            "input": "select",
            "options": [("1", "啟用"), ("0", "停用")],
            "help": "啟用後不使用密碼",
        },
        {
            "label": "AP IP (ip,mask,gw,dns)",
            "name": "wifi_ap_ifcfg",
            "value": ",".join(ap_cfg.get("ifcfg", [])),
            "input": "text",
        },
    ]


# 套用 Wi-Fi 表單資料



# 套用 Wi-Fi 表單資料
def apply_wifi_form(cfg, form):
    wifi = cfg.get("wifi", {})
    primary = wifi.get("primary", {})
    backup = wifi.get("backup", {})
    ap_cfg = wifi.get("ap", {})

    primary["ssid"] = form.get("wifi_primary_ssid", primary.get("ssid", "")).strip()
    primary["password"] = form.get(
        "wifi_primary_password", primary.get("password", "")
    )
    backup["ssid"] = form.get("wifi_backup_ssid", backup.get("ssid", "")).strip()
    backup["password"] = form.get("wifi_backup_password", backup.get("password", ""))

    wifi["primary"] = primary
    wifi["backup"] = backup
    wifi["use_static_ip"] = _to_bool(
        form.get("wifi_use_static_ip"), wifi.get("use_static_ip", False)
    )
    wifi["static_ifcfg"] = _parse_static_ifcfg(
        form.get("wifi_static_ifcfg", ""),
        wifi.get("static_ifcfg", []),
    )
    wifi["max_failures"] = _to_int(
        form.get("wifi_max_failures"), wifi.get("max_failures", 5)
    )
    wifi["max_connection_attempts"] = _to_int(
        form.get("wifi_max_connection_attempts"),
        wifi.get("max_connection_attempts", 10),
    )
    wifi["reset_after_failures"] = _to_int(
        form.get("wifi_reset_after_failures"),
        wifi.get("reset_after_failures", 3),
    )

    ap_cfg["ssid"] = form.get("wifi_ap_ssid", ap_cfg.get("ssid", ""))
    ap_cfg["password"] = form.get("wifi_ap_password", ap_cfg.get("password", ""))
    ap_cfg["channel"] = _to_int(form.get("wifi_ap_channel"), ap_cfg.get("channel", 6))
    ap_cfg["hidden"] = _to_bool(
        form.get("wifi_ap_hidden"), ap_cfg.get("hidden", False)
    )
    ap_cfg["force_open"] = _to_bool(
        form.get("wifi_ap_force_open"), ap_cfg.get("force_open", False)
    )
    ap_cfg["ifcfg"] = _parse_static_ifcfg(
        form.get("wifi_ap_ifcfg", ""),
        ap_cfg.get("ifcfg", []),
    )

    wifi["ap"] = ap_cfg
    cfg["wifi"] = wifi
    return True, "網路設定已儲存"


# 建立 API 表單欄位
