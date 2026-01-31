from .common import _to_float, _to_int, _to_bool



# 建立感測器表單欄位
def build_sensor_fields(cfg):
    adc = cfg.get("adc", {})
    ph = cfg.get("ph", {})
    turb = cfg.get("turbidity", {})
    mq = cfg.get("mq", {})
    ds = cfg.get("ds18b20", {})
    tds = cfg.get("tds", {})
    ec = cfg.get("ec", {})
    orp = cfg.get("orp", {})
    web_cfg = cfg.get("web", {})
    base_path = "/" + web_cfg.get("base_path", "admin").strip("/")
    data_url = base_path + "/calibration/data"
    return [
        {"type": "section", "label": "ADC"},
        {
            "label": "ADC 參考電壓",
            "name": "adc_vref",
            "value": adc.get("vref", 3.3),
            "input": "number",
            "step": "0.01",
        },
        {"type": "section", "label": "pH"},
        {"label": "pH 腳位", "name": "ph_pin", "value": ph.get("pin", 0), "input": "number"},
        {"label": "pH 最小值", "name": "ph_min", "value": ph.get("min", 0.0), "input": "number", "step": "0.01"},
        {"label": "pH 最大值", "name": "ph_max", "value": ph.get("max", 14.0), "input": "number", "step": "0.01"},
        {"label": "平滑視窗", "name": "ph_smoothing_window", "value": ph.get("smoothing_window", 5), "input": "number"},
        {"type": "section", "label": "pH 校正"},
        {"label": "使用程式校正", "name": "ph_use_code_calibration", "value": "1" if ph.get("use_code_calibration", True) else "0", "input": "select", "options": [("1", "啟用"), ("0", "停用")]},
        {"label": "校正電壓 pH4.01", "name": "ph_cal_voltage_ph4", "value": ph.get("calibration_voltages", {}).get("ph4", 0.0), "input": "number", "step": "0.001"},
        {"label": "校正電壓 pH7.0", "name": "ph_cal_voltage_ph7", "value": ph.get("calibration_voltages", {}).get("ph7", 0.0), "input": "number", "step": "0.001"},
        {"label": "校正電壓 pH10.01", "name": "ph_cal_voltage_ph10", "value": ph.get("calibration_voltages", {}).get("ph10", 0.0), "input": "number", "step": "0.001"},
        {"type": "section", "label": "pH 分壓"},
        {"label": "分壓電阻上 (Ohm)", "name": "ph_divider_r_top", "value": ph.get("divider", {}).get("r_top", 0), "input": "number"},
        {"label": "分壓電阻下 (Ohm)", "name": "ph_divider_r_bot", "value": ph.get("divider", {}).get("r_bot", 0), "input": "number"},
        {"label": "pH 除錯輸出", "name": "ph_debug", "value": "1" if ph.get("debug", False) else "0", "input": "select", "options": [("1", "啟用"), ("0", "停用")]},
        {"type": "section", "label": "濁度"},
        {"label": "濁度腳位", "name": "turbidity_pin", "value": turb.get("pin", 0), "input": "number"},
        {"label": "空氣閾值", "name": "turbidity_air_threshold", "value": turb.get("air_threshold", 0), "input": "number"},
        {"label": "raw0 (0 NTU)", "name": "turbidity_raw0", "value": "" if turb.get("raw0") is None else turb.get("raw0"), "input": "number"},
        {"label": "raw_max (%上限)", "name": "turbidity_raw_max", "value": "" if turb.get("raw_max") is None else turb.get("raw_max"), "input": "number"},
        {"label": "raw1 (NTU校正點)", "name": "turbidity_raw1", "value": "" if turb.get("raw1") is None else turb.get("raw1"), "input": "number"},
        {"label": "ntu1 (raw1 對應)", "name": "turbidity_ntu1", "value": "" if turb.get("ntu1") is None else turb.get("ntu1"), "input": "number", "step": "0.01"},
        {
            "label": "百分比代表清澈度",
            "name": "turbidity_percent_clear_high",
            "value": "1" if turb.get("percent_clear_high", True) else "0",
            "input": "select",
            "options": [("1", "是（高=清）"), ("0", "否（高=濁）")],
        },
        {"type": "section", "label": "MQ135 / MQ137"},
        {"label": "MQ135 腳位", "name": "mq_pin_135", "value": mq.get("pin_135", 0), "input": "number"},
        {"label": "MQ137 腳位", "name": "mq_pin_137", "value": mq.get("pin_137", 0), "input": "number"},
        {"type": "section", "label": "DS18B20"},
        {"label": "淺層腳位", "name": "ds18b20_pin_shallow", "value": ds.get("pin_shallow", 0), "input": "number"},
        {"label": "深層腳位", "name": "ds18b20_pin_deep", "value": ds.get("pin_deep", 0), "input": "number"},
        {"label": "淺層偏移量", "name": "ds18b20_shallow_offset", "value": ds.get("shallow_offset", 0.0), "input": "number", "step": "0.001"},
        {"label": "淺層比例係數", "name": "ds18b20_shallow_scale", "value": ds.get("shallow_scale", 1.0), "input": "number", "step": "0.001"},
        {"type": "section", "label": "TDS"},
        {"label": "TDS 腳位", "name": "tds_pin", "value": tds.get("pin", 0), "input": "number"},
        {"label": "TDS 參考電壓", "name": "tds_vref", "value": tds.get("vref", 3.3), "input": "number", "step": "0.01"},
        {"label": "溫度補償係數", "name": "tds_temp_compensation_factor", "value": tds.get("temp_compensation_factor", 0.5), "input": "number", "step": "0.01"},
        {"label": "TDS K 係數", "name": "tds_k_factor", "value": tds.get("k_factor", 0.5), "input": "number", "step": "0.01"},
        {"type": "section", "label": "EC"},
        {"label": "EC 腳位", "name": "ec_pin", "value": ec.get("pin", 0), "input": "number"},
        {"label": "校正電壓點1", "name": "ec_cal_v1", "value": "" if ec.get("cal_v1") is None else ec.get("cal_v1"), "input": "number", "step": "0.001"},
        {"label": "校正電導點1 (uS/cm)", "name": "ec_cal_us1", "value": "" if ec.get("cal_us1") is None else ec.get("cal_us1"), "input": "number", "step": "0.1"},
        {"label": "校正電壓點2", "name": "ec_cal_v2", "value": "" if ec.get("cal_v2") is None else ec.get("cal_v2"), "input": "number", "step": "0.001"},
        {"label": "校正電導點2 (uS/cm)", "name": "ec_cal_us2", "value": "" if ec.get("cal_us2") is None else ec.get("cal_us2"), "input": "number", "step": "0.1"},
        {"label": "分壓電阻上 (Ohm)", "name": "ec_divider_r_top", "value": ec.get("divider", {}).get("r_top", 0), "input": "number"},
        {"label": "分壓電阻下 (Ohm)", "name": "ec_divider_r_bot", "value": ec.get("divider", {}).get("r_bot", 0), "input": "number"},
        {"label": "EC 除錯輸出", "name": "ec_debug", "value": "1" if ec.get("debug", False) else "0", "input": "select", "options": [("1", "啟用"), ("0", "停用")]},
        {"type": "section", "label": "ORP"},
        {"label": "ORP 腳位", "name": "orp_pin", "value": orp.get("pin", 0), "input": "number"},
        {"label": "ORP 縮放係數", "name": "orp_scale", "value": orp.get("scale", 1.0), "input": "number", "step": "0.01"},
        {"label": "ORP 偏移量 (mV)", "name": "orp_offset_mv", "value": orp.get("offset_mv", 0.0), "input": "number", "step": "0.1"},
        {"label": "分壓電阻上 (Ohm)", "name": "orp_divider_r_top", "value": orp.get("divider", {}).get("r_top", 0), "input": "number"},
        {"label": "分壓電阻下 (Ohm)", "name": "orp_divider_r_bot", "value": orp.get("divider", {}).get("r_bot", 0), "input": "number"},
        {"label": "取樣次數", "name": "orp_sample_count", "value": orp.get("sample_count", 15), "input": "number"},
        {"label": "取樣間隔 (ms)", "name": "orp_delay_ms", "value": orp.get("delay_ms", 3), "input": "number"},
        {"label": "ORP 除錯輸出", "name": "orp_debug", "value": "1" if orp.get("debug", False) else "0", "input": "select", "options": [("1", "啟用"), ("0", "停用")]},
        {
            "type": "html",
            "html": "<tr><th>ORP 即時讀值</th><td><span data-live-key=\"orp_v_sensor\">NA</span> V / <span data-live-key=\"orp_mv\">NA</span> mV</td></tr>",
        },
        {
            "type": "html",
            "html": """<tr><td colspan="2"><script>
(function() {{
  var inFlight = false;
  function fmt(val) {{
    if (val === null || val === undefined) return "NA";
    if (typeof val === "number") {{
      return (Math.round(val * 100) / 100).toString();
    }}
    return String(val);
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
            var values = data.values || {{}};
            var nodes = document.querySelectorAll("[data-live-key]");
            for (var i = 0; i < nodes.length; i++) {{
              var key = nodes[i].getAttribute("data-live-key");
              nodes[i].textContent = fmt(values[key]);
            }}
          }} catch (e) {{}}
        }}
        inFlight = false;
      }}
    }};
    xhr.send();
  }}
  update();
  setInterval(update, 2000);
}})();
</script></td></tr>""".format(
                data_url=data_url
            ),
        },
    ]


# 套用感測器表單資料



# 套用感測器表單資料
def apply_sensor_form(cfg, form):
    adc = cfg.get("adc", {})
    ph = cfg.get("ph", {})
    turb = cfg.get("turbidity", {})
    mq = cfg.get("mq", {})
    ds = cfg.get("ds18b20", {})
    tds = cfg.get("tds", {})
    orp_cfg = cfg.get("orp", {})

    adc["vref"] = _to_float(form.get("adc_vref"), adc.get("vref", 3.3))
    ph["pin"] = _to_int(form.get("ph_pin"), ph.get("pin", 0))
    ph["min"] = _to_float(form.get("ph_min"), ph.get("min", 0.0))
    ph["max"] = _to_float(form.get("ph_max"), ph.get("max", 14.0))
    ph["smoothing_window"] = _to_int(
        form.get("ph_smoothing_window"), ph.get("smoothing_window", 5)
    )
    ph["use_code_calibration"] = _to_bool(
        form.get("ph_use_code_calibration"),
        ph.get("use_code_calibration", True),
    )
    cal_voltages = ph.get("calibration_voltages", {})
    cal_voltages["ph4"] = _to_float(
        form.get("ph_cal_voltage_ph4"), cal_voltages.get("ph4", 0.0)
    )
    cal_voltages["ph7"] = _to_float(
        form.get("ph_cal_voltage_ph7"), cal_voltages.get("ph7", 0.0)
    )
    cal_voltages["ph10"] = _to_float(
        form.get("ph_cal_voltage_ph10"), cal_voltages.get("ph10", 0.0)
    )
    ph["calibration_voltages"] = cal_voltages
    divider = ph.get("divider", {})
    divider["r_top"] = _to_float(
        form.get("ph_divider_r_top"), divider.get("r_top", 0)
    )
    divider["r_bot"] = _to_float(
        form.get("ph_divider_r_bot"), divider.get("r_bot", 0)
    )
    ph["divider"] = divider
    ph["debug"] = _to_bool(
        form.get("ph_debug"),
        ph.get("debug", False),
    )

    turb["pin"] = _to_int(form.get("turbidity_pin"), turb.get("pin", 0))
    turb["air_threshold"] = _to_int(
        form.get("turbidity_air_threshold"), turb.get("air_threshold", 0)
    )
    raw0 = form.get("turbidity_raw0", "").strip()
    raw_max = form.get("turbidity_raw_max", "").strip()
    raw1 = form.get("turbidity_raw1", "").strip()
    ntu1 = form.get("turbidity_ntu1", "").strip()
    turb["raw0"] = _to_int(raw0, None) if raw0 != "" else None
    turb["raw_max"] = _to_int(raw_max, None) if raw_max != "" else None
    turb["raw1"] = _to_int(raw1, None) if raw1 != "" else None
    turb["ntu1"] = _to_float(ntu1, None) if ntu1 != "" else None
    turb["percent_clear_high"] = _to_bool(
        form.get("turbidity_percent_clear_high"),
        turb.get("percent_clear_high", True),
    )

    mq["pin_135"] = _to_int(form.get("mq_pin_135"), mq.get("pin_135", 0))
    mq["pin_137"] = _to_int(form.get("mq_pin_137"), mq.get("pin_137", 0))

    ds["pin_shallow"] = _to_int(
        form.get("ds18b20_pin_shallow"), ds.get("pin_shallow", 0)
    )
    ds["pin_deep"] = _to_int(
        form.get("ds18b20_pin_deep"), ds.get("pin_deep", 0)
    )
    ds["shallow_offset"] = _to_float(
        form.get("ds18b20_shallow_offset"), ds.get("shallow_offset", 0.0)
    )
    ds["shallow_scale"] = _to_float(
        form.get("ds18b20_shallow_scale"), ds.get("shallow_scale", 1.0)
    )

    tds["pin"] = _to_int(form.get("tds_pin"), tds.get("pin", 0))
    tds["vref"] = _to_float(form.get("tds_vref"), tds.get("vref", 3.3))
    tds["temp_compensation_factor"] = _to_float(
        form.get("tds_temp_compensation_factor"),
        tds.get("temp_compensation_factor", 0.5),
    )
    tds["k_factor"] = _to_float(
        form.get("tds_k_factor"), tds.get("k_factor", 0.5)
    )
    ec_cfg = cfg.get("ec", {})
    ec_cfg["pin"] = _to_int(form.get("ec_pin"), ec_cfg.get("pin", 0))
    ec_cfg["cal_v1"] = _to_float(form.get("ec_cal_v1"), ec_cfg.get("cal_v1"))
    ec_cfg["cal_us1"] = _to_float(form.get("ec_cal_us1"), ec_cfg.get("cal_us1"))
    ec_cfg["cal_v2"] = _to_float(form.get("ec_cal_v2"), ec_cfg.get("cal_v2"))
    ec_cfg["cal_us2"] = _to_float(form.get("ec_cal_us2"), ec_cfg.get("cal_us2"))
    ec_div = ec_cfg.get("divider", {})
    ec_div["r_top"] = _to_float(
        form.get("ec_divider_r_top"), ec_div.get("r_top", 0)
    )
    ec_div["r_bot"] = _to_float(
        form.get("ec_divider_r_bot"), ec_div.get("r_bot", 0)
    )
    ec_cfg["divider"] = ec_div
    ec_cfg["debug"] = _to_bool(form.get("ec_debug"), ec_cfg.get("debug", False))

    orp_cfg["pin"] = _to_int(form.get("orp_pin"), orp_cfg.get("pin", 0))
    orp_cfg["scale"] = _to_float(form.get("orp_scale"), orp_cfg.get("scale", 1.0))
    orp_cfg["offset_mv"] = _to_float(
        form.get("orp_offset_mv"), orp_cfg.get("offset_mv", 0.0)
    )
    orp_div = orp_cfg.get("divider", {})
    orp_div["r_top"] = _to_float(
        form.get("orp_divider_r_top"), orp_div.get("r_top", 0)
    )
    orp_div["r_bot"] = _to_float(
        form.get("orp_divider_r_bot"), orp_div.get("r_bot", 0)
    )
    orp_cfg["divider"] = orp_div
    orp_cfg["sample_count"] = _to_int(
        form.get("orp_sample_count"), orp_cfg.get("sample_count", 15)
    )
    orp_cfg["delay_ms"] = _to_int(
        form.get("orp_delay_ms"), orp_cfg.get("delay_ms", 3)
    )
    orp_cfg["debug"] = _to_bool(form.get("orp_debug"), orp_cfg.get("debug", False))

    cfg["adc"] = adc
    cfg["ph"] = ph
    cfg["turbidity"] = turb
    cfg["mq"] = mq
    cfg["ds18b20"] = ds
    cfg["tds"] = tds
    cfg["ec"] = ec_cfg
    cfg["orp"] = orp_cfg
    return True, "感測器設定已儲存"


# 建立系統表單欄位
