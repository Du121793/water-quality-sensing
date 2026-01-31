from ..forms import parse_form
from ..views import render_login_page, render_password_page
from ..security import _generate_salt_hex, _hash_password


# 處理登入流程
def handle_login(server, method, body, is_authed, has_password):
    if method == "GET":
        if is_authed and has_password:
            server._redirect(server._client, server._base_path + "/")
            return True
        html = render_login_page(server._base_path, server._message, not has_password)
        server._message = ""
        server._send_response(server._client, 200, {"Content-Type": "text/html"}, html)
        return True

    if method == "POST":
        form = parse_form(body)
        if not has_password:
            pwd = form.get("password", "")
            pwd2 = form.get("password2", "")
            if not pwd or pwd != pwd2:
                server._message = "密碼不一致"
                html = render_login_page(server._base_path, server._message, True)
                server._message = ""
                server._send_response(
                    server._client, 200, {"Content-Type": "text/html"}, html
                )
                return True
            salt_hex = _generate_salt_hex()
            server._cfg["admin"]["password_salt"] = salt_hex
            server._cfg["admin"]["password_hash"] = _hash_password(pwd, salt_hex)
            server._save_config(server._cfg)
            server._log("Admin password set")
            server._message = "密碼已設定，請登入"
            html = render_login_page(server._base_path, server._message, False)
            server._message = ""
            server._send_response(
                server._client, 200, {"Content-Type": "text/html"}, html
            )
            return True

        pwd = form.get("password", "")
        salt_hex = server._cfg["admin"]["password_salt"]
        pwd_hash = _hash_password(pwd, salt_hex) if pwd else ""
        if pwd_hash != server._cfg["admin"]["password_hash"]:
            server._message = "密碼錯誤"
            server._log("Admin login failed")
            html = render_login_page(server._base_path, server._message, False)
            server._message = ""
            server._send_response(
                server._client, 200, {"Content-Type": "text/html"}, html
            )
            return True

        token = server._new_session()
        server._log("Admin login success")
        headers = {
            "Set-Cookie": "SID={}; Max-Age={}; Path={}; HttpOnly".format(
                token, server._session_ttl_s, server._base_path
            ),
            "Location": server._base_path + "/",
        }
        server._send_response(server._client, 302, headers, "")
        return True

    return False


# 處理登出流程
def handle_logout(server):
    server._clear_session()
    server._log("Admin logout")
    headers = {
        "Set-Cookie": "SID=; Max-Age=0; Path={}; HttpOnly".format(server._base_path),
        "Location": server._base_path + "/login",
    }
    server._send_response(server._client, 302, headers, "")
    return True


# 處理修改密碼流程
def handle_password(server, method, body):
    if method == "GET":
        html = render_password_page(server._base_path, server._message)
        server._message = ""
        server._send_response(server._client, 200, {"Content-Type": "text/html"}, html)
        return True

    if method == "POST":
        form = parse_form(body)
        current_pwd = form.get("current_password", "")
        new_pwd = form.get("new_password", "")
        new_pwd2 = form.get("new_password2", "")

        if not new_pwd or new_pwd != new_pwd2:
            server._message = "新密碼不一致"
            html = render_password_page(server._base_path, server._message)
            server._message = ""
            server._send_response(server._client, 200, {"Content-Type": "text/html"}, html)
            return True

        if server._has_password():
            salt_hex = server._cfg["admin"]["password_salt"]
            pwd_hash = _hash_password(current_pwd, salt_hex) if current_pwd else ""
            if pwd_hash != server._cfg["admin"]["password_hash"]:
                server._message = "當前密碼錯誤"
                html = render_password_page(server._base_path, server._message)
                server._message = ""
                server._send_response(
                    server._client, 200, {"Content-Type": "text/html"}, html
                )
                return True

        salt_hex = _generate_salt_hex()
        server._cfg["admin"]["password_salt"] = salt_hex
        server._cfg["admin"]["password_hash"] = _hash_password(new_pwd, salt_hex)
        server._save_config(server._cfg)
        server._log("Admin password updated")
        server._message = "密碼已更新，請重新登入"
        server._clear_session()
        server._redirect(server._client, server._base_path + "/login")
        return True

    return False
