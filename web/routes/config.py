try:
    import ujson as json
except Exception:
    import json

from ..forms import (
    apply_api_form,
    apply_sensor_form,
    apply_system_form,
    apply_wifi_form,
    build_api_fields,
    build_sensor_fields,
    build_system_fields,
    build_wifi_fields,
    parse_form,
)
from ..views import render_confirm_download_page, render_form_page


# 渲染設定表單
def _render_form(server, title, path, fields):
    html = render_form_page(
        server._base_path,
        title,
        path,
        fields,
        server._message,
        reset_prompt=server._reset_prompt,
    )
    server._message = ""
    server._send_response(server._client, 200, {"Content-Type": "text/html"}, html)


# 顯示更新前下載提示
def _confirm_save(server, subpath, form):
    server._set_pending_save(subpath, form)
    html = render_confirm_download_page(
        server._base_path,
        "更新前是否下載舊設定檔？",
        server._template_download_url(),
    )
    server._send_response(server._client, 200, {"Content-Type": "text/html"}, html)


# 處理網路設定
def handle_wifi(server, method, body):
    if method == "GET":
        fields = build_wifi_fields(server._cfg)
        _render_form(server, "網路設定", server._base_path + "/wifi", fields)
        return True
    if method == "POST":
        form = parse_form(body)
        _confirm_save(server, "/wifi", form)
        return True
    return False


# 處理 API 設定
def handle_api(server, method, body):
    if method == "GET":
        fields = build_api_fields(server._cfg)
        _render_form(server, "API 設定", server._base_path + "/api", fields)
        return True
    if method == "POST":
        form = parse_form(body)
        _confirm_save(server, "/api", form)
        return True
    return False


# 處理感測器設定
def handle_sensors(server, method, body):
    if method == "GET":
        fields = build_sensor_fields(server._cfg)
        _render_form(server, "感測器設定", server._base_path + "/sensors", fields)
        return True
    if method == "POST":
        form = parse_form(body)
        _confirm_save(server, "/sensors", form)
        return True
    return False


# 處理系統設定
def handle_system(server, method, body):
    if method == "GET":
        fields = build_system_fields(server._cfg)
        _render_form(server, "系統設定", server._base_path + "/system", fields)
        return True
    if method == "POST":
        form = parse_form(body)
        _confirm_save(server, "/system", form)
        return True
    return False


# 套用待確認的設定更新
def apply_pending_save(server):
    pending = server._pending_save
    if not pending:
        server._redirect(server._client, server._base_path + "/")
        return True
    server._clear_pending_save()

    subpath = pending.get("path", "")
    form = pending.get("form", {})

    if subpath.startswith("/wifi"):
        ok, msg = apply_wifi_form(server._cfg, form)
        if ok:
            server._save_config_data()
            server._log("Config updated: wifi")
        server._message = msg
        fields = build_wifi_fields(server._cfg)
        _render_form(server, "網路設定", server._base_path + "/wifi", fields)
        return True

    if subpath.startswith("/api"):
        ok, msg = apply_api_form(server._cfg, form)
        if ok:
            server._save_config_data()
            server._log("Config updated: api")
        server._message = msg
        fields = build_api_fields(server._cfg)
        _render_form(server, "API 設定", server._base_path + "/api", fields)
        return True

    if subpath.startswith("/sensors"):
        ok, msg = apply_sensor_form(server._cfg, form)
        if ok:
            server._save_config_data()
            server._log("Config updated: sensors")
        server._message = msg
        fields = build_sensor_fields(server._cfg)
        _render_form(server, "感測器設定", server._base_path + "/sensors", fields)
        return True

    if subpath.startswith("/system"):
        template_import = (form.get("template_import") or "").strip()
        if template_import:
            try:
                new_cfg = json.loads(template_import)
                if not isinstance(new_cfg, dict):
                    raise ValueError("invalid template")
            except Exception:
                server._message = "模板格式錯誤，請確認 JSON"
                fields = build_system_fields(server._cfg)
                _render_form(server, "系統設定", server._base_path + "/system", fields)
                return True

            server._cfg = new_cfg
            server._save_config_data()
            server._log("Config updated: template import")
            server._message = "模板已匯入"
            fields = build_system_fields(server._cfg)
            _render_form(server, "系統設定", server._base_path + "/system", fields)
            return True

        ok_pwd, pwd_msg, pwd_changed = server._apply_password_change(form)
        if not ok_pwd:
            server._message = pwd_msg
            fields = build_system_fields(server._cfg)
            _render_form(server, "系統設定", server._base_path + "/system", fields)
            return True

        ok, msg = apply_system_form(server._cfg, form)
        if ok:
            server._save_config_data()
            server._log("Config updated: system")
        server._message = msg

        if pwd_changed:
            server._clear_session()
            server._message = pwd_msg
            server._redirect(server._client, server._base_path + "/login")
            return True

        fields = build_system_fields(server._cfg)
        _render_form(server, "系統設定", server._base_path + "/system", fields)
        return True

    server._redirect(server._client, server._base_path + "/")
    return True
