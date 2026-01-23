import socket
import time
import ubinascii
import uhashlib
import machine

try:
    import urandom as _urandom
except Exception:
    import random as _urandom

from .admin_forms import (
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
from .admin_views import (
    render_form_page,
    render_log_page,
    render_login_page,
    render_status_page,
)


# 取得隨機位元組
def _rand_bytes(length):
    out = []
    for _ in range(length):
        try:
            out.append(_urandom.getrandbits(8))
        except Exception:
            out.append(_urandom.randrange(256))
    return bytes(out)


# 產生密碼雜湊
def _hash_password(password, salt_hex):
    salt = ubinascii.unhexlify(salt_hex.encode())
    h = uhashlib.sha256()
    h.update(salt)
    h.update(password.encode())
    return ubinascii.hexlify(h.digest()).decode()


# 取得隨機 Salt（Hex）
def _generate_salt_hex():
    return ubinascii.hexlify(_rand_bytes(16)).decode()


# 檢查 Session 是否過期
def _session_expired(expires_ms):
    return time.ticks_diff(time.ticks_ms(), expires_ms) >= 0


# 取得 HTTP 狀態文字
def _status_text(code):
    mapping = {
        200: "OK",
        302: "Found",
        400: "Bad Request",
        404: "Not Found",
    }
    return mapping.get(code, "OK")


class AdminServer:
    # 初始化管理介面伺服器
    def __init__(self, cfg, status, save_config_fn, logger=None):
        self._cfg = cfg
        self._status = status
        self._save_config = save_config_fn
        self._logger = logger
        self._session_token = None
        self._session_expires_ms = 0
        self._message = ""
        self._restart_required = False
        self._reset_prompt = False
        self._apply_runtime_config()

        self._sock = socket.socket()
        self._sock.bind((self._cfg["web"]["host"], self._cfg["web"]["port"]))
        self._sock.listen(1)
        self._sock.settimeout(0)
        self._log(
            "Web server started: {}:{}{}".format(
                self._cfg["web"]["host"],
                self._cfg["web"]["port"],
                self._base_path,
            )
        )

    # 寫入 Log 訊息
    def _log(self, message):
        if self._logger:
            self._logger.log(message)

    # 套用設定到記憶體
    def _apply_runtime_config(self):
        self._base_path = "/" + self._cfg["web"]["base_path"].strip("/")
        self._session_ttl_s = int(self._cfg["admin"]["session_ttl_s"])
        self._max_request_size = int(self._cfg["web"]["max_request_size"])

    # 產生 Session Token
    def _new_session(self):
        token = ubinascii.hexlify(_rand_bytes(16)).decode()
        self._session_token = token
        self._session_expires_ms = time.ticks_add(
            time.ticks_ms(), self._session_ttl_s * 1000
        )
        return token

    # 清除 Session
    def _clear_session(self):
        self._session_token = None
        self._session_expires_ms = 0

    # 檢查是否已登入
    def _is_authed(self, headers):
        if not self._session_token:
            return False
        if _session_expired(self._session_expires_ms):
            self._clear_session()
            return False
        cookie = headers.get("Cookie", "")
        for part in cookie.split(";"):
            part = part.strip()
            if part.startswith("SID="):
                return part[4:] == self._session_token
        return False

    # 取得密碼是否已設定
    def _has_password(self):
        admin_cfg = self._cfg.get("admin", {})
        return bool(admin_cfg.get("password_hash")) and bool(
            admin_cfg.get("password_salt")
        )

    # 讀取 HTTP 請求
    def _read_request(self, client):
        data = b""
        while b"\r\n\r\n" not in data:
            try:
                chunk = client.recv(512)
            except OSError:
                return None
            if not chunk:
                break
            data += chunk
            if len(data) > self._max_request_size:
                return None

        if b"\r\n\r\n" in data:
            header, body = data.split(b"\r\n\r\n", 1)
        else:
            header, body = data, b""

        lines = header.decode("utf-8", "ignore").split("\r\n")
        if not lines or len(lines[0].split()) < 2:
            return None
        method, path = lines[0].split()[:2]
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip()] = value.strip()

        content_length = int(headers.get("Content-Length", "0") or 0)
        if content_length > self._max_request_size:
            return None
        while len(body) < content_length:
            try:
                body += client.recv(content_length - len(body))
            except OSError:
                return None

        return method, path, headers, body.decode("utf-8", "ignore")

    # 回傳 HTTP 內容
    def _send_response(self, client, status, headers, body):
        if body is None:
            body = ""
        if "Connection" not in headers:
            headers["Connection"] = "close"
        body_bytes = body.encode("utf-8")
        header_lines = ["HTTP/1.1 {} {}".format(status, _status_text(status))]
        for key, value in headers.items():
            header_lines.append("{}: {}".format(key, value))
        header_lines.append("Content-Length: {}".format(len(body_bytes)))
        header_lines.append("\r\n")
        try:
            client.send("\r\n".join(header_lines).encode("utf-8") + body_bytes)
        except OSError:
            return

    # 回傳重新導向
    def _redirect(self, client, location):
        headers = {"Location": location}
        self._send_response(client, 302, headers, "")

    # 儲存設定並同步記憶體
    def _save_config_data(self):
        self._save_config(self._cfg)
        self._apply_runtime_config()
        self._restart_required = True
        self._reset_prompt = True
        if self._logger:
            self._logger.refresh()

    # 主輪詢處理
    def poll(self):
        try:
            client, _ = self._sock.accept()
        except Exception:
            return

        try:
            client.settimeout(5)
            try:
                req = self._read_request(client)
            except OSError:
                return
            if not req:
                return

            method, path, headers, body = req
            if path == "/":
                self._redirect(client, self._base_path + "/")
                return

            if not path.startswith(self._base_path):
                self._send_response(
                    client, 404, {"Content-Type": "text/plain"}, "Not Found"
                )
                return

            subpath = path[len(self._base_path) :] or "/"
            is_authed = self._is_authed(headers)
            has_password = self._has_password()

            if subpath in ("/login", "/login/"):
                if method == "GET":
                    if is_authed and has_password:
                        self._redirect(client, self._base_path + "/")
                        return
                    html = render_login_page(
                        self._base_path, self._message, not has_password
                    )
                    self._message = ""
                    self._send_response(client, 200, {"Content-Type": "text/html"}, html)
                    return

                if method == "POST":
                    form = parse_form(body)
                    if not has_password:
                        pwd = form.get("password", "")
                        pwd2 = form.get("password2", "")
                        if not pwd or pwd != pwd2:
                            self._message = "密碼不一致"
                            html = render_login_page(
                                self._base_path, self._message, True
                            )
                            self._message = ""
                            self._send_response(
                                client, 200, {"Content-Type": "text/html"}, html
                            )
                            return
                        salt_hex = _generate_salt_hex()
                        self._cfg["admin"]["password_salt"] = salt_hex
                        self._cfg["admin"]["password_hash"] = _hash_password(
                            pwd, salt_hex
                        )
                        self._save_config(self._cfg)
                        self._log("Admin password set")
                        self._message = "密碼已設定，請登入"
                        html = render_login_page(
                            self._base_path, self._message, False
                        )
                        self._message = ""
                        self._send_response(
                            client, 200, {"Content-Type": "text/html"}, html
                        )
                        return
                    pwd = form.get("password", "")
                    salt_hex = self._cfg["admin"]["password_salt"]
                    pwd_hash = _hash_password(pwd, salt_hex) if pwd else ""
                    if pwd_hash != self._cfg["admin"]["password_hash"]:
                        self._message = "密碼錯誤"
                        self._log("Admin login failed")
                        html = render_login_page(
                            self._base_path, self._message, False
                        )
                        self._message = ""
                        self._send_response(
                            client, 200, {"Content-Type": "text/html"}, html
                        )
                        return
                    token = self._new_session()
                    self._log("Admin login success")
                    headers = {
                        "Set-Cookie": "SID={}; Max-Age={}; Path={}; HttpOnly".format(
                            token, self._session_ttl_s, self._base_path
                        ),
                        "Location": self._base_path + "/",
                    }
                    self._send_response(client, 302, headers, "")
                    return

            if subpath in ("/logout", "/logout/"):
                self._clear_session()
                self._log("Admin logout")
                headers = {
                    "Set-Cookie": "SID=; Max-Age=0; Path={}; HttpOnly".format(
                        self._base_path
                    ),
                    "Location": self._base_path + "/login",
                }
                self._send_response(client, 302, headers, "")
                return

            if has_password and not is_authed:
                self._redirect(client, self._base_path + "/login")
                return

            if subpath in ("/", ""):
                html = render_status_page(
                    self._base_path,
                    self._status,
                    self._message,
                    self._restart_required,
                )
                self._message = ""
                self._send_response(client, 200, {"Content-Type": "text/html"}, html)
                return

            if subpath in ("/reset", "/reset/") and method == "POST":
                self._log("Device reset requested")
                self._reset_prompt = False
                self._send_response(
                    client,
                    200,
                    {"Content-Type": "text/html"},
                    render_status_page(
                        self._base_path,
                        self._status,
                        "裝置即將重啟",
                        self._restart_required,
                    ),
                )
                time.sleep(1)
                machine.reset()
                return

            if subpath in ("/reset-dismiss", "/reset-dismiss/") and method == "POST":
                self._reset_prompt = False
                self._message = "已稍後重啟"
                self._redirect(client, self._base_path + "/")
                return

            if subpath.startswith("/wifi"):
                if method == "GET":
                    fields = build_wifi_fields(self._cfg)
                    html = render_form_page(
                        self._base_path,
                        "網路設定",
                        self._base_path + "/wifi",
                        fields,
                        self._message,
                        reset_prompt=self._reset_prompt,
                    )
                    self._message = ""
                    self._send_response(client, 200, {"Content-Type": "text/html"}, html)
                    return
                if method == "POST":
                    form = parse_form(body)
                    ok, msg = apply_wifi_form(self._cfg, form)
                    if ok:
                        self._save_config_data()
                        self._log("Config updated: wifi")
                    self._message = msg
                    fields = build_wifi_fields(self._cfg)
                    html = render_form_page(
                        self._base_path,
                        "網路設定",
                        self._base_path + "/wifi",
                        fields,
                        self._message,
                        reset_prompt=self._reset_prompt,
                    )
                    self._message = ""
                    self._send_response(client, 200, {"Content-Type": "text/html"}, html)
                    return

            if subpath.startswith("/api"):
                if method == "GET":
                    fields = build_api_fields(self._cfg)
                    html = render_form_page(
                        self._base_path,
                        "API 設定",
                        self._base_path + "/api",
                        fields,
                        self._message,
                        reset_prompt=self._reset_prompt,
                    )
                    self._message = ""
                    self._send_response(client, 200, {"Content-Type": "text/html"}, html)
                    return
                if method == "POST":
                    form = parse_form(body)
                    ok, msg = apply_api_form(self._cfg, form)
                    if ok:
                        self._save_config_data()
                        self._log("Config updated: api")
                    self._message = msg
                    fields = build_api_fields(self._cfg)
                    html = render_form_page(
                        self._base_path,
                        "API 設定",
                        self._base_path + "/api",
                        fields,
                        self._message,
                        reset_prompt=self._reset_prompt,
                    )
                    self._message = ""
                    self._send_response(client, 200, {"Content-Type": "text/html"}, html)
                    return

            if subpath.startswith("/sensors"):
                if method == "GET":
                    fields = build_sensor_fields(self._cfg)
                    html = render_form_page(
                        self._base_path,
                        "感測器設定",
                        self._base_path + "/sensors",
                        fields,
                        self._message,
                        reset_prompt=self._reset_prompt,
                    )
                    self._message = ""
                    self._send_response(client, 200, {"Content-Type": "text/html"}, html)
                    return
                if method == "POST":
                    form = parse_form(body)
                    ok, msg = apply_sensor_form(self._cfg, form)
                    if ok:
                        self._save_config_data()
                        self._log("Config updated: sensors")
                    self._message = msg
                    fields = build_sensor_fields(self._cfg)
                    html = render_form_page(
                        self._base_path,
                        "感測器設定",
                        self._base_path + "/sensors",
                        fields,
                        self._message,
                        reset_prompt=self._reset_prompt,
                    )
                    self._message = ""
                    self._send_response(client, 200, {"Content-Type": "text/html"}, html)
                    return

            if subpath.startswith("/system"):
                if method == "GET":
                    fields = build_system_fields(self._cfg)
                    html = render_form_page(
                        self._base_path,
                        "系統設定",
                        self._base_path + "/system",
                        fields,
                        self._message,
                        reset_prompt=self._reset_prompt,
                    )
                    self._message = ""
                    self._send_response(client, 200, {"Content-Type": "text/html"}, html)
                    return
                if method == "POST":
                    form = parse_form(body)
                    ok, msg = apply_system_form(self._cfg, form)
                    if ok:
                        self._save_config_data()
                        self._log("Config updated: system")
                    self._message = msg
                    fields = build_system_fields(self._cfg)
                    html = render_form_page(
                        self._base_path,
                        "系統設定",
                        self._base_path + "/system",
                        fields,
                        self._message,
                        reset_prompt=self._reset_prompt,
                    )
                    self._message = ""
                    self._send_response(client, 200, {"Content-Type": "text/html"}, html)
                    return

            if subpath.startswith("/logs"):
                if method == "GET":
                    lines = self._logger.read_tail() if self._logger else []
                    html = render_log_page(self._base_path, lines, self._message)
                    self._message = ""
                    self._send_response(client, 200, {"Content-Type": "text/html"}, html)
                    return
                if method == "POST":
                    form = parse_form(body)
                    if form.get("action") == "clear" and self._logger:
                        self._logger.clear()
                        self._log("Log cleared")
                        self._message = "Log 已清除"
                    lines = self._logger.read_tail() if self._logger else []
                    html = render_log_page(self._base_path, lines, self._message)
                    self._message = ""
                    self._send_response(client, 200, {"Content-Type": "text/html"}, html)
                    return

            self._send_response(client, 404, {"Content-Type": "text/plain"}, "Not Found")
        finally:
            try:
                client.close()
            except Exception:
                pass
