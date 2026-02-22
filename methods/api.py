try:
    import ujson as json
except Exception:
    import json


def _join_url(endpoint, path):
    if not endpoint:
        return path or ""
    if not path:
        return endpoint
    if endpoint.endswith("/") and path.startswith("/"):
        return endpoint[:-1] + path
    if (not endpoint.endswith("/")) and (not path.startswith("/")):
        return endpoint + "/" + path
    return endpoint + path


def _legacy_base(url):
    if not url:
        return ""
    idx = url.rfind("/")
    if idx <= 8:
        return url
    return url[:idx]


def build_api_url(cfg, route_key, default_path):
    api_cfg = cfg.get("api", {})
    endpoint = api_cfg.get("endpoint") or api_cfg.get("base") or ""
    routes = api_cfg.get("routes", {}) or {}
    path = routes.get(route_key)
    if not path:
        if route_key == "include":
            path = routes.get("include", default_path)
        elif route_key == "maintain_record":
            path = routes.get("maintain_record") or routes.get("maintainRecord")
            if not path:
                path = default_path
        elif route_key == "crash_report":
            path = routes.get("crash_report") or routes.get("crashReport")
            if not path:
                path = default_path
        else:
            path = default_path

    if endpoint:
        return _join_url(endpoint, path)

    legacy_url = api_cfg.get("url", "")
    if legacy_url:
        if route_key == "include":
            return legacy_url
        base = _legacy_base(legacy_url)
        return _join_url(base, path)

    return _join_url("", path)


def clone_json(value, fallback=None):
    try:
        return json.loads(json.dumps(value))
    except Exception:
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, list):
            return list(value)
        return value if value is not None else fallback
