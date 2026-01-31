from .auth import handle_login, handle_logout, handle_password
from .config import (
    apply_pending_save,
    handle_api,
    handle_sensors,
    handle_system,
    handle_wifi,
)
from .logs import handle_logs, handle_logs_download
from .status import (
    handle_reset,
    handle_reset_dismiss,
    handle_status,
    handle_status_data,
    handle_status_json,
)
from .template import handle_template_download
from .calibration import handle_calibration, handle_calibration_data
from .confirm import handle_confirm_cancel


# 派發路由處理
def dispatch_request(server, method, subpath, headers, body):
    is_authed = server._is_authed(headers)
    has_password = server._has_password()

    if subpath in ("/login", "/login/"):
        return handle_login(server, method, body, is_authed, has_password)

    if subpath in ("/logout", "/logout/"):
        return handle_logout(server)

    if subpath in ("/status", "/status/") and method == "GET":
        return handle_status_json(server)

    if not is_authed:
        server._redirect(server._client, server._base_path + "/login")
        return True

    if subpath in ("/template", "/template/") and method == "GET":
        return handle_template_download(server)

    if subpath in ("/confirm-save", "/confirm-save/") and method == "POST":
        return apply_pending_save(server)

    if subpath in ("/confirm-cancel", "/confirm-cancel/") and method == "POST":
        return handle_confirm_cancel(server)

    if subpath in ("/password", "/password/"):
        return handle_password(server, method, body)

    if subpath in ("/", ""):
        web_mode = server._cfg.get("web", {}).get("mode", "normal")
        if web_mode == "calibration":
            server._redirect(server._client, server._base_path + "/calibration")
            return True
        return handle_status(server)

    if subpath in ("/status/data", "/status/data/") and method == "GET":
        return handle_status_data(server)

    if subpath in ("/reset", "/reset/") and method == "POST":
        return handle_reset(server)

    if subpath in ("/reset-dismiss", "/reset-dismiss/") and method == "POST":
        return handle_reset_dismiss(server)

    if subpath.startswith("/wifi"):
        return handle_wifi(server, method, body)

    if subpath.startswith("/api"):
        return handle_api(server, method, body)

    if subpath.startswith("/sensors"):
        return handle_sensors(server, method, body)

    if subpath.startswith("/system"):
        return handle_system(server, method, body)

    if subpath.startswith("/logs"):
        if subpath in ("/logs/download", "/logs/download/") and method == "GET":
            return handle_logs_download(server)
        return handle_logs(server, method, body)

    if subpath in ("/calibration/data", "/calibration/data/") and method == "GET":
        return handle_calibration_data(server)

    if subpath.startswith("/calibration"):
        return handle_calibration(server, method, body)

    return False
