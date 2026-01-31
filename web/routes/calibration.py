from methods.utils import get_date_iso
from sensors.tds import calculate_tds_k
from ..forms import parse_form
from ..views import render_calibration_page, render_calibration_step
try:
    import ujson as json
except Exception:
    import json


# 校正步驟順序
_STEPS = [
    "intro",
    "ph7",
    "ph4",
    "ph10",
    "temp_match",
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


# 處理校正流程
def handle_calibration(server, method, body):
    query = getattr(server, "_query", "") or ""
    step = _current_step(query)

    if method == "POST":
        form = parse_form(body)
        action = form.get("action", "")
        cfg = server._cfg
        # 切換模式（校正/一般）
        if action in ("set_mode_calibration", "set_mode_normal"):
            web_cfg = cfg.get("web", {})
            web_cfg["mode"] = "calibration" if action == "set_mode_calibration" else "normal"
            cfg["web"] = web_cfg
            _save(cfg, server._save_config)
            if action == "set_mode_calibration":
                server._redirect(server._client, server._base_path + "/calibration?step=intro")
            else:
                server._redirect(server._client, server._base_path + "/")
            return True

        if action == "skip":
            server._redirect(
                server._client,
                server._base_path + "/calibration?step={}".format(_next_step(step)),
            )
            return True

        if action == "confirm":
            cfg = server._cfg
            status = server._status

            if step == "ph7":
                ph_v = _read_detail(status, "ph_v", None)
                if ph_v is not None:
                    ph_cfg = cfg.get("ph", {})
                    cal = ph_cfg.get("calibration_voltages", {})
                    cal["ph7"] = float(ph_v)
                    ph_cfg["calibration_voltages"] = cal
                    cfg["ph"] = ph_cfg
                    _set_last_calibration(cfg, "ph")
                    _save(cfg, server._save_config)

            elif step == "ph4":
                ph_v = _read_detail(status, "ph_v", None)
                if ph_v is not None:
                    ph_cfg = cfg.get("ph", {})
                    cal = ph_cfg.get("calibration_voltages", {})
                    cal["ph4"] = float(ph_v)
                    ph_cfg["calibration_voltages"] = cal
                    cfg["ph"] = ph_cfg
                    _set_last_calibration(cfg, "ph")
                    _save(cfg, server._save_config)

            elif step == "ph10":
                ph_v = _read_detail(status, "ph_v", None)
                if ph_v is not None:
                    ph_cfg = cfg.get("ph", {})
                    cal = ph_cfg.get("calibration_voltages", {})
                    cal["ph10"] = float(ph_v)
                    ph_cfg["calibration_voltages"] = cal
                    cfg["ph"] = ph_cfg
                    _set_last_calibration(cfg, "ph")
                    _save(cfg, server._save_config)

            elif step == "temp_match":
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

            elif step == "turb_raw0":
                turb_raw = _read_detail(status, "turbidity_raw", None)
                if turb_raw is not None:
                    turb_cfg = cfg.get("turbidity", {})
                    turb_cfg["raw0"] = int(turb_raw)
                    cfg["turbidity"] = turb_cfg
                    _set_last_calibration(cfg, "turbidity")
                    _save(cfg, server._save_config)

            elif step == "turb_raw_max":
                turb_raw = _read_detail(status, "turbidity_raw", None)
                if turb_raw is not None:
                    turb_cfg = cfg.get("turbidity", {})
                    turb_cfg["raw_max"] = int(turb_raw)
                    cfg["turbidity"] = turb_cfg
                    _set_last_calibration(cfg, "turbidity")
                    _save(cfg, server._save_config)

            elif step == "turb_raw1":
                turb_raw = _read_detail(status, "turbidity_raw", None)
                ntu1 = form.get("ntu1", "").strip()
                if turb_raw is not None and ntu1:
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

            elif step == "tds_point":
                tds_raw = _read_detail(status, "tds_raw", None)
                temp_c = _read_detail(status, "temp_for_ph_tds", None)
                ppm_text = form.get("ppm", "").strip()
                if (
                    isinstance(tds_raw, (int, float))
                    and isinstance(temp_c, (int, float))
                    and ppm_text
                ):
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

            elif step == "ec_point1":
                ec_v = _read_detail(status, "ec_v", None)
                us1 = form.get("us1", "").strip()
                unit1 = form.get("unit1", "us").strip().lower()
                if ec_v is not None and us1:
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

            elif step == "ec_point2":
                ec_v = _read_detail(status, "ec_v", None)
                us2 = form.get("us2", "").strip()
                unit2 = form.get("unit2", "us").strip().lower()
                if ec_v is not None and us2:
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


            elif step == "orp_point":
                v_sensor = _read_detail(status, "orp_v_sensor", None)
                raw_val = _read_detail(status, "orp_raw", None)
                is_valid = _read_detail(status, "orp_valid", True)
                target_text = form.get("target_mv", "").strip()
                if v_sensor is not None and target_text and is_valid:
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
                        orp_cfg["cal_raw"] = int(raw_val) if isinstance(raw_val, (int, float)) else None
                        cfg["orp"] = orp_cfg
                        _set_last_calibration(cfg, "orp")
                        _save(cfg, server._save_config)

            server._redirect(
                server._client,
                server._base_path + "/calibration?step={}".format(_next_step(step)),
            )
            return True

    # GET 顯示頁面
    status = server._status
    cfg = server._cfg
    message = server._message
    server._message = ""

    refresh_s = 0
    web_mode = cfg.get("web", {}).get("mode", "normal")

    if web_mode != "calibration":
        content = """<p>校正頁面需先切換為「校正模式」才能使用。</p>
<p class="muted">請到「系統」→「網頁管理」把模式改成校正，或使用下方按鈕切換。</p>
<form method="post" action="{action}">
  <input type="hidden" name="action" value="set_mode_calibration" />
  <button class="btn" type="submit">切換到校正模式</button>
</form>""".format(
            action=server._base_path + "/calibration?step=intro"
        )
        html = render_calibration_page(
            server._base_path, "校正模式", content, message, refresh_s=0
        )
        server._send_response(server._client, 200, {"Content-Type": "text/html"}, html)
        return True

    if step == "intro":
        content = """<p>校正前請準備以下物品：</p>
  <ul>
    <li>蒸餾水（濁度/清洗）</li>
    <li>pH 4/7/10 緩衝液</li>
    <li>TDS 標準液（例如 1413 ppm）</li>
    <li>EC 標準液（例如 1413 uS/cm、12.88 mS/cm）</li>
    <li>ORP 標準液（例如 222 mV@25C）</li>
  </ul>
<form method="post" action="{action}">
  <input type="hidden" name="action" value="confirm" />
  <button class="btn" type="submit">開始校正</button>
</form>""".format(
            action=server._base_path + "/calibration?step=intro"
        )
        html = render_calibration_page(
            server._base_path, "校正模式", content, message, refresh_s=refresh_s
        )
        server._send_response(server._client, 200, {"Content-Type": "text/html"}, html)
        return True

    if step == "ph7":
        ph_v = _read_detail(status, "ph_v", "NA")
        value_html = '<span data-live-key="ph_v" data-live-unit=" V">{}</span>'.format(
            ph_v
        )
        html = render_calibration_step(
            server._base_path,
            "pH 7 校正",
            "請將探頭放入 pH7 緩衝液，數值穩定後按確認",
            "",
            server._base_path + "/calibration?step=ph7",
            [],
            message,
            refresh_s=refresh_s,
            value_html=value_html,
        )
    elif step == "ph4":
        ph_v = _read_detail(status, "ph_v", "NA")
        value_html = '<span data-live-key="ph_v" data-live-unit=" V">{}</span>'.format(
            ph_v
        )
        html = render_calibration_step(
            server._base_path,
            "pH 4 校正",
            "請將探頭放入 pH4 緩衝液，數值穩定後按確認",
            "",
            server._base_path + "/calibration?step=ph4",
            [],
            message,
            refresh_s=refresh_s,
            value_html=value_html,
        )
    elif step == "ph10":
        ph_v = _read_detail(status, "ph_v", "NA")
        value_html = '<span data-live-key="ph_v" data-live-unit=" V">{}</span>'.format(
            ph_v
        )
        html = render_calibration_step(
            server._base_path,
            "pH 10 校正",
            "請將探頭放入 pH10 緩衝液，數值穩定後按確認",
            "",
            server._base_path + "/calibration?step=ph10",
            [],
            message,
            refresh_s=refresh_s,
            value_html=value_html,
        )
    elif step == "temp_match":
        temp_shallow = _read_detail(status, "temp_shallow", "NA")
        temp_deep = _read_detail(status, "temp_deep", "NA")
        value_html = (
            '<span data-live-key="temp_shallow" data-live-unit=" C">{}</span>'
            " / "
            '<span data-live-key="temp_deep" data-live-unit=" C">{}</span>'
        ).format(temp_shallow, temp_deep)
        html = render_calibration_step(
            server._base_path,
            "溫度校正",
            "請將兩個探頭放在同一容器，數值穩定後按確認",
            "",
            server._base_path + "/calibration?step=temp_match",
            [],
            message,
            refresh_s=refresh_s,
            value_html=value_html,
        )
    elif step == "turb_raw0":
        turb_raw = _read_detail(status, "turbidity_raw", "NA")
        value_html = 'raw <span data-live-key="turbidity_raw">{}</span>'.format(
            turb_raw
        )
        html = render_calibration_step(
            server._base_path,
            "濁度 0 NTU 校正",
            "請將探頭放入清水（0 NTU），數值穩定後按確認",
            "",
            server._base_path + "/calibration?step=turb_raw0",
            [],
            message,
            refresh_s=refresh_s,
            value_html=value_html,
        )
    elif step == "turb_raw_max":
        turb_raw = _read_detail(status, "turbidity_raw", "NA")
        value_html = 'raw <span data-live-key="turbidity_raw">{}</span>'.format(
            turb_raw
        )
        html = render_calibration_step(
            server._base_path,
            "濁度 相對上限校正",
            "請將探頭放入最濁狀態（作為 100%），數值穩定後按確認",
            "",
            server._base_path + "/calibration?step=turb_raw_max",
            [],
            message,
            refresh_s=refresh_s,
            value_html=value_html,
        )
    elif step == "turb_raw1":
        turb_raw = _read_detail(status, "turbidity_raw", "NA")
        value_html = 'raw <span data-live-key="turbidity_raw">{}</span>'.format(
            turb_raw
        )
        html = render_calibration_step(
            server._base_path,
            "濁度 NTU 校正",
            "請將探頭放入已知 NTU 溶液，輸入 NTU 後按確認",
            "",
            server._base_path + "/calibration?step=turb_raw1",
            [{"label": "NTU 值", "name": "ntu1", "value": "", "input": "number", "step": "0.1"}],
            message,
            refresh_s=refresh_s,
            value_html=value_html,
        )
    elif step == "tds_point":
        tds_raw = _read_detail(status, "tds_raw", "NA")
        tds_v = _read_detail(status, "tds_v", "NA")
        value_html = (
            'raw <span data-live-key="tds_raw">{}</span> / V '
            '<span data-live-key="tds_v">{}</span>'
        ).format(tds_raw, tds_v)
        html = render_calibration_step(
            server._base_path,
            "TDS 校正",
            "請將探頭放入 TDS 標準液，輸入 ppm 後按確認",
            "",
            server._base_path + "/calibration?step=tds_point",
            [{"label": "ppm", "name": "ppm", "value": "1413", "input": "number", "step": "0.1"}],
            message,
            refresh_s=refresh_s,
            value_html=value_html,
        )
    elif step == "ec_point1":
        ec_v = _read_detail(status, "ec_v", "NA")
        value_html = '<span data-live-key="ec_v" data-live-unit=" V">{}</span>'.format(
            ec_v
        )
        html = render_calibration_step(
            server._base_path,
            "EC 校正點 1",
            "請將探頭放入標準液，輸入數值並選擇單位後按確認",
            "",
            server._base_path + "/calibration?step=ec_point1",
            [
                {"label": "數值", "name": "us1", "value": "1413", "input": "number", "step": "0.1"},
                {
                    "label": "單位",
                    "name": "unit1",
                    "value": "us",
                    "input": "select",
                    "options": [("us", "uS/cm"), ("ms", "mS/cm")],
                },
            ],
            message,
            refresh_s=refresh_s,
            value_html=value_html,
        )
    elif step == "ec_point2":
        ec_v = _read_detail(status, "ec_v", "NA")
        value_html = '<span data-live-key="ec_v" data-live-unit=" V">{}</span>'.format(
            ec_v
        )
        html = render_calibration_step(
            server._base_path,
            "EC 校正點 2",
            "請將探頭放入第二標準液，輸入數值並選擇單位後按確認",
            "",
            server._base_path + "/calibration?step=ec_point2",
            [
                {"label": "數值", "name": "us2", "value": "12.88", "input": "number", "step": "0.01"},
                {
                    "label": "單位",
                    "name": "unit2",
                    "value": "ms",
                    "input": "select",
                    "options": [("us", "uS/cm"), ("ms", "mS/cm")],
                },
            ],
            message,
            refresh_s=refresh_s,
            value_html=value_html,
        )
    elif step == "orp_point":
        orp_v = _read_detail(status, "orp_v_sensor", "NA")
        orp_mv = _read_detail(status, "orp_mv", "NA")
        value_html = (
            '<span data-live-key="orp_v_sensor" data-live-unit=" V">{}</span>'
            " / "
            '<span data-live-key="orp_mv" data-live-unit=" mV">{}</span>'
        ).format(orp_v, orp_mv)
        html = render_calibration_step(
            server._base_path,
            "ORP 校正",
            "請將探頭放入 ORP 標準液，輸入目標 mV 後按確認",
            "",
            server._base_path + "/calibration?step=orp_point",
            [
                {"label": "目標 mV", "name": "target_mv", "value": "222", "input": "number", "step": "0.1"},
            ],
            message,
            refresh_s=refresh_s,
            value_html=value_html,
        )
    else:
        ph_last = cfg.get("ph", {}).get("last_calibration_iso", "NA")
        turb_last = cfg.get("turbidity", {}).get("last_calibration_iso", "NA")
        ec_last = cfg.get("ec", {}).get("last_calibration_iso", "NA")
        temp_last = cfg.get("ds18b20", {}).get("last_calibration_iso", "NA")
        orp_last = cfg.get("orp", {}).get("last_calibration_iso", "NA")
        content = """<p>校正完成。</p>
<ul>
  <li>pH：{ph}</li>
  <li>濁度：{turb}</li>
  <li>溫度：{temp}</li>
  <li>EC：{ec}</li>
  <li>ORP：{orp}</li>
</ul>
<p>是否切回一般模式？</p>
<form method="post" action="{action}">
  <input type="hidden" name="action" value="set_mode_normal" />
  <button class="btn" type="submit">切回一般模式</button>
</form>
<p><a class="btn secondary" href="{home}">維持校正模式</a></p>""".format(
            ph=ph_last,
            turb=turb_last,
            temp=temp_last,
            ec=ec_last,
            orp=orp_last,
            home=server._base_path + "/",
            action=server._base_path + "/calibration?step=done",
        )
        html = render_calibration_page(
            server._base_path, "校正完成", content, message, refresh_s=refresh_s
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
