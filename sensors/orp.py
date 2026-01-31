from methods.adc_utils import create_adc, read_avg
from methods.utils import safe_print, get_date_iso


# 初始化 ORP 感測器 ADC
def init_orp(pin):
    return create_adc(pin)


# 依溫度取得 ORP 標準液目標值（查表 + 線性插值）
def orp_target_mv_by_temp(temp_c):
    table = [
        (10.0, 262.0),
        (15.0, 249.0),
        (20.0, 236.0),
        (25.0, 222.0),
        (30.0, 209.0),
        (35.0, 196.0),
        (40.0, 183.0),
    ]
    if temp_c is None:
        return 222.0
    try:
        t = float(temp_c)
    except Exception:
        return 222.0

    if t <= table[0][0]:
        return table[0][1]
    if t >= table[-1][0]:
        return table[-1][1]

    for (t0, v0), (t1, v1) in zip(table, table[1:]):
        if t0 <= t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)

    return 222.0


# 讀取 ORP（以 ADC 電壓為主）
def orp_read(adc, orp_cfg, vref):
    sample_count = int(orp_cfg.get("sample_count", 15))
    delay_ms = int(orp_cfg.get("delay_ms", 3))
    raw = int(read_avg(adc, n=sample_count, delay_ms=delay_ms))
    if not isinstance(vref, (int, float)) or vref <= 0:
        return _orp_invalid(raw, None, None, "vref_invalid")
    v_adc = raw / 4095 * vref

    if raw < 10 or raw > 4085:
        return _orp_invalid(raw, v_adc, None, "raw_saturated")

    # 使用分壓參數回算感測器輸出電壓
    divider = orp_cfg.get("divider", {})
    r_top = divider.get("r_top")
    r_bot = divider.get("r_bot")
    if not isinstance(r_top, (int, float)) or not isinstance(r_bot, (int, float)) or r_bot <= 0:
        return _orp_invalid(raw, v_adc, None, "divider_invalid")
    v_sensor = v_adc * (r_top + r_bot) / r_bot

    if v_sensor < -0.1 or v_sensor > 4.2:
        return _orp_invalid(raw, v_adc, v_sensor, "v_sensor_out_of_range")

    scale = orp_cfg.get("scale", 1.0)
    if not isinstance(scale, (int, float)) or scale <= 0:
        scale = 1.0

    offset_mv = orp_cfg.get("offset_mv", 0.0)
    if not isinstance(offset_mv, (int, float)):
        offset_mv = 0.0
    if abs(offset_mv) > 3000:
        return _orp_invalid(raw, v_adc, v_sensor, "offset_out_of_range")

    # 0~4V 對應 -2000~+2000mV，2.0V 為 0mV
    orp_mv_no_offset = (v_sensor - 2.0) * 1000.0 * scale
    orp_mv = orp_mv_no_offset + offset_mv

    if orp_cfg.get("debug"):
        safe_print(
            "ORP Debug: raw={}, v_adc={:.3f}, v_sensor={:.3f}, orp_mv={}, no_offset={}".format(
                raw, v_adc, v_sensor, orp_mv, orp_mv_no_offset
            )
        )

    return {
        "raw": raw,
        "v_adc": round(v_adc, 3),
        "v_sensor": round(v_sensor, 3),
        "orp_mv": round(orp_mv, 2),
        "orp_mv_no_offset": round(orp_mv_no_offset, 2),
        "valid": True,
        "reason": "",
    }


# ORP 無效回傳
def _orp_invalid(raw, v_adc, v_sensor, reason):
    return {
        "raw": raw,
        "v_adc": round(v_adc, 3) if isinstance(v_adc, (int, float)) else None,
        "v_sensor": round(v_sensor, 3) if isinstance(v_sensor, (int, float)) else None,
        "orp_mv": None,
        "orp_mv_no_offset": None,
        "valid": False,
        "reason": reason,
    }


# 單點校正 ORP（標準液）
def set_orp_calibration(
    adc, cfg, save_config_fn, target_mv, sample_count=20, delay_ms=5
):
    orp_cfg = cfg.get("orp", {})
    raw = int(read_avg(adc, n=sample_count, delay_ms=delay_ms))
    vref = cfg.get("adc", {}).get("vref", 3.3)
    if not isinstance(vref, (int, float)) or vref <= 0:
        return None, None, None
    v_adc = raw / 4095 * vref

    divider = orp_cfg.get("divider", {})
    r_top = divider.get("r_top")
    r_bot = divider.get("r_bot")
    if not isinstance(r_top, (int, float)) or not isinstance(r_bot, (int, float)) or r_bot <= 0:
        return None, None, None
    v_sensor = v_adc * (r_top + r_bot) / r_bot

    scale = orp_cfg.get("scale", 1.0)
    if not isinstance(scale, (int, float)) or scale <= 0:
        scale = 1.0

    orp_mv_no_offset = (v_sensor - 2.0) * 1000.0 * scale
    offset_mv = float(target_mv) - float(orp_mv_no_offset)

    orp_cfg["offset_mv"] = round(offset_mv, 2)
    orp_cfg["cal_target_mv"] = float(target_mv)
    orp_cfg["cal_v_sensor"] = round(v_sensor, 3)
    orp_cfg["cal_raw"] = raw
    orp_cfg["last_calibration_iso"] = get_date_iso(
        cfg.get("time", {}).get("timezone_offset_s", 0)
    )
    cfg["orp"] = orp_cfg
    save_config_fn(cfg)

    return round(offset_mv, 2), round(v_sensor, 3), round(orp_mv_no_offset, 2)

