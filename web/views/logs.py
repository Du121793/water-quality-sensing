from .layout import _html_escape


# 產生精簡 Log 頁版型（避免配置過大記憶體）
def _render_log_layout(base_path, title, content, message, refresh_s=0):
    message_html = ""
    if message:
        message_html = "<p><strong>{}</strong></p>".format(_html_escape(message))

    refresh_meta = ""
    if refresh_s:
        refresh_meta = '<meta http-equiv="refresh" content="{}" />'.format(
            int(refresh_s)
        )

    return """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  {refresh}
  <title>{title}</title>
</head>
<body>
  <h1>{title}</h1>
  {message}
  {content}
  <p><a href="{home}">回到首頁</a></p>
</body>
</html>""".format(
        title=_html_escape(title),
        content=content,
        message=message_html,
        home=base_path + "/",
        refresh=refresh_meta,
    )


# 顯示 Log 頁面
def render_log_page(base_path, lines, message, page, has_next):
    if not lines:
        log_text = "尚無紀錄"
    else:
        log_text = "\n".join(lines)

    max_chars = 2048
    truncated = False
    if len(log_text) > max_chars:
        log_text = log_text[-max_chars:]
        truncated = True

    log_note = ""
    if truncated:
        log_note = "<p>Log 已截斷，請調整顯示行數或字數上限</p>"

    nav = []
    if page > 0:
        nav.append(
            '<a href="{}">上一頁</a>'.format(
                base_path + "/logs?page={}".format(page - 1)
            )
        )
    if has_next:
        nav.append(
            '<a href="{}">下一頁</a>'.format(
                base_path + "/logs?page={}".format(page + 1)
            )
        )
    nav_html = " | ".join(nav)
    if nav_html:
        nav_html = "<p>{}</p>".format(nav_html)

    content = """{note}
<form method="post" action="{reset_action}">
  <button type="submit">重啟裝置</button>
</form>
<p><a href="{download_action}">下載 Log</a></p>
<form method="post" action="{log_action}">
  <input type="hidden" name="action" value="clear" />
  <button type="submit">清除紀錄</button>
  <pre style="white-space: pre-wrap; font-size: 12px; background: #111827; color: #f9fafb; padding: 10px; border-radius: 6px;">{log_text}</pre>
</form>
{nav}""".format(
        reset_action=base_path + "/reset",
        download_action=base_path + "/logs/download",
        log_action=base_path + "/logs?page={}".format(page),
        log_text=_html_escape(log_text),
        note=log_note,
        nav=nav_html,
    )
    refresh_s = 5 if page == 0 else 0
    return _render_log_layout(
        base_path, "LOG 紀錄", content, message, refresh_s=refresh_s
    )
