import gc
import time


# 轉換為安全的 HTML 文字
def _html_escape(text, escape_quotes=True):
    text = str(text)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    if escape_quotes:
        text = text.replace('"', "&quot;")
    return text


# 渲染整體版面
def _render_layout(base_path, title, content, active, message, show_nav=True):
    nav_items = [
        ("狀態", base_path + "/"),
        ("網路", base_path + "/wifi"),
        ("API", base_path + "/api"),
        ("感測器", base_path + "/sensors"),
        ("系統", base_path + "/system"),
        ("LOG", base_path + "/logs"),
    ]
    nav_html = ""
    if show_nav:
        links = []
        for name, href in nav_items:
            cls = "nav-item active" if active == href else "nav-item"
            links.append('<a class="{}" href="{}">{}</a>'.format(cls, href, name))
        links.append('<a class="nav-item" href="{}">登出</a>'.format(base_path + "/logout"))
        nav_html = '<aside class="nav">{}</aside>'.format("".join(links))

    message_html = ""
    if message:
        message_html = '<div class="flash">{}</div>'.format(_html_escape(message))

    return """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    :root {{
      --bg: #f3f4f6;
      --nav: #1f2937;
      --nav-accent: #f59e0b;
      --card: #ffffff;
      --border: #e5e7eb;
      --text: #111827;
      --muted: #6b7280;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Trebuchet MS", "Georgia", serif;
      background: var(--bg);
      color: var(--text);
    }}
    .shell {{ display: flex; min-height: 100vh; }}
    .nav {{
      width: 200px;
      padding: 16px 12px;
      background: var(--nav);
    }}
    .nav-item {{
      display: block;
      padding: 8px 10px;
      border-radius: 6px;
      color: #f3f4f6;
      text-decoration: none;
      margin-bottom: 6px;
      font-size: 14px;
    }}
    .nav-item.active {{
      background: var(--nav-accent);
      color: #111827;
      font-weight: bold;
    }}
    .main {{ flex: 1; padding: 20px; }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 18px;
    }}
    h1 {{ margin: 0 0 12px; font-size: 20px; }}
    h2 {{ margin: 16px 0 8px; font-size: 16px; }}
    .muted {{ color: var(--muted); font-size: 12px; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 8px;
    }}
    th, td {{
      border-bottom: 1px solid var(--border);
      padding: 8px;
      text-align: left;
      font-size: 13px;
    }}
    th {{ color: var(--muted); font-weight: normal; width: 220px; }}
    input[type="text"], input[type="number"], input[type="password"] {{
      width: 100%;
      padding: 6px 8px;
      border-radius: 6px;
      border: 1px solid var(--border);
      font-size: 13px;
    }}
    select {{
      width: 100%;
      padding: 6px 8px;
      border-radius: 6px;
      border: 1px solid var(--border);
      font-size: 13px;
      background: #ffffff;
    }}
    input[type="checkbox"] {{ transform: scale(1.1); }}
    .btn {{
      display: inline-block;
      margin-top: 12px;
      padding: 8px 14px;
      border-radius: 6px;
      border: none;
      background: var(--nav-accent);
      color: #111827;
      font-weight: bold;
    }}
    .btn.secondary {{
      background: #e5e7eb;
      color: #111827;
    }}
    .actions {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 12px;
    }}
    .prompt {{
      background: #fff7ed;
      border: 1px solid #fed7aa;
      color: #9a3412;
      padding: 8px 10px;
      border-radius: 6px;
      margin-bottom: 12px;
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
    }}
    .prompt form {{ margin: 0; }}
    tr.section th {{
      background: #f8fafc;
      color: #111827;
      font-weight: bold;
      border-top: 1px solid var(--border);
    }}
    .flash {{
      background: #eef2ff;
      border: 1px solid #c7d2fe;
      color: #1e3a8a;
      padding: 8px 10px;
      border-radius: 6px;
      margin-bottom: 12px;
      font-size: 13px;
    }}
    .log {{
      background: #111827;
      color: #f9fafb;
      padding: 10px;
      border-radius: 8px;
      font-size: 12px;
      white-space: pre-wrap;
      max-height: 360px;
      overflow: auto;
    }}
    @media (max-width: 768px) {{
      .shell {{ flex-direction: column; }}
      .nav {{ width: 100%; display: flex; flex-wrap: wrap; gap: 6px; }}
      .nav-item {{ flex: 1 1 auto; text-align: center; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    {nav}
    <main class="main">
      <div class="card">
        <h1>{title}</h1>
        {message}
        {content}
      </div>
    </main>
  </div>
</body>
</html>""".format(
        title=_html_escape(title),
        nav=nav_html,
        content=content,
        message=message_html,
    )


# 顯示登入/設定密碼頁面
def render_login_page(base_path, message, is_init):
    if is_init:
        title = "初始化管理密碼"
        content = """<form method="post" action="{base}/login">
  <p class="muted">第一次使用請設定管理密碼</p>
  <table>
    <tr><th>新密碼</th><td><input type="password" name="password" /></td></tr>
    <tr><th>再次輸入</th><td><input type="password" name="password2" /></td></tr>
  </table>
  <button class="btn" type="submit">設定密碼</button>
</form>""".format(
            base=base_path
        )
    else:
        title = "管理員登入"
        content = """<form method="post" action="{base}/login">
  <p class="muted">請輸入管理密碼</p>
  <table>
    <tr><th>密碼</th><td><input type="password" name="password" /></td></tr>
  </table>
  <button class="btn" type="submit">登入</button>
</form>""".format(
            base=base_path
        )
    return _render_layout(base_path, title, content, "", message, show_nav=False)


# 顯示狀態頁面
def render_status_page(base_path, status, message, restart_required):
    uptime_ms = time.ticks_diff(time.ticks_ms(), status.get("boot_ms", 0))
    uptime_s = int(uptime_ms / 1000)
    uptime = "{}h {}m {}s".format(
        uptime_s // 3600, (uptime_s % 3600) // 60, uptime_s % 60
    )
    wifi = "已連線" if status.get("wifi_connected") else "未連線"
    ip = status.get("ip") or "-"
    mode = status.get("wifi_mode") or "-"
    last_send = status.get("last_send_iso") or "-"
    last_http = status.get("last_http_code")
    last_http = last_http if last_http is not None else "-"
    last_error = status.get("last_error") or "-"
    mem_free = gc.mem_free()

    rows = [
        ("模式", mode),
        ("Wi-Fi", wifi),
        ("IP", ip),
        ("Uptime", uptime),
        ("記憶體 (bytes)", mem_free),
        ("最後傳送時間", last_send),
        ("最後 HTTP Code", last_http),
        ("最後錯誤", last_error),
    ]
    stat_html = "".join(
        ["<tr><th>{}</th><td>{}</td></tr>".format(_html_escape(k), _html_escape(v)) for k, v in rows]
    )

    reading_rows = ""
    readings = status.get("last_reading", {})
    for key, value in readings.items():
        reading_rows += "<tr><th>{}</th><td>{}</td></tr>".format(
            _html_escape(key), _html_escape(value)
        )
    if not reading_rows:
        reading_rows = "<tr><th>感測資料</th><td>尚無</td></tr>"

    restart_hint = ""
    if restart_required:
        restart_hint = '<p class="muted">設定已更新，建議重新啟動裝置套用變更。</p>'

    actions = """<div class="actions">
  <form method="post" action="{action}">
    <button class="btn secondary" type="submit">重啟裝置</button>
  </form>
</div>""".format(
        action=base_path + "/reset"
    )

    prompt = ""
    if restart_required:
        prompt = """<div class="prompt">
  <span>設定已更新，是否立即重啟？</span>
  <form method="post" action="{action}">
    <button class="btn" type="submit">立即重啟</button>
  </form>
  <form method="post" action="{dismiss}">
    <button class="btn secondary" type="submit">稍後</button>
  </form>
</div>""".format(
            action=base_path + "/reset",
            dismiss=base_path + "/reset-dismiss",
        )

    content = """
{prompt}
{actions}
<table>
  {stat_html}
</table>
{restart_hint}
<h2>感測器最新狀態</h2>
<table>
  {reading_rows}
</table>
""".format(
        prompt=prompt,
        actions=actions,
        stat_html=stat_html,
        restart_hint=restart_hint,
        reading_rows=reading_rows,
    )
    return _render_layout(base_path, "系統狀態", content, base_path + "/", message)


# 顯示表單頁面
def render_form_page(base_path, title, active_path, fields, message, reset_prompt=False):
    rows = []
    for field in fields:
        if field.get("type") == "section":
            rows.append(
                '<tr class="section"><th colspan="2">{}</th></tr>'.format(
                    _html_escape(field.get("label", ""))
                )
            )
            continue
        label = _html_escape(field.get("label", ""))
        name = _html_escape(field.get("name", ""))
        value = field.get("value", "")
        ftype = field.get("input", "text")
        placeholder = _html_escape(field.get("placeholder", ""))
        help_text = field.get("help")
        step_attr = ""
        if ftype == "number" and field.get("step"):
            step_attr = ' step="{}"'.format(_html_escape(field.get("step")))

        if ftype == "select":
            options = field.get("options", [])
            opt_html = []
            for opt_value, opt_label in options:
                selected = " selected" if str(value) == str(opt_value) else ""
                opt_html.append(
                    '<option value="{}"{}>{}</option>'.format(
                        _html_escape(opt_value),
                        selected,
                        _html_escape(opt_label),
                    )
                )
            input_html = '<select name="{}">{}</select>'.format(
                name, "".join(opt_html)
            )
        else:
            input_html = (
                '<input type="{}" name="{}" value="{}" placeholder="{}"{} />'.format(
                    ftype,
                    name,
                    _html_escape(value, escape_quotes=True),
                    placeholder,
                    step_attr,
                )
            )
        if help_text:
            input_html += '<div class="muted">{}</div>'.format(
                _html_escape(help_text)
            )
        rows.append("<tr><th>{}</th><td>{}</td></tr>".format(label, input_html))

    prompt = ""
    if reset_prompt:
        prompt = """<div class="prompt">
  <span>設定已儲存，是否立即重啟？</span>
  <form method="post" action="{action}">
    <button class="btn" type="submit">立即重啟</button>
  </form>
  <form method="post" action="{dismiss}">
    <button class="btn secondary" type="submit">稍後</button>
  </form>
</div>""".format(
            action=base_path + "/reset",
            dismiss=base_path + "/reset-dismiss",
        )

    actions = """<div class="actions">
  <form method="post" action="{action}">
    <button class="btn secondary" type="submit">重啟裝置</button>
  </form>
</div>""".format(
        action=base_path + "/reset"
    )

    content = """{prompt}
{actions}
<form method="post" action="{action}">
  <table>
    {rows}
  </table>
  <button class="btn" type="submit">儲存</button>
</form>""".format(
        action=active_path, rows="".join(rows), prompt=prompt, actions=actions
    )
    return _render_layout(base_path, title, content, active_path, message)


# 顯示 Log 頁面
def render_log_page(base_path, lines, message):
    if not lines:
        log_text = "尚無紀錄"
    else:
        log_text = "\n".join(lines)

    actions = """<div class="actions">
  <form method="post" action="{action}">
    <button class="btn secondary" type="submit">重啟裝置</button>
  </form>
</div>""".format(
        action=base_path + "/reset"
    )
    content = """{actions}
<form method="post" action="{action}">
  <div class="log">{log_text}</div>
  <input type="hidden" name="action" value="clear" />
  <button class="btn" type="submit">清除紀錄</button>
</form>""".format(
        action=base_path + "/logs",
        log_text=_html_escape(log_text),
        actions=actions,
    )
    return _render_layout(base_path, "LOG 紀錄", content, base_path + "/logs", message)
