# 取得 HTTP 狀態文字
def _status_text(code):
    mapping = {
        200: "OK",
        302: "Found",
        400: "Bad Request",
        404: "Not Found",
    }
    return mapping.get(code, "OK")


# 讀取 HTTP 請求
def read_request(client, max_request_size):
    data = b""
    while b"\r\n\r\n" not in data:
        try:
            chunk = client.recv(512)
        except OSError:
            return None
        if not chunk:
            break
        data += chunk
        if len(data) > max_request_size:
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
    if content_length > max_request_size:
        return None
    while len(body) < content_length:
        try:
            body += client.recv(content_length - len(body))
        except OSError:
            return None

    return method, path, headers, body.decode("utf-8", "ignore")


# 回傳 HTTP 內容
def send_response(client, status, headers, body):
    if body is None:
        body = ""
    if headers is None:
        headers = {}
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
def redirect(client, location):
    headers = {"Location": location}
    send_response(client, 302, headers, "")
