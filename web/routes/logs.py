try:
    import uos as os
except Exception:
    import os

from ..forms import parse_form
from ..views import render_log_page


# 處理 Log 頁面
def handle_logs(server, method, body):
    query = getattr(server, "_query", "") or ""
    query_form = parse_form(query)
    try:
        page = int(query_form.get("page", "0"))
    except Exception:
        page = 0
    if page < 0:
        page = 0

    if method == "GET":
        if server._logger:
            lines, has_next, page = server._logger.read_tail_page(
                page,
                lines=server._logger.get_view_lines(),
                max_chars=server._logger.get_view_max_chars(),
            )
        else:
            lines, has_next = [], False
        html = render_log_page(
            server._base_path, lines, server._message, page, has_next
        )
        server._message = ""
        server._send_response(server._client, 200, {"Content-Type": "text/html"}, html)
        return True

    if method == "POST":
        form = parse_form(body)
        if form.get("action") == "clear" and server._logger:
            server._logger.clear()
            server._log("Log cleared")
            server._message = "Log 已清除"
            page = 0
        if server._logger:
            lines, has_next, page = server._logger.read_tail_page(
                page,
                lines=server._logger.get_view_lines(),
                max_chars=server._logger.get_view_max_chars(),
            )
        else:
            lines, has_next = [], False
        html = render_log_page(
            server._base_path, lines, server._message, page, has_next
        )
        server._message = ""
        server._send_response(server._client, 200, {"Content-Type": "text/html"}, html)
        return True

    return False


# 下載完整 Log 檔案
def handle_logs_download(server):
    if not server._logger:
        server._send_response(
            server._client, 404, {"Content-Type": "text/plain"}, "Log not found"
        )
        return True

    log_path = getattr(server._logger, "_file", "logs.txt")
    try:
        stat = os.stat(log_path)
    except Exception:
        server._send_response(
            server._client, 404, {"Content-Type": "text/plain"}, "Log not found"
        )
        return True

    size = 0
    try:
        size = stat[6]
    except Exception:
        try:
            size = stat[0]
        except Exception:
            size = 0

    filename = log_path.split("/")[-1].split("\\")[-1]
    headers = [
        "HTTP/1.1 200 OK",
        "Content-Type: text/plain; charset=utf-8",
        "Content-Disposition: attachment; filename=\"{}\"".format(filename),
        "Content-Length: {}".format(size),
        "Connection: close",
        "\r\n",
    ]
    try:
        server._client.send("\r\n".join(headers).encode("utf-8"))
        with open(log_path, "rb") as f:
            while True:
                chunk = f.read(512)
                if not chunk:
                    break
                server._client.send(chunk)
    except OSError:
        return True
    return True
