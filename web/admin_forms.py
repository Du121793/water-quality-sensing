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
def _to_int(value, default):
    try:
        return int(value)
    except Exception:
        return default


# 解析浮點數
def _to_float(value, default):
    try:
        return float(value)
    except Exception:
        return default


# 解析逗號分隔字串
def _split_csv(value):
    return [v.strip() for v in value.split(",") if v.strip()]


# 解析 IP 設定
def _parse_static_ifcfg(value, fallback):
    parts = _split_csv(value)
    if len(parts) == 4:
        return parts
    return fallback


# 解析 RGB 陣列
def _parse_rgb(value, fallback):
    parts = _split_csv(value)
    if len(parts) != 3:
        return fallback
    out = []
    for part in parts:
        try:
            out.append(int(part))
        except Exception:
            return fallback
    return out


# 解析布林值
def _to_bool(value, default):
    if value is None:
        return default
    return value in ("1", "true", "True", "on", "yes")


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
def build_api_fields(cfg):
    api_cfg = cfg.get("api", {})
    headers = api_cfg.get("headers", {})
    return [
        {"type": "section", "label": "API 設定"},
        {
            "label": "API URL",
            "name": "api_url",
            "value": api_cfg.get("url", ""),
            "input": "text",
        },
        {
            "label": "Authorization",
            "name": "api_header_authorization",
            "value": headers.get("Authorization", ""),
            "input": "text",
        },
        {
            "label": "Content-Type",
            "name": "api_header_content_type",
            "value": headers.get("Content-Type", "application/json"),
            "input": "text",
        },
        {
            "label": "Connection",
            "name": "api_header_connection",
            "value": headers.get("Connection", "close"),
            "input": "text",
        },
        {
            "label": "POST Timeout (秒)",
            "name": "api_post_timeout_s",
            "value": api_cfg.get("post_timeout_s", 30),
            "input": "number",
        },
        {
            "label": "最大重試間隔 (秒)",
            "name": "api_max_retry_interval_s",
            "value": api_cfg.get("max_retry_interval_s", 5),
            "input": "number",
        },
        {
            "label": "重連 Wi-Fi 前最大重試",
            "name": "api_max_retries_before_wifi_reconnect",
            "value": api_cfg.get("max_retries_before_wifi_reconnect", 3),
            "input": "number",
        },
    ]


# 套用 API 表單資料
def apply_api_form(cfg, form):
    api_cfg = cfg.get("api", {})
    headers = api_cfg.get("headers", {})

    api_cfg["url"] = form.get("api_url", api_cfg.get("url", ""))
    headers["Authorization"] = form.get(
        "api_header_authorization", headers.get("Authorization", "")
    )
    headers["Content-Type"] = form.get(
        "api_header_content_type", headers.get("Content-Type", "application/json")
    )
    headers["Connection"] = form.get(
        "api_header_connection", headers.get("Connection", "close")
    )
    api_cfg["headers"] = headers
    api_cfg["post_timeout_s"] = _to_int(
        form.get("api_post_timeout_s"), api_cfg.get("post_timeout_s", 30)
    )
    api_cfg["max_retry_interval_s"] = _to_int(
        form.get("api_max_retry_interval_s"),
        api_cfg.get("max_retry_interval_s", 5),
    )
    api_cfg["max_retries_before_wifi_reconnect"] = _to_int(
        form.get("api_max_retries_before_wifi_reconnect"),
        api_cfg.get("max_retries_before_wifi_reconnect", 3),
    )

    cfg["api"] = api_cfg
    return True, "API 設定已儲存"


# 建立感測器表單欄位
def build_sensor_fields(cfg):
    adc = cfg.get("adc", {})
    ph = cfg.get("ph", {})
    turb = cfg.get("turbidity", {})
    mq = cfg.get("mq", {})
    ds = cfg.get("ds18b20", {})
    tds = cfg.get("tds", {})
    led = cfg.get("led", {})
    return [
        {"type": "section", "label": "ADC"},
        {
            "label": "ADC 參考電壓",
            "name": "adc_vref",
            "value": adc.get("vref", 3.3),
            "input": "number",
            "step": "0.01",
        },
        {"type": "section", "label": "pH"},
        {"label": "pH 腳位", "name": "ph_pin", "value": ph.get("pin", 0), "input": "number"},
        {"label": "pH 最小值", "name": "ph_min", "value": ph.get("min", 0.0), "input": "number", "step": "0.01"},
        {"label": "pH 最大值", "name": "ph_max", "value": ph.get("max", 14.0), "input": "number", "step": "0.01"},
        {"label": "k25 預設值", "name": "ph_default_k25", "value": ph.get("default_k25", 0.18), "input": "number", "step": "0.001"},
        {"label": "平滑視窗", "name": "ph_smoothing_window", "value": ph.get("smoothing_window", 5), "input": "number"},
        {"label": "平滑係數", "name": "ph_smoothing_factor", "value": ph.get("smoothing_factor", 0.5), "input": "number", "step": "0.01"},
        {"label": "pH 7 參考電壓", "name": "ph_v7_default", "value": ph.get("v7_default", 2.5), "input": "number", "step": "0.001"},
        {"type": "section", "label": "濁度"},
        {"label": "濁度腳位", "name": "turbidity_pin", "value": turb.get("pin", 0), "input": "number"},
        {"label": "空氣閾值", "name": "turbidity_air_threshold", "value": turb.get("air_threshold", 0), "input": "number"},
        {"type": "section", "label": "MQ135 / MQ137"},
        {"label": "MQ135 腳位", "name": "mq_pin_135", "value": mq.get("pin_135", 0), "input": "number"},
        {"label": "MQ137 腳位", "name": "mq_pin_137", "value": mq.get("pin_137", 0), "input": "number"},
        {"type": "section", "label": "DS18B20"},
        {"label": "淺層腳位", "name": "ds18b20_pin_shallow", "value": ds.get("pin_shallow", 0), "input": "number"},
        {"label": "深層腳位", "name": "ds18b20_pin_deep", "value": ds.get("pin_deep", 0), "input": "number"},
        {"type": "section", "label": "TDS"},
        {"label": "TDS 腳位", "name": "tds_pin", "value": tds.get("pin", 0), "input": "number"},
        {"label": "TDS 參考電壓", "name": "tds_vref", "value": tds.get("vref", 3.3), "input": "number", "step": "0.01"},
        {"label": "溫度補償係數", "name": "tds_temp_compensation_factor", "value": tds.get("temp_compensation_factor", 0.5), "input": "number", "step": "0.01"},
        {"label": "TDS K 係數", "name": "tds_k_factor", "value": tds.get("k_factor", 0.5), "input": "number", "step": "0.01"},
        {"type": "section", "label": "LED"},
        {"label": "LED 腳位", "name": "led_pin", "value": led.get("pin", 0), "input": "number"},
        {"label": "LED 數量", "name": "led_num", "value": led.get("num", 1), "input": "number"},
    ]


# 套用感測器表單資料
def apply_sensor_form(cfg, form):
    adc = cfg.get("adc", {})
    ph = cfg.get("ph", {})
    turb = cfg.get("turbidity", {})
    mq = cfg.get("mq", {})
    ds = cfg.get("ds18b20", {})
    tds = cfg.get("tds", {})
    led = cfg.get("led", {})

    adc["vref"] = _to_float(form.get("adc_vref"), adc.get("vref", 3.3))
    ph["pin"] = _to_int(form.get("ph_pin"), ph.get("pin", 0))
    ph["min"] = _to_float(form.get("ph_min"), ph.get("min", 0.0))
    ph["max"] = _to_float(form.get("ph_max"), ph.get("max", 14.0))
    ph["default_k25"] = _to_float(
        form.get("ph_default_k25"), ph.get("default_k25", 0.18)
    )
    ph["smoothing_window"] = _to_int(
        form.get("ph_smoothing_window"), ph.get("smoothing_window", 5)
    )
    ph["smoothing_factor"] = _to_float(
        form.get("ph_smoothing_factor"), ph.get("smoothing_factor", 0.5)
    )
    ph["v7_default"] = _to_float(
        form.get("ph_v7_default"), ph.get("v7_default", 2.5)
    )

    turb["pin"] = _to_int(form.get("turbidity_pin"), turb.get("pin", 0))
    turb["air_threshold"] = _to_int(
        form.get("turbidity_air_threshold"), turb.get("air_threshold", 0)
    )

    mq["pin_135"] = _to_int(form.get("mq_pin_135"), mq.get("pin_135", 0))
    mq["pin_137"] = _to_int(form.get("mq_pin_137"), mq.get("pin_137", 0))

    ds["pin_shallow"] = _to_int(
        form.get("ds18b20_pin_shallow"), ds.get("pin_shallow", 0)
    )
    ds["pin_deep"] = _to_int(
        form.get("ds18b20_pin_deep"), ds.get("pin_deep", 0)
    )

    tds["pin"] = _to_int(form.get("tds_pin"), tds.get("pin", 0))
    tds["vref"] = _to_float(form.get("tds_vref"), tds.get("vref", 3.3))
    tds["temp_compensation_factor"] = _to_float(
        form.get("tds_temp_compensation_factor"),
        tds.get("temp_compensation_factor", 0.5),
    )
    tds["k_factor"] = _to_float(
        form.get("tds_k_factor"), tds.get("k_factor", 0.5)
    )

    led["pin"] = _to_int(form.get("led_pin"), led.get("pin", 0))
    led["num"] = _to_int(form.get("led_num"), led.get("num", 1))

    cfg["adc"] = adc
    cfg["ph"] = ph
    cfg["turbidity"] = turb
    cfg["mq"] = mq
    cfg["ds18b20"] = ds
    cfg["tds"] = tds
    cfg["led"] = led
    return True, "感測器設定已儲存"


# 建立系統表單欄位
def build_system_fields(cfg):
    intervals = cfg.get("intervals", {})
    watchdog = cfg.get("watchdog", {})
    time_cfg = cfg.get("time", {})
    web_cfg = cfg.get("web", {})
    admin = cfg.get("admin", {})
    payload = cfg.get("payload", {})
    log_cfg = cfg.get("log", {})
    return [
        {"type": "section", "label": "間隔與監控"},
        {
            "label": "資料間隔 (秒)",
            "name": "intervals_data_interval_s",
            "value": intervals.get("data_interval_s", 30),
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
        {
            "label": "RGB (r,g,b)",
            "name": "payload_rgb",
            "value": ",".join([str(v) for v in payload.get("rgb", [0, 0, 0])]),
            "input": "text",
        },
    ]


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
    log_cfg["view_lines"] = _to_int(
        form.get("log_view_lines"), log_cfg.get("view_lines", 200)
    )
    log_cfg["view_max_chars"] = _to_int(
        form.get("log_view_max_chars"), log_cfg.get("view_max_chars", 4096)
    )

    payload["sensor_id"] = form.get(
        "payload_sensor_id", payload.get("sensor_id", "S1")
    )
    payload["rgb"] = _parse_rgb(
        form.get("payload_rgb", ""), payload.get("rgb", [0, 0, 0])
    )

    cfg["intervals"] = intervals
    cfg["watchdog"] = watchdog
    cfg["time"] = time_cfg
    cfg["web"] = web_cfg
    cfg["admin"] = admin
    cfg["log"] = log_cfg
    cfg["payload"] = payload
    return True, "系統設定已儲存"
