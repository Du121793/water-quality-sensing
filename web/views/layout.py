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
def _render_layout(base_path, title, content, active, message, show_nav=True, refresh_s=0):
    nav_items = [
        ("狀態", base_path + "/"),
        ("網路", base_path + "/wifi"),
        ("API", base_path + "/api"),
        ("感測器", base_path + "/sensors"),
        ("校正", base_path + "/calibration"),
        ("系統", base_path + "/system"),
        ("LOG", base_path + "/logs"),
    ]
    nav_html = ""
    if show_nav:
        links = []
        for name, href in nav_items:
            cls = "nav-item active" if active == href else "nav-item"
            links.append('<a class="{}" href="{}">{}</a>'.format(cls, href, name))
        links.append(
            '<a class="nav-item" href="{}">登出</a>'.format(base_path + "/logout")
        )
        nav_html = '<aside class="nav">{}</aside>'.format("".join(links))

    message_html = ""
    if message:
        message_html = '<div class="flash">{}</div>'.format(_html_escape(message))

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
    textarea {{
      width: 100%;
      padding: 6px 8px;
      border-radius: 6px;
      border: 1px solid var(--border);
      font-size: 13px;
      font-family: "Courier New", monospace;
      resize: vertical;
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
      text-decoration: none;
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
        refresh=refresh_meta,
    )
