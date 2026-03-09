from methods.utils import get_date_iso, get_date_iso_utc
from methods.api import build_api_url, clone_json
from sensors.tds import calculate_tds_k
from ..forms import parse_form
from ..views import (
    render_calibration_overview,
    render_calibration_page,
    render_calibration_step,
)
import urequests
try:
    import ujson as json
except Exception:
    import json


# 校正步驟順序
_STEPS = [
    "intro",
    "temp_match",
    "ph7",
    "ph4",
    "ph10",
    "turb_raw0",
    "turb_raw_max",
    "turb_raw1",
    "tds_point",
    "ec_point1",
    "ec_point2",
    "orp_point",
    "done",
]


# 取得下一步驟
def _next_step(step):
    if step not in _STEPS:
        return "intro"
    idx = _STEPS.index(step)
    if idx + 1 >= len(_STEPS):
        return "done"
    return _STEPS[idx + 1]


# 從 query 取得當前步驟
def _current_step(query):
    form = parse_form(query)
    step = form.get("step", "intro")
    if step not in _STEPS:
        return "intro"
    return step


# 儲存設定檔
def _save(cfg, save_fn):
    save_fn(cfg)


# 更新指定感測器的最後校正時間
def _set_last_calibration(cfg, key):
    iso = get_date_iso(cfg.get("time", {}).get("timezone_offset_s", 0))
    sensor_cfg = cfg.get(key, {})
    sensor_cfg["last_calibration_iso"] = iso
    cfg[key] = sensor_cfg


# 讀取狀態中的感測細節
# 讀取狀態中的感測細節
def _read_detail(status, key, default=None):
    detail = status.get("last_reading_detail", {})
    return detail.get(key, default)


def _pick_fields(src, keys):
    out = {}
    for key in keys:
        if key in src:
            out[key] = src.get(key)
    return out


def _calibration_config_snapshot(cfg):
    return {
        "ph": _pick_fields(
            cfg.get("ph", {}),
            ["calibration_voltages", "use_code_calibration", "last_calibration_iso"],
        ),
        "turbidity": _pick_fields(
            cfg.get("turbidity", {}),
            ["raw0", "raw_max", "raw1", "ntu1", "last_calibration_iso"],
        ),
        "tds": _pick_fields(
            cfg.get("tds", {}),
            ["k_factor", "cal_ppm", "cal_v", "cal_temp", "last_calibration_iso"],
        ),
        "ec": _pick_fields(
            cfg.get("ec", {}),
            ["cal_v1", "cal_us1", "cal_v2", "cal_us2", "last_calibration_iso"],
        ),
        "orp": _pick_fields(
            cfg.get("orp", {}),
            ["offset_mv", "cal_target_mv", "cal_v_sensor", "cal_raw", "last_calibration_iso"],
        ),
        "ds18b20": _pick_fields(
            cfg.get("ds18b20", {}),
            ["shallow_offset", "shallow_scale", "last_calibration_iso"],
        ),
    }


def _calibration_snapshot(cfg, status):
    return {
        "config": clone_json(_calibration_config_snapshot(cfg), {}),
        "reading": clone_json(status.get("last_reading_detail", {}), {}),
    }


def _send_maintenance_record(server, cfg, status):
    api_cfg = cfg.get("api", {})
    if not api_cfg:
        return

    before = status.pop("calibration_before", None)
    before_iso = status.pop("calibration_before_iso", None)
    after = _calibration_snapshot(cfg, status)
    calibration_time = get_date_iso_utc()
    payload = {
        "sensorId": cfg.get("payload", {}).get("sensor_id"),
        "date": calibration_time,
        "local_ip": status.get("ip") or "",
        "calibration_time": calibration_time,
        "before": before or {},
        "after": after,
    }
    if before_iso:
        payload["calibration_start"] = before_iso

    url = build_api_url(cfg, "maintain_record", "/maintainRecord")
    headers = api_cfg.get("headers", {})
    timeout = api_cfg.get("post_timeout_s", 10)
    try:
        try:
            r = urequests.post(url, json=payload, headers=headers, timeout=timeout)
        except TypeError:
            r = urequests.post(url, json=payload, headers=headers)
        status_code = r.status_code
        r.close()
        if status_code == 200:
            server._log("Maintenance record sent")
        else:
            server._log("Maintenance record HTTP {}".format(status_code))
    except Exception as e:
        server._log("Maintenance record send failed: {}".format(e))


# 處理校正流程
def handle_calibration(server, method, body):
    if method == "POST":
        form = parse_form(body)
        action = form.get("action", "")
        cfg = server._cfg
        # 切換模式（校正/一般）
        if action in ("set_mode_calibration", "set_mode_normal"):
            web_cfg = cfg.get("web", {})
            web_cfg["mode"] = "calibration" if action == "set_mode_calibration" else "normal"
            cfg["web"] = web_cfg
            if action == "set_mode_calibration":
                status = server._status
                status["calibration_before"] = _calibration_snapshot(cfg, status)
                status["calibration_before_iso"] = get_date_iso_utc()
            _save(cfg, server._save_config)
            if action == "set_mode_calibration":
                server._redirect(server._client, server._base_path + "/calibration")
            else:
                _send_maintenance_record(server, cfg, server._status)
                server._redirect(server._client, server._base_path + "/")
            return True

        status = server._status
        saved = False
        msg = ""

        if action == "save_ph7":
            ph_v = _read_detail(status, "ph_v", None)
            if ph_v is not None:
                ph_cfg = cfg.get("ph", {})
                cal = ph_cfg.get("calibration_voltages", {})
                cal["ph7"] = float(ph_v)
                ph_cfg["calibration_voltages"] = cal
                cfg["ph"] = ph_cfg
                _set_last_calibration(cfg, "ph")
                _save(cfg, server._save_config)
                saved = True
                msg = "pH 7 校正已儲存"
            else:
                msg = "pH 7 儲存失敗：讀值無效"

        elif action == "save_ph4":
            ph_v = _read_detail(status, "ph_v", None)
            if ph_v is not None:
                ph_cfg = cfg.get("ph", {})
                cal = ph_cfg.get("calibration_voltages", {})
                cal["ph4"] = float(ph_v)
                ph_cfg["calibration_voltages"] = cal
                cfg["ph"] = ph_cfg
                _set_last_calibration(cfg, "ph")
                _save(cfg, server._save_config)
                saved = True
                msg = "pH 4 校正已儲存"
            else:
                msg = "pH 4 儲存失敗：讀值無效"

        elif action == "save_ph10":
            ph_v = _read_detail(status, "ph_v", None)
            if ph_v is not None:
                ph_cfg = cfg.get("ph", {})
                cal = ph_cfg.get("calibration_voltages", {})
                cal["ph10"] = float(ph_v)
                ph_cfg["calibration_voltages"] = cal
                cfg["ph"] = ph_cfg
                _set_last_calibration(cfg, "ph")
                _save(cfg, server._save_config)
                saved = True
                msg = "pH 10 校正已儲存"
            else:
                msg = "pH 10 儲存失敗：讀值無效"

        elif action == "save_temp_match":
            temp_shallow = _read_detail(status, "temp_shallow", None)
            temp_deep = _read_detail(status, "temp_deep", None)
            if isinstance(temp_shallow, (int, float)) and isinstance(
                temp_deep, (int, float)
            ):
                if temp_shallow != -127.0 and temp_deep != -127.0:
                    offset = float(temp_deep) - float(temp_shallow)
                    ds_cfg = cfg.get("ds18b20", {})
                    ds_cfg["shallow_offset"] = round(offset, 3)
                    ds_cfg["shallow_scale"] = 1.0
                    cfg["ds18b20"] = ds_cfg
                    _set_last_calibration(cfg, "ds18b20")
                    _save(cfg, server._save_config)
                    saved = True
                    msg = "溫度校正已儲存"
                else:
                    msg = "溫度校正失敗：讀值無效"
            else:
                msg = "溫度校正失敗：讀值無效"

        elif action == "save_turb_raw0":
            turb_raw = _read_detail(status, "turbidity_raw", None)
            if turb_raw is not None:
                turb_cfg = cfg.get("turbidity", {})
                turb_cfg["raw0"] = int(turb_raw)
                cfg["turbidity"] = turb_cfg
                _set_last_calibration(cfg, "turbidity")
                _save(cfg, server._save_config)
                saved = True
                msg = "濁度 0 NTU 校正已儲存"
            else:
                msg = "濁度 0 NTU 儲存失敗：讀值無效"

        elif action == "save_turb_raw_max":
            turb_raw = _read_detail(status, "turbidity_raw", None)
            if turb_raw is not None:
                turb_cfg = cfg.get("turbidity", {})
                turb_cfg["raw_max"] = int(turb_raw)
                cfg["turbidity"] = turb_cfg
                _set_last_calibration(cfg, "turbidity")
                _save(cfg, server._save_config)
                saved = True
                msg = "濁度上限校正已儲存"
            else:
                msg = "濁度上限儲存失敗：讀值無效"

        elif action == "save_turb_raw1":
            turb_raw = _read_detail(status, "turbidity_raw", None)
            ntu1 = form.get("ntu1", "").strip()
            if not ntu1:
                msg = "濁度 NTU 儲存失敗：請輸入 NTU 值"
            elif turb_raw is None:
                msg = "濁度 NTU 儲存失敗：讀值無效"
            else:
                try:
                    ntu1_val = float(ntu1)
                except Exception:
                    ntu1_val = None
                if ntu1_val is not None:
                    turb_cfg = cfg.get("turbidity", {})
                    turb_cfg["raw1"] = int(turb_raw)
                    turb_cfg["ntu1"] = ntu1_val
                    cfg["turbidity"] = turb_cfg
                    _set_last_calibration(cfg, "turbidity")
                    _save(cfg, server._save_config)
                    saved = True
                    msg = "濁度 NTU 校正已儲存"
                else:
                    msg = "濁度 NTU 儲存失敗：輸入無效"

        elif action == "save_tds_point":
            tds_raw = _read_detail(status, "tds_raw", None)
            temp_c = _read_detail(status, "temp_for_ph_tds", None)
            ppm_text = form.get("ppm", "").strip()
            if not ppm_text:
                msg = "TDS 校正失敗：請輸入 ppm"
            elif not isinstance(tds_raw, (int, float)) or not isinstance(
                temp_c, (int, float)
            ):
                msg = "TDS 校正失敗：讀值無效"
            else:
                try:
                    ppm_val = float(ppm_text)
                except Exception:
                    ppm_val = None
                if ppm_val is not None:
                    k_val, v_val, base_ppm = calculate_tds_k(
                        tds_raw,
                        temp_c,
                        cfg.get("tds", {}).get("vref", 3.3),
                        cfg.get("tds", {}).get("temp_compensation_factor", 0.02),
                        ppm_val,
                    )
                    if k_val is not None:
                        tds_cfg = cfg.get("tds", {})
                        tds_cfg["k_factor"] = k_val
                        tds_cfg["cal_ppm"] = ppm_val
                        tds_cfg["cal_v"] = v_val
                        tds_cfg["cal_temp"] = temp_c
                        cfg["tds"] = tds_cfg
                        _set_last_calibration(cfg, "tds")
                        _save(cfg, server._save_config)
                        saved = True
                        msg = "TDS 校正已儲存"
                    else:
                        msg = "TDS 校正失敗：係數計算無效"
                else:
                    msg = "TDS 校正失敗：輸入無效"

        elif action == "save_ec_point1":
            ec_v = _read_detail(status, "ec_v", None)
            us1 = form.get("us1", "").strip()
            unit1 = form.get("unit1", "us").strip().lower()
            if ec_v is None:
                msg = "EC 校正點 1 失敗：讀值無效"
            elif not us1:
                msg = "EC 校正點 1 失敗：請輸入數值"
            else:
                try:
                    us1_val = float(us1)
                except Exception:
                    us1_val = None
                if us1_val is not None:
                    if unit1 == "ms":
                        us1_val = us1_val * 1000.0
                    ec_cfg = cfg.get("ec", {})
                    ec_cfg["cal_v1"] = float(ec_v)
                    ec_cfg["cal_us1"] = us1_val
                    cfg["ec"] = ec_cfg
                    _set_last_calibration(cfg, "ec")
                    _save(cfg, server._save_config)
                    saved = True
                    msg = "EC 校正點 1 已儲存"
                else:
                    msg = "EC 校正點 1 失敗：輸入無效"

        elif action == "save_ec_point2":
            ec_v = _read_detail(status, "ec_v", None)
            us2 = form.get("us2", "").strip()
            unit2 = form.get("unit2", "us").strip().lower()
            if ec_v is None:
                msg = "EC 校正點 2 失敗：讀值無效"
            elif not us2:
                msg = "EC 校正點 2 失敗：請輸入數值"
            else:
                try:
                    us2_val = float(us2)
                except Exception:
                    us2_val = None
                if us2_val is not None:
                    if unit2 == "ms":
                        us2_val = us2_val * 1000.0
                    ec_cfg = cfg.get("ec", {})
                    ec_cfg["cal_v2"] = float(ec_v)
                    ec_cfg["cal_us2"] = us2_val
                    cfg["ec"] = ec_cfg
                    _set_last_calibration(cfg, "ec")
                    _save(cfg, server._save_config)
                    saved = True
                    msg = "EC 校正點 2 已儲存"
                else:
                    msg = "EC 校正點 2 失敗：輸入無效"

        elif action == "save_orp_point":
            v_sensor = _read_detail(status, "orp_v_sensor", None)
            raw_val = _read_detail(status, "orp_raw", None)
            is_valid = _read_detail(status, "orp_valid", True)
            target_text = form.get("target_mv", "").strip()
            if not target_text:
                msg = "ORP 校正失敗：請輸入目標 mV"
            elif v_sensor is None or not is_valid:
                msg = "ORP 校正失敗：讀值無效"
            else:
                try:
                    target_val = float(target_text)
                except Exception:
                    target_val = None
                if target_val is not None:
                    orp_cfg = cfg.get("orp", {})
                    scale = orp_cfg.get("scale", 1.0)
                    if not isinstance(scale, (int, float)) or scale <= 0:
                        scale = 1.0
                    orp_no_offset = (float(v_sensor) - 2.0) * 1000.0 * scale
                    orp_cfg["offset_mv"] = round(target_val - orp_no_offset, 2)
                    orp_cfg["cal_target_mv"] = float(target_val)
                    orp_cfg["cal_v_sensor"] = round(float(v_sensor), 3)
                    orp_cfg["cal_raw"] = (
                        int(raw_val) if isinstance(raw_val, (int, float)) else None
                    )
                    cfg["orp"] = orp_cfg
                    _set_last_calibration(cfg, "orp")
                    _save(cfg, server._save_config)
                    saved = True
                    msg = "ORP 校正已儲存"
                else:
                    msg = "ORP 校正失敗：輸入無效"

        if action:
            if saved:
                server._message = msg
            else:
                server._message = msg or "儲存失敗：讀值無效"
            server._redirect(server._client, server._base_path + "/calibration")
            return True

    # GET 顯示頁面
    status = server._status
    cfg = server._cfg
    message = server._message
    server._message = ""

    refresh_s = 0
    web_mode = cfg.get("web", {}).get("mode", "normal")

    if web_mode != "calibration":
        content = """<p>校正頁面僅能在「校正模式」下使用。</p>
<p class="muted">請到「系統」→「網頁管理」切換模式或使用下方按鈕。</p>
<form method="post" action="{action}">
  <input type="hidden" name="action" value="set_mode_calibration" />
  <button class="btn" type="submit">切換至校正模式</button>
</form>""".format(
            action=server._base_path + "/calibration"
        )
        html = render_calibration_page(
            server._base_path, "校正模式", content, message, refresh_s=0
        )
        server._send_response(server._client, 200, {"Content-Type": "text/html"}, html)
        return True

    ph_v = _read_detail(status, "ph_v", "NA")
    ph_val = _read_detail(status, "ph", "NA")
    temp_c = _read_detail(status, "temp_for_ph_tds", "NA")
    ph_value_html = (
        '電壓 <span data-live-key="ph_v" data-live-unit=" V">{}</span>'
        " / "
        '檢測值 <span data-live-key="ph">{}</span>'
        " / "
        '溫度 <span data-live-key="temp_for_ph_tds" data-live-unit=" C">{}</span>'
    ).format(ph_v, ph_val, temp_c)

    temp_shallow = _read_detail(status, "temp_shallow", "NA")
    temp_deep = _read_detail(status, "temp_deep", "NA")
    temp_value_html = (
        '淺層 <span data-live-key="temp_shallow" data-live-unit=" C">{}</span>'
        " / "
        '深層 <span data-live-key="temp_deep" data-live-unit=" C">{}</span>'
    ).format(temp_shallow, temp_deep)

    turb_raw = _read_detail(status, "turbidity_raw", "NA")
    turb_v = _read_detail(status, "turbidity_v", "NA")
    turb_ntu = _read_detail(status, "turbidity_ntu", "NA")
    turb_temp = _read_detail(status, "temp_shallow", "NA")
    turb_value_html = (
        '電壓 <span data-live-key="turbidity_v" data-live-unit=" V">{}</span>'
        " / "
        '檢測值 raw <span data-live-key="turbidity_raw">{}</span>'
        " / "
        'NTU <span data-live-key="turbidity_ntu">{}</span>'
        " / "
        '溫度 <span data-live-key="temp_shallow" data-live-unit=" C">{}</span>'
    ).format(turb_v, turb_raw, turb_ntu, turb_temp)

    tds_v = _read_detail(status, "tds_v", "NA")
    tds_ppm = _read_detail(status, "tds_ppm", "NA")
    tds_temp = _read_detail(status, "temp_for_ph_tds", "NA")
    tds_value_html = (
        '電壓 <span data-live-key="tds_v" data-live-unit=" V">{}</span>'
        " / "
        '檢測值 <span data-live-key="tds_ppm" data-live-unit=" ppm">{}</span>'
        " / "
        '溫度 <span data-live-key="temp_for_ph_tds" data-live-unit=" C">{}</span>'
    ).format(tds_v, tds_ppm, tds_temp)

    ec_v = _read_detail(status, "ec_v", "NA")
    ec_us = _read_detail(status, "ec_us", "NA")
    ec_temp = _read_detail(status, "temp_for_ph_tds", "NA")
    ec_value_html = (
        '電壓 <span data-live-key="ec_v" data-live-unit=" V">{}</span>'
        " / "
        '檢測值 <span data-live-key="ec_us" data-live-unit=" uS/cm">{}</span>'
        " / "
        '溫度 <span data-live-key="temp_for_ph_tds" data-live-unit=" C">{}</span>'
    ).format(ec_v, ec_us, ec_temp)

    orp_v = _read_detail(status, "orp_v_sensor", "NA")
    orp_mv = _read_detail(status, "orp_mv", "NA")
    orp_temp = _read_detail(status, "temp_for_ph_tds", "NA")
    orp_value_html = (
        '電壓 <span data-live-key="orp_v_sensor" data-live-unit=" V">{}</span>'
        " / "
        '檢測值 <span data-live-key="orp_mv" data-live-unit=" mV">{}</span>'
        " / "
        '溫度 <span data-live-key="temp_for_ph_tds" data-live-unit=" C">{}</span>'
    ).format(orp_v, orp_mv, orp_temp)

    turb_cfg = cfg.get("turbidity", {})
    tds_cfg = cfg.get("tds", {})
    ec_cfg = cfg.get("ec", {})
    orp_cfg = cfg.get("orp", {})

    ntu1_value = turb_cfg.get("ntu1")
    tds_ppm_value = tds_cfg.get("cal_ppm")
    if not isinstance(tds_ppm_value, (int, float)):
        tds_ppm_value = 1413
    ec_us1_value = ec_cfg.get("cal_us1")
    if not isinstance(ec_us1_value, (int, float)):
        ec_us1_value = 1413
    ec_us2_value = ec_cfg.get("cal_us2")
    if isinstance(ec_us2_value, (int, float)):
        ec_us2_display = round(ec_us2_value / 1000.0, 3)
    else:
        ec_us2_display = 12.88
    orp_target_value = orp_cfg.get("cal_target_mv")
    if not isinstance(orp_target_value, (int, float)):
        orp_target_value = 222

    prompt = """<div class="prompt">
  <span>校正模式中，請將探頭放入標準液並等待數值穩定後再儲存。</span>
  <form method="post" action="{action}">
    <input type="hidden" name="action" value="set_mode_normal" />
    <button class="btn secondary" type="submit">切回一般模式</button>
  </form>
</div>
<p class="muted">建議準備：清水、pH 4/7/10 緩衝液、TDS/EC/ORP 標準液。</p>""".format(
        action=server._base_path + "/calibration"
    )

    sections = [
        {
            "title": "pH 7 校正",
            "tip": "請將探頭放入 pH7 緩衝液，數值穩定後按儲存。",
            "value_html": ph_value_html,
            "action": "save_ph7",
            "button_text": "儲存 pH7",
        },
        {
            "title": "pH 4 校正",
            "tip": "請將探頭放入 pH4 緩衝液，數值穩定後按儲存。",
            "value_html": ph_value_html,
            "action": "save_ph4",
            "button_text": "儲存 pH4",
        },
        {
            "title": "pH 10 校正",
            "tip": "請將探頭放入 pH10 緩衝液，數值穩定後按儲存。",
            "value_html": ph_value_html,
            "action": "save_ph10",
            "button_text": "儲存 pH10",
        },
        {
            "title": "溫度校正",
            "tip": "請將兩個探頭放在同一容器，數值穩定後按儲存。",
            "value_html": temp_value_html,
            "action": "save_temp_match",
            "button_text": "儲存溫度校正",
        },
        {
            "title": "濁度 0 NTU 校正",
            "tip": "請將探頭放入清水（0 NTU），數值穩定後按儲存。",
            "value_html": turb_value_html,
            "action": "save_turb_raw0",
            "button_text": "儲存 0 NTU 校正",
        },
        {
            "title": "濁度 相對上限校正",
            "tip": "請將探頭放入最濁狀態（作為 100%），數值穩定後按儲存。",
            "value_html": turb_value_html,
            "action": "save_turb_raw_max",
            "button_text": "儲存濁度上限",
        },
        {
            "title": "濁度 NTU 校正",
            "tip": "請將探頭放入已知 NTU 溶液，輸入 NTU 後按儲存。",
            "value_html": turb_value_html,
            "action": "save_turb_raw1",
            "button_text": "儲存 NTU 校正",
            "fields": [
                {
                    "label": "NTU 值",
                    "name": "ntu1",
                    "value": "" if ntu1_value is None else ntu1_value,
                    "input": "number",
                    "step": "0.1",
                }
            ],
        },
        {
            "title": "TDS 校正",
            "tip": "請將探頭放入 TDS 標準液，輸入 ppm 後按儲存。",
            "value_html": tds_value_html,
            "action": "save_tds_point",
            "button_text": "儲存 TDS 校正",
            "fields": [
                {
                    "label": "ppm",
                    "name": "ppm",
                    "value": tds_ppm_value,
                    "input": "number",
                    "step": "0.1",
                }
            ],
        },
        {
            "title": "EC 校正點 1",
            "tip": "請將探頭放入標準液，輸入數值並選擇單位後按儲存。",
            "value_html": ec_value_html,
            "action": "save_ec_point1",
            "button_text": "儲存 EC 點 1",
            "fields": [
                {
                    "label": "數值",
                    "name": "us1",
                    "value": ec_us1_value,
                    "input": "number",
                    "step": "0.1",
                },
                {
                    "label": "單位",
                    "name": "unit1",
                    "value": "us",
                    "input": "select",
                    "options": [("us", "uS/cm"), ("ms", "mS/cm")],
                },
            ],
        },
        {
            "title": "EC 校正點 2",
            "tip": "請將探頭放入第二標準液，輸入數值並選擇單位後按儲存。",
            "value_html": ec_value_html,
            "action": "save_ec_point2",
            "button_text": "儲存 EC 點 2",
            "fields": [
                {
                    "label": "數值",
                    "name": "us2",
                    "value": ec_us2_display,
                    "input": "number",
                    "step": "0.01",
                },
                {
                    "label": "單位",
                    "name": "unit2",
                    "value": "ms",
                    "input": "select",
                    "options": [("us", "uS/cm"), ("ms", "mS/cm")],
                },
            ],
        },
        {
            "title": "ORP 校正",
            "tip": "請將探頭放入 ORP 標準液，輸入目標 mV 後按儲存。",
            "value_html": orp_value_html,
            "action": "save_orp_point",
            "button_text": "儲存 ORP 校正",
            "fields": [
                {
                    "label": "目標 mV",
                    "name": "target_mv",
                    "value": orp_target_value,
                    "input": "number",
                    "step": "0.1",
                }
            ],
        },
    ]

    html = render_calibration_overview(
        server._base_path,
        "校正模式",
        sections,
        message,
        refresh_s=refresh_s,
        prompt_html=prompt,
    )
    server._send_response(server._client, 200, {"Content-Type": "text/html"}, html)
    return True

# 提供校正頁面即時讀值
def handle_calibration_data(server):
    status = server._status
    detail = status.get("last_reading_detail", {})
    payload = {"ok": True, "values": detail}
    try:
        body = json.dumps(payload)
    except Exception:
        body = "{}"
    server._send_response(
        server._client, 200, {"Content-Type": "application/json"}, body
    )
    return True
