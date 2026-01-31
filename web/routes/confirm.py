# 取消待確認的更新
def handle_confirm_cancel(server):
    pending = server._pending_save
    server._clear_pending_save()
    if pending and pending.get("path"):
        server._redirect(server._client, server._base_path + pending.get("path"))
    else:
        server._redirect(server._client, server._base_path + "/")
    return True
