try:
    import ujson as json
except Exception:
    import json


# 下載目前設定模板
def handle_template_download(server):
    try:
        payload = json.dumps(server._cfg)
    except TypeError:
        payload = json.dumps(server._cfg, ensure_ascii=True)
    headers = {
        "Content-Type": "application/json",
        "Content-Disposition": "attachment; filename=config.json",
    }
    server._send_response(server._client, 200, headers, payload)
    return True
