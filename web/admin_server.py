import socket
import time
import ubinascii
import machine
import json

from .routes import dispatch_request
from .security import _generate_salt_hex, _hash_password, _rand_bytes
from .http_utils import read_request, send_response, redirect


# 檢查 Session 是否過期
def _session_expired(expires_ms):
    return time.ticks_diff(time.ticks_ms(), expires_ms) >= 0


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
        self._pending_save = None
        self._query = ""
        self._apply_runtime_config()

        self._sock = socket.socket()
        # 使用 getaddrinfo 取得可用綁定位址
        try:
            addr = socket.getaddrinfo(
                self._cfg["web"]["host"], self._cfg["web"]["port"]
            )[0][-1]
        except Exception:
            addr = (self._cfg["web"]["host"], self._cfg["web"]["port"])
        self._sock.bind(addr)
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
        return read_request(client, self._max_request_size)

    # 回傳 HTTP 內容
    def _send_response(self, client, status, headers, body):
        send_response(client, status, headers, body)

    # 回傳重新導向
    def _redirect(self, client, location):
        redirect(client, location)

    # 儲存設定並同步記憶體
    def _save_config_data(self):
        self._save_config(self._cfg)
        self._apply_runtime_config()
        self._restart_required = True
        self._reset_prompt = True
        if self._logger:
            self._logger.refresh()

    # 複製設定供備份
    def _clone_config(self):
        try:
            return json.loads(json.dumps(self._cfg))
        except Exception:
            try:
                return dict(self._cfg)
            except Exception:
                return {}

    # 套用密碼更新（系統頁）
    def _apply_password_change(self, form):
        current_pwd = form.get("admin_current_password", "")
        new_pwd = form.get("admin_new_password", "")
        new_pwd2 = form.get("admin_new_password2", "")

        if not new_pwd and not new_pwd2:
            return True, "", False

        if not new_pwd or new_pwd != new_pwd2:
            return False, "新密碼不一致", False

        if self._has_password():
            salt_hex = self._cfg["admin"]["password_salt"]
            pwd_hash = _hash_password(current_pwd, salt_hex) if current_pwd else ""
            if pwd_hash != self._cfg["admin"]["password_hash"]:
                return False, "當前密碼錯誤", False

        salt_hex = _generate_salt_hex()
        self._cfg["admin"]["password_salt"] = salt_hex
        self._cfg["admin"]["password_hash"] = _hash_password(new_pwd, salt_hex)
        return True, "密碼已更新，請重新登入", True

    # 取得模板下載連結
    def _template_download_url(self):
        return self._base_path + "/template?source=current"

    # 設定暫存更新
    def _set_pending_save(self, subpath, form):
        self._pending_save = {"path": subpath, "form": form}

    # 清除暫存更新
    def _clear_pending_save(self):
        self._pending_save = None

    # 主輪詢處理
    def poll(self):
        try:
            client, _ = self._sock.accept()
        except Exception:
            return

        self._client = client
        try:
            client.settimeout(5)
            try:
                req = self._read_request(client)
            except OSError:
                return
            if not req:
                return

            method, path, headers, body = req
            self._query = ""
            if "?" in path:
                path_only, self._query = path.split("?", 1)
            else:
                path_only = path
            if path == "/":
                self._redirect(client, self._base_path + "/")
                return

            # 允許直接從根路徑存取 /status
            if path_only in ("/status", "/status/") and method == "GET":
                handled = dispatch_request(self, method, "/status", headers, body)
                if not handled:
                    self._send_response(
                        client, 404, {"Content-Type": "text/plain"}, "Not Found"
                    )
                return

            if not path_only.startswith(self._base_path):
                self._send_response(
                    client, 404, {"Content-Type": "text/plain"}, "Not Found"
                )
                return

            subpath = path_only[len(self._base_path) :] or "/"
            handled = dispatch_request(self, method, subpath, headers, body)
            if not handled:
                self._send_response(
                    client, 404, {"Content-Type": "text/plain"}, "Not Found"
                )
        finally:
            try:
                client.close()
            except Exception:
                pass
