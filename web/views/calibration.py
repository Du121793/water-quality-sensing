from .layout import _html_escape, _render_layout


# 顯示校正頁面
def render_calibration_page(base_path, title, content, message, refresh_s=0):
    return _render_layout(
        base_path,
        title,
        content,
        base_path + "/calibration",
        message,
        refresh_s=refresh_s,
    )


# 產生校正欄位表格列
def _render_field_rows(fields):
    rows = ""
    for field in fields:
        label = _html_escape(field.get("label", ""))
        name = _html_escape(field.get("name", ""))
        value = field.get("value", "")
        input_type = field.get("input", "text")
        step_attr = ""
        if input_type == "number" and field.get("step") is not None:
            step_attr = ' step="{}"'.format(_html_escape(field.get("step")))
        if input_type == "select":
            options = field.get("options", [])
            options_html = []
            for opt_value, opt_label in options:
                opt_value_esc = _html_escape(opt_value)
                opt_label_esc = _html_escape(opt_label)
                selected = " selected" if str(opt_value) == str(value) else ""
                options_html.append(
                    '<option value="{}"{}>{}</option>'.format(
                        opt_value_esc, selected, opt_label_esc
                    )
                )
            rows += "<tr><th>{}</th><td><select name=\"{}\">{}</select></td></tr>".format(
                label,
                name,
                "".join(options_html),
            )
        else:
            rows += (
                "<tr><th>{}</th><td><input type=\"{}\" name=\"{}\" value=\"{}\"{} /></td></tr>".format(
                    label,
                    input_type,
                    name,
                    _html_escape(value, escape_quotes=True),
                    step_attr,
                )
            )
    return rows


# 顯示校正步驟頁面
def render_calibration_step(
    base_path,
    title,
    tip,
    value_text,
    action,
    fields,
    message,
    refresh_s=0,
    value_html=None,
):
    rows = _render_field_rows(fields)

    if value_html is None:
        value_html = _html_escape(value_text, escape_quotes=False)

    content = """<p>{tip}</p>
<p><strong>目前讀值：</strong>{value}</p>
<p class="muted">狀態：<span id="live-status">尚未更新</span> ｜ 距上次更新：<span id="live-age">NA</span></p>
<form method="post" action="{action}">
  <table>
    {rows}
  </table>
  <input type="hidden" name="action" value="confirm" />
  <button class="btn" type="submit">確認並下一步</button>
</form>
<form method="post" action="{action}">
  <input type="hidden" name="action" value="skip" />
  <button class="btn secondary" type="submit">略過此項</button>
</form>
<script>
(function() {{
  var baseDelay = 1000;
  var errorDelay = 3000;
  var inFlight = false;
  var lastUpdateMs = 0;
  var statusEl = document.getElementById("live-status");
  var ageEl = document.getElementById("live-age");
  function fmt(val) {{
    if (val === null || val === undefined) return "NA";
    if (typeof val === "number") {{
      return (Math.round(val * 100) / 100).toString();
    }}
    return String(val);
  }}
  function updateAge() {{
    if (!ageEl) return;
    if (!lastUpdateMs) {{
      ageEl.textContent = "NA";
      return;
    }}
    var sec = Math.floor((Date.now() - lastUpdateMs) / 1000);
    if (sec < 0) sec = 0;
    ageEl.textContent = sec + " 秒前";
  }}
  function update() {{
    if (inFlight) {{
      setTimeout(update, baseDelay);
      return;
    }}
    inFlight = true;
    var xhr = new XMLHttpRequest();
    xhr.open("GET", "{data_url}?ts=" + Date.now(), true);
    xhr.onreadystatechange = function() {{
      if (xhr.readyState === 4) {{
        if (xhr.status === 200) {{
          try {{
            var data = JSON.parse(xhr.responseText);
            var values = data.values || {{}};
            var nodes = document.querySelectorAll("[data-live-key]");
            for (var i = 0; i < nodes.length; i++) {{
              var key = nodes[i].getAttribute("data-live-key");
              var unit = nodes[i].getAttribute("data-live-unit") || "";
              nodes[i].textContent = fmt(values[key]) + unit;
            }}
          }} catch (e) {{}}
          lastUpdateMs = Date.now();
          if (statusEl) {{
            statusEl.textContent = "已更新";
            statusEl.style.color = "#166534";
          }}
          inFlight = false;
          setTimeout(update, baseDelay);
        }} else {{
          if (statusEl) {{
            statusEl.textContent = "更新失敗";
            statusEl.style.color = "#b91c1c";
          }}
          inFlight = false;
          setTimeout(update, errorDelay);
        }}
      }}
    }};
    xhr.send();
  }}
  update();
  setInterval(updateAge, 1000);
}})();
</script>""".format(
        tip=_html_escape(tip, escape_quotes=False),
        value=value_html,
        action=action,
        rows=rows,
        data_url=base_path + "/calibration/data",
    )
    return render_calibration_page(
        base_path, title, content, message, refresh_s=refresh_s
    )


# 顯示校正總覽頁面
def render_calibration_overview(
    base_path,
    title,
    sections,
    message,
    refresh_s=0,
    prompt_html="",
):
    blocks = []
    for section in sections:
        section_title = _html_escape(section.get("title", ""))
        tip = _html_escape(section.get("tip", ""), escape_quotes=False)
        value_html = section.get("value_html")
        if value_html is None:
            value_html = _html_escape(section.get("value_text", ""), escape_quotes=False)
        rows = _render_field_rows(section.get("fields", []))
        table_html = ""
        if rows:
            table_html = "<table>{}</table>".format(rows)
        action_name = _html_escape(section.get("action", ""))
        button_text = _html_escape(section.get("button_text", "儲存"))
        block_html = """<div class="cal-block">
  <h2>{title}</h2>
  <p class="muted">{tip}</p>
  <p><strong>目前讀值：</strong>{value}</p>
  <form method="post" action="{action_url}">
    {table}
    <input type="hidden" name="action" value="{action_name}" />
    <button class="btn" type="submit">{button_text}</button>
  </form>
</div>""".format(
            title=section_title,
            tip=tip,
            value=value_html,
            action_url=base_path + "/calibration",
            table=table_html,
            action_name=action_name,
            button_text=button_text,
        )
        blocks.append(block_html)

    content = """{prompt}
<p class="muted">狀態：<span id="live-status">尚未更新</span> ｜ 距上次更新：<span id="live-age">NA</span></p>
{blocks}
<script>
(function() {{
  var baseDelay = 1000;
  var errorDelay = 3000;
  var inFlight = false;
  var lastUpdateMs = 0;
  var statusEl = document.getElementById("live-status");
  var ageEl = document.getElementById("live-age");
  function fmt(val) {{
    if (val === null || val === undefined) return "NA";
    if (typeof val === "number") {{
      return (Math.round(val * 100) / 100).toString();
    }}
    return String(val);
  }}
  function updateAge() {{
    if (!ageEl) return;
    if (!lastUpdateMs) {{
      ageEl.textContent = "NA";
      return;
    }}
    var sec = Math.floor((Date.now() - lastUpdateMs) / 1000);
    if (sec < 0) sec = 0;
    ageEl.textContent = sec + " 秒前";
  }}
  function update() {{
    if (inFlight) {{
      setTimeout(update, baseDelay);
      return;
    }}
    inFlight = true;
    var xhr = new XMLHttpRequest();
    xhr.open("GET", "{data_url}?ts=" + Date.now(), true);
    xhr.onreadystatechange = function() {{
      if (xhr.readyState === 4) {{
        if (xhr.status === 200) {{
          try {{
            var data = JSON.parse(xhr.responseText);
            var values = data.values || {{}};
            var nodes = document.querySelectorAll("[data-live-key]");
            for (var i = 0; i < nodes.length; i++) {{
              var key = nodes[i].getAttribute("data-live-key");
              var unit = nodes[i].getAttribute("data-live-unit") || "";
              nodes[i].textContent = fmt(values[key]) + unit;
            }}
          }} catch (e) {{}}
          lastUpdateMs = Date.now();
          if (statusEl) {{
            statusEl.textContent = "已更新";
            statusEl.style.color = "#166534";
          }}
          inFlight = false;
          setTimeout(update, baseDelay);
        }} else {{
          if (statusEl) {{
            statusEl.textContent = "更新失敗";
            statusEl.style.color = "#b91c1c";
          }}
          inFlight = false;
          setTimeout(update, errorDelay);
        }}
      }}
    }};
    xhr.send();
  }}
  update();
  setInterval(updateAge, 1000);
}})();
</script>""".format(
        prompt=prompt_html,
        blocks="".join(blocks),
        data_url=base_path + "/calibration/data",
    )
    return render_calibration_page(
        base_path, title, content, message, refresh_s=refresh_s
    )
