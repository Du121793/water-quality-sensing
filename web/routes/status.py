import time
import machine
import gc

from ..views import render_status_page
try:
    import ujson as json
except Exception:
    import json
from ..views.layout import _render_layout


# 顯示系統狀態
def handle_status(server):
    html = render_status_page(
        server._base_path,
        server._status,
        server._message,
        server._restart_required,
    )
    server._message = ""
    server._send_response(server._client, 200, {"Content-Type": "text/html"}, html)
    return True


# 提供狀態頁即時讀值
def handle_status_data(server):
    last = server._status.get("last_reading_detail", {})
    payload = {
        "readings": server._status.get("last_reading", {}),
        "reading_ms": last.get("reading_ms"),
        "reading_iso": last.get("reading_iso"),
        "server_ms": time.ticks_ms(),
    }
    try:
        body = json.dumps(payload)
    except Exception:
        body = "{}"
    server._send_response(
        server._client, 200, {"Content-Type": "application/json"}, body
    )
    return True


# 提供 JSON 狀態摘要
def handle_status_json(server):
    status = server._status
    now_ms = time.ticks_ms()
    uptime_ms = time.ticks_diff(now_ms, status.get("boot_ms", 0))
    uptime_s = int(uptime_ms / 1000)
    uptime = "{}h {}m {}s".format(
        uptime_s // 3600, (uptime_s % 3600) // 60, uptime_s % 60
    )
    last = status.get("last_reading_detail", {})
    reading_ms = last.get("reading_ms")
    if isinstance(reading_ms, (int, float)):
        reading_age_s = max(0, int(time.ticks_diff(now_ms, int(reading_ms)) / 1000))
    else:
        reading_age_s = None

    payload = {
        "mode": status.get("web_mode", ""),
        "web_mode": status.get("web_mode", ""),
        "wifi_mode": status.get("wifi_mode", ""),
        "wifi_connected": bool(status.get("wifi_connected")),
        "local_ip": status.get("ip") or "",
        "uptime_s": uptime_s,
        "uptime": uptime,
        "last_send_iso": status.get("last_send_iso") or "",
        "last_success_iso": status.get("last_send_iso") or "",
        "last_http_code": status.get("last_http_code"),
        "last_error": status.get("last_error") or "",
        "reading_iso": last.get("reading_iso"),
        "reading_age_s": reading_age_s,
        "mem_free": gc.mem_free(),
        "readings": status.get("last_reading", {}),
        "calibration": status.get("last_calibration", {}),
        "server_ms": now_ms,
    }
    try:
        body = json.dumps(payload)
    except Exception:
        body = "{}"
    server._send_response(
        server._client, 200, {"Content-Type": "application/json"}, body
    )
    return True


# 執行裝置重啟
def handle_reset(server):
    server._log("Device reset requested")
    server._reset_prompt = False
    # 顯示重啟提示頁，1 秒後開始嘗試回到管理頁
    content = """<p>裝置即將重啟，將在 1 秒後嘗試返回管理頁。</p>
<p class="muted" id="reboot-status">等待裝置重新啟動...</p>
<script>
(function() {{
  var base = "{base}";
  var statusEl = document.getElementById("reboot-status");
  function ping() {{
    var xhr = new XMLHttpRequest();
    xhr.open("GET", base + "/?ts=" + Date.now(), true);
    xhr.onreadystatechange = function() {{
      if (xhr.readyState === 4) {{
        if (xhr.status === 200) {{
          window.location = base + "/";
        }} else {{
          if (statusEl) {{
            statusEl.textContent = "裝置尚未就緒，持續嘗試中...";
          }}
          setTimeout(ping, 2000);
        }}
      }}
    }};
    try {{
      xhr.send();
    }} catch (e) {{
      setTimeout(ping, 2000);
    }}
  }}
  setTimeout(ping, 1000);
}})();
</script>""".format(
        base=server._base_path
    )
    html = _render_layout(
        server._base_path,
        "裝置重啟中",
        content,
        server._base_path + "/",
        "裝置即將重啟",
        show_nav=False,
        refresh_s=0,
    )
    server._send_response(server._client, 200, {"Content-Type": "text/html"}, html)
    time.sleep(1)
    machine.reset()
    return True


# 延後重啟提示
def handle_reset_dismiss(server):
    server._reset_prompt = False
    server._message = "已稍後重啟"
    server._redirect(server._client, server._base_path + "/")
    return True
