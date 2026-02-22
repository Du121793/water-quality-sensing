from .common import _to_int



# 建立 API 表單欄位
def build_api_fields(cfg):
    api_cfg = cfg.get("api", {})
    endpoint = api_cfg.get("endpoint", "")
    routes = api_cfg.get("routes", {}) or {}
    if not endpoint:
        legacy_url = api_cfg.get("url", "")
        if legacy_url:
            idx = legacy_url.rfind("/")
            endpoint = legacy_url[:idx] if idx > 8 else legacy_url
    headers = api_cfg.get("headers", {})
    return [
        {"type": "section", "label": "API 設定"},
        {
            "label": "API 數據發送節點",
            "name": "api_endpoint",
            "value": endpoint,
            "input": "text",
        },
        {
            "label": "感測資料發送路由 (/include)",
            "name": "api_route_include",
            "value": routes.get("include", "/include"),
            "input": "text",
        },
        {
            "label": "維護紀錄發送路由 (/maintainRecord)",
            "name": "api_route_maintain_record",
            "value": routes.get("maintain_record", "/maintainRecord"),
            "input": "text",
        },
        {
            "label": "崩潰紀錄發送路由 (/crashReport)",
            "name": "api_route_crash_report",
            "value": routes.get("crash_report", "/crashReport"),
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
            "label": "最大重試次數",
            "name": "api_max_retries",
            "value": api_cfg.get("max_retries", 6),
            "input": "number",
        },
        {
            "label": "SSL 最大重試延遲 (秒)",
            "name": "api_ssl_retry_max_s",
            "value": api_cfg.get("ssl_retry_max_s", 6),
            "input": "number",
        },
    ]


# 套用 API 表單資料



# 套用 API 表單資料
def apply_api_form(cfg, form):
    api_cfg = cfg.get("api", {})
    headers = api_cfg.get("headers", {})

    api_cfg["endpoint"] = form.get("api_endpoint", api_cfg.get("endpoint", ""))
    routes = api_cfg.get("routes", {}) or {}
    routes["include"] = form.get("api_route_include", routes.get("include", "/include"))
    routes["maintain_record"] = form.get(
        "api_route_maintain_record", routes.get("maintain_record", "/maintainRecord")
    )
    routes["crash_report"] = form.get(
        "api_route_crash_report", routes.get("crash_report", "/crashReport")
    )
    api_cfg["routes"] = routes
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
    api_cfg["max_retries"] = _to_int(
        form.get("api_max_retries"),
        api_cfg.get("max_retries", 6),
    )
    api_cfg["ssl_retry_max_s"] = _to_int(
        form.get("api_ssl_retry_max_s"),
        api_cfg.get("ssl_retry_max_s", 6),
    )

    cfg["api"] = api_cfg
    return True, "API 設定已儲存"


# 建立感測器表單欄位
