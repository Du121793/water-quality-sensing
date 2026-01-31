from .common import _split_csv, _to_bool, _to_int



# 建立系統表單欄位
def build_system_fields(cfg):
    intervals = cfg.get("intervals", {})
    watchdog = cfg.get("watchdog", {})
    time_cfg = cfg.get("time", {})
    web_cfg = cfg.get("web", {})
    admin = cfg.get("admin", {})
    payload = cfg.get("payload", {})
    log_cfg = cfg.get("log", {})
    base_path = "/" + web_cfg.get("base_path", "admin").strip("/")
    template_href = base_path + "/template?source=current"
    return [
        {"type": "section", "label": "間隔與監控"},
        {
            "label": "資料間隔 (秒)",
            "name": "intervals_data_interval_s",
            "value": intervals.get("data_interval_s", 30),
            "input": "number",
        },
        {
            "label": "感測取樣間隔 (秒)",
            "name": "intervals_sample_interval_s",
            "value": intervals.get("sample_interval_s", 1),
            "input": "number",
        },
        {
            "label": "WiFi 靜默時間 (秒)",
            "name": "intervals_wifi_quiet_s",
            "value": intervals.get("wifi_quiet_s", 3),
            "input": "number",
        },
        {
            "label": "無成功傳送重置 (ms)",
            "name": "watchdog_no_success_reset_ms",
            "value": watchdog.get("no_success_reset_ms", 300000),
            "input": "number",
        },
        {"type": "section", "label": "時間設定"},
        {
            "label": "時區偏移 (秒)",
            "name": "time_timezone_offset_s",
            "value": time_cfg.get("timezone_offset_s", 0),
            "input": "number",
        },
        {
            "label": "NTP 主機",
            "name": "time_ntp_host",
            "value": time_cfg.get("ntp_host", ""),
            "input": "text",
        },
        {
            "label": "HTTP 時間主機 (逗號分隔)",
            "name": "time_http_hosts",
            "value": ",".join(time_cfg.get("http_hosts", [])),
            "input": "text",
        },
        {"type": "section", "label": "網頁管理"},
        {
            "label": "啟用管理介面",
            "name": "web_enabled",
            "value": "1" if web_cfg.get("enabled") else "0",
            "input": "select",
            "options": [("1", "啟用"), ("0", "停用")],
        },
        {
            "label": "監聽主機",
            "name": "web_host",
            "value": web_cfg.get("host", "0.0.0.0"),
            "input": "text",
        },
        {
            "label": "監聽埠號",
            "name": "web_port",
            "value": web_cfg.get("port", 80),
            "input": "number",
        },
        {
            "label": "路徑名稱",
            "name": "web_base_path",
            "value": web_cfg.get("base_path", "admin"),
            "input": "text",
        },
        {
            "label": "模式",
            "name": "web_mode",
            "value": web_cfg.get("mode", "normal"),
            "input": "select",
            "options": [
                ("normal", "一般"),
                ("dev", "檢修"),
                ("calibration", "校正"),
            ],
        },
        {
            "label": "檢修讀取間隔 (秒)",
            "name": "web_dev_interval_s",
            "value": web_cfg.get("dev_interval_s", 1),
            "input": "number",
        },
        {
            "label": "檢修頁面刷新 (秒)",
            "name": "web_dev_refresh_s",
            "value": web_cfg.get("dev_refresh_s", 1),
            "input": "number",
        },
        {
            "label": "最大請求大小",
            "name": "web_max_request_size",
            "value": web_cfg.get("max_request_size", 8192),
            "input": "number",
        },
        {
            "label": "Session TTL (秒)",
            "name": "admin_session_ttl_s",
            "value": admin.get("session_ttl_s", 1800),
            "input": "number",
        },
        {"type": "section", "label": "管理密碼"},
        {
            "label": "當前密碼",
            "name": "admin_current_password",
            "value": "",
            "input": "password",
            "help": "若未設定過密碼可留空",
        },
        {
            "label": "新密碼",
            "name": "admin_new_password",
            "value": "",
            "input": "password",
            "help": "留空表示不變",
        },
        {
            "label": "再次輸入",
            "name": "admin_new_password2",
            "value": "",
            "input": "password",
        },
        {"type": "section", "label": "Log 設定"},
        {
            "label": "啟用 Log",
            "name": "log_enabled",
            "value": "1" if log_cfg.get("enabled") else "0",
            "input": "select",
            "options": [("1", "啟用"), ("0", "停用")],
        },
        {
            "label": "Log 檔名",
            "name": "log_file",
            "value": log_cfg.get("file", "logs.txt"),
            "input": "text",
        },
        {
            "label": "Log 最大行數",
            "name": "log_max_lines",
            "value": log_cfg.get("max_lines", 30000),
            "input": "number",
        },
        {
            "label": "Log 修剪保留行數",
            "name": "log_trim_to_lines",
            "value": log_cfg.get("trim_to_lines", 10000),
            "input": "number",
        },
        {
            "label": "Log 顯示行數",
            "name": "log_view_lines",
            "value": log_cfg.get("view_lines", 200),
            "input": "number",
        },
        {
            "label": "Log 顯示字數上限",
            "name": "log_view_max_chars",
            "value": log_cfg.get("view_max_chars", 4096),
            "input": "number",
        },
        {"type": "section", "label": "資料回報"},
        {
            "label": "Sensor ID",
            "name": "payload_sensor_id",
            "value": payload.get("sensor_id", "S1"),
            "input": "text",
        },
        {"type": "section", "label": "模板"},
        {"type": "link", "label": "下載目前模板", "href": template_href, "text": "下載"},
        {
            "label": "匯入模板 (JSON)",
            "name": "template_import",
            "value": "",
            "input": "textarea",
            "rows": 10,
            "placeholder": "貼上模板 JSON 後儲存",
            "help": "貼上後儲存會覆蓋現有設定",
        },
    ]


# 套用系統表單資料



# 套用系統表單資料
def apply_system_form(cfg, form):
    intervals = cfg.get("intervals", {})
    watchdog = cfg.get("watchdog", {})
    time_cfg = cfg.get("time", {})
    web_cfg = cfg.get("web", {})
    admin = cfg.get("admin", {})
    payload = cfg.get("payload", {})
    log_cfg = cfg.get("log", {})

    intervals["data_interval_s"] = _to_int(
        form.get("intervals_data_interval_s"),
        intervals.get("data_interval_s", 30),
    )
    intervals["sample_interval_s"] = _to_int(
        form.get("intervals_sample_interval_s"),
        intervals.get("sample_interval_s", 1),
    )
    intervals["wifi_quiet_s"] = _to_int(
        form.get("intervals_wifi_quiet_s"),
        intervals.get("wifi_quiet_s", 3),
    )
    watchdog["no_success_reset_ms"] = _to_int(
        form.get("watchdog_no_success_reset_ms"),
        watchdog.get("no_success_reset_ms", 300000),
    )

    time_cfg["timezone_offset_s"] = _to_int(
        form.get("time_timezone_offset_s"),
        time_cfg.get("timezone_offset_s", 0),
    )
    time_cfg["ntp_host"] = form.get("time_ntp_host", time_cfg.get("ntp_host", ""))
    http_hosts = _split_csv(form.get("time_http_hosts", ""))
    if http_hosts:
        time_cfg["http_hosts"] = http_hosts

    web_cfg["enabled"] = _to_bool(
        form.get("web_enabled"), web_cfg.get("enabled", True)
    )
    web_cfg["host"] = form.get("web_host", web_cfg.get("host", "0.0.0.0"))
    web_cfg["port"] = _to_int(form.get("web_port"), web_cfg.get("port", 80))
    web_cfg["base_path"] = form.get("web_base_path", web_cfg.get("base_path", "admin"))
    web_cfg["mode"] = form.get("web_mode", web_cfg.get("mode", "normal"))
    web_cfg["dev_interval_s"] = _to_int(
        form.get("web_dev_interval_s"), web_cfg.get("dev_interval_s", 1)
    )
    web_cfg["dev_refresh_s"] = _to_int(
        form.get("web_dev_refresh_s"), web_cfg.get("dev_refresh_s", 1)
    )
    web_cfg["max_request_size"] = _to_int(
        form.get("web_max_request_size"), web_cfg.get("max_request_size", 8192)
    )
    admin["session_ttl_s"] = _to_int(
        form.get("admin_session_ttl_s"), admin.get("session_ttl_s", 1800)
    )

    log_cfg["enabled"] = _to_bool(
        form.get("log_enabled"), log_cfg.get("enabled", True)
    )
    log_cfg["file"] = form.get("log_file", log_cfg.get("file", "logs.txt"))
    log_cfg["max_lines"] = _to_int(
        form.get("log_max_lines"), log_cfg.get("max_lines", 30000)
    )
    log_cfg["trim_to_lines"] = _to_int(
        form.get("log_trim_to_lines"), log_cfg.get("trim_to_lines", 10000)
    )
    log_cfg["view_lines"] = _to_int(
        form.get("log_view_lines"), log_cfg.get("view_lines", 200)
    )
    log_cfg["view_max_chars"] = _to_int(
        form.get("log_view_max_chars"), log_cfg.get("view_max_chars", 4096)
    )

    payload["sensor_id"] = form.get(
        "payload_sensor_id", payload.get("sensor_id", "S1")
    )

    cfg["intervals"] = intervals
    cfg["watchdog"] = watchdog
    cfg["time"] = time_cfg
    cfg["web"] = web_cfg
    cfg["admin"] = admin
    cfg["log"] = log_cfg
    cfg["payload"] = payload
    return True, "系統設定已儲存"
