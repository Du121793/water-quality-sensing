import gc
import time

from .layout import _html_escape, _render_layout


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
        [
            "<tr><th>{}</th><td>{}</td></tr>".format(
                _html_escape(k), _html_escape(v)
            )
            for k, v in rows
        ]
    )

    reading_rows = ""
    readings = status.get("last_reading", {})
    last_powered = status.get("last_reading_last_powered", {})
    for key, value in readings.items():
        last_val = last_powered.get(key, value)
        reading_rows += "<tr><th>{}</th><td data-live-key=\"{}\">{}</td><td data-last-key=\"{}\">{}</td></tr>".format(
            _html_escape(key),
            _html_escape(key),
            _html_escape(value),
            _html_escape(key),
            _html_escape(last_val),
        )
    if not reading_rows:
        reading_rows = "<tr><th>感測資料</th><td colspan='2'>尚無</td></tr>"

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

    cal_rows = ""
    cal_info = status.get("last_calibration", {})
    if cal_info:
        for key, value in cal_info.items():
            cal_rows += "<tr><th>{}</th><td>{}</td></tr>".format(
                _html_escape(key), _html_escape(value if value else "-")
            )
    if not cal_rows:
        cal_rows = "<tr><th>校正時間</th><td>尚無</td></tr>"

    content = """
{prompt}
{actions}
<table>
  {stat_html}
</table>
{restart_hint}
<h2>感測器最新狀態</h2>
<div class="muted">更新時間：<span id="reading-time">-</span>（<span id="reading-age">-</span> 秒前）</div>
<table>
  <tr><th>項目</th><th>即時</th><th>最後檢測</th></tr>
  {reading_rows}
</table>
<h2>上次校正時間</h2>
<table>
  {cal_rows}
</table>
<script>
(function() {{
  var inFlight = false;
  var lastReadingAgeBase = null;
  var lastReadingLocalMs = null;
  var timeEl = document.getElementById("reading-time");
  var ageEl = document.getElementById("reading-age");
  function fmt(val) {{
    if (val === null || val === undefined) return "NA";
    return String(val);
  }}
  function updateAge() {{
    if (!ageEl || lastReadingAgeBase === null || lastReadingLocalMs === null) return;
    var sec = Math.floor(lastReadingAgeBase + (Date.now() - lastReadingLocalMs) / 1000);
    if (sec < 0) sec = 0;
    ageEl.textContent = sec;
  }}
  function update() {{
    if (inFlight) return;
    inFlight = true;
    var xhr = new XMLHttpRequest();
    xhr.open("GET", "{data_url}?ts=" + Date.now(), true);
    xhr.onreadystatechange = function() {{
      if (xhr.readyState === 4) {{
        if (xhr.status === 200) {{
          try {{
            var data = JSON.parse(xhr.responseText);
            var readings = data.readings || {{}};
            var lastPowered = data.last_powered || {{}};
            if (data.reading_ms !== null && data.reading_ms !== undefined && data.server_ms !== null && data.server_ms !== undefined) {{
              var readingMs = Number(data.reading_ms);
              var serverMs = Number(data.server_ms);
              if (!isNaN(readingMs) && !isNaN(serverMs)) {{
                lastReadingAgeBase = Math.max(0, (serverMs - readingMs) / 1000);
                lastReadingLocalMs = Date.now();
              }}
            }}
            if (data.reading_iso && timeEl) {{
              timeEl.textContent = String(data.reading_iso);
            }}
            var nodes = document.querySelectorAll("[data-live-key]");
            for (var i = 0; i < nodes.length; i++) {{
              var key = nodes[i].getAttribute("data-live-key");
              if (readings.hasOwnProperty(key)) {{
                nodes[i].textContent = fmt(readings[key]);
              }}
            }}
            var lastNodes = document.querySelectorAll("[data-last-key]");
            for (var j = 0; j < lastNodes.length; j++) {{
              var lastKey = lastNodes[j].getAttribute("data-last-key");
              if (lastPowered.hasOwnProperty(lastKey)) {{
                lastNodes[j].textContent = fmt(lastPowered[lastKey]);
              }} else if (readings.hasOwnProperty(lastKey)) {{
                lastNodes[j].textContent = fmt(readings[lastKey]);
              }}
            }}
          }} catch (e) {{}}
        }}
        inFlight = false;
      }}
    }};
    xhr.send();
  }}
  update();
  setInterval(updateAge, 1000);
  setInterval(update, 2000);
}})();
</script>
""".format(
        prompt=prompt,
        actions=actions,
        stat_html=stat_html,
        restart_hint=restart_hint,
        reading_rows=reading_rows,
        cal_rows=cal_rows,
        data_url=base_path + "/status/data",
    )
    refresh_s = status.get("web_refresh_s", 0) or 0
    return _render_layout(
        base_path, "系統狀態", content, base_path + "/", message, refresh_s=refresh_s
    )
