from methods.adc_utils import create_adc, read_avg
from methods.utils import safe_print, get_date_iso


# 初始化 EC 感測器 ADC
def init_ec(pin):
    return create_adc(pin)


# 讀取 EC（以電壓為主）
def ec_read(adc, ec_cfg, vref):
    raw = read_avg(adc)
    v = raw / 4095 * vref

    cal_v1 = ec_cfg.get("cal_v1")
    cal_us1 = ec_cfg.get("cal_us1")
    cal_v2 = ec_cfg.get("cal_v2")
    cal_us2 = ec_cfg.get("cal_us2")

    ec_us = None
    if isinstance(cal_v1, (int, float)) and isinstance(cal_us1, (int, float)):
        if isinstance(cal_v2, (int, float)) and isinstance(cal_us2, (int, float)) and cal_v2 != cal_v1:
            # 兩點線性校正
            slope = (cal_us2 - cal_us1) / (cal_v2 - cal_v1)
            intercept = cal_us1 - slope * cal_v1
            ec_us = slope * v + intercept
        elif cal_v1 > 0:
            # 單點校正：假設 0V 對應 0uS
            slope = cal_us1 / cal_v1
            ec_us = slope * v

    if ec_us is not None and ec_us < 0:
        ec_us = 0.0

    if ec_cfg.get("debug"):
        safe_print(
            "EC Debug: raw={}, v={:.3f}, ec_us={}".format(raw, v, ec_us)
        )

    return {
        "raw": raw,
        "v": round(v, 3),
        "ec_us": round(ec_us, 2) if ec_us is not None else None,
    }


# 量測並記錄校正點 1
def set_ec_point1(adc, cfg, save_config_fn, us_cm, sample_count=10, delay_ms=3):
    raw = int(read_avg(adc, n=sample_count, delay_ms=delay_ms))
    vref = cfg.get("adc", {}).get("vref", 3.3)
    v = raw / 4095 * vref
    ec_cfg = cfg.get("ec", {})
    ec_cfg["cal_v1"] = v
    ec_cfg["cal_us1"] = float(us_cm)
    ec_cfg["last_calibration_iso"] = get_date_iso(
        cfg.get("time", {}).get("timezone_offset_s", 0)
    )
    cfg["ec"] = ec_cfg
    save_config_fn(cfg)
    return v, float(us_cm)


# 量測並記錄校正點 2
def set_ec_point2(adc, cfg, save_config_fn, us_cm, sample_count=10, delay_ms=3):
    raw = int(read_avg(adc, n=sample_count, delay_ms=delay_ms))
    vref = cfg.get("adc", {}).get("vref", 3.3)
    v = raw / 4095 * vref
    ec_cfg = cfg.get("ec", {})
    ec_cfg["cal_v2"] = v
    ec_cfg["cal_us2"] = float(us_cm)
    ec_cfg["last_calibration_iso"] = get_date_iso(
        cfg.get("time", {}).get("timezone_offset_s", 0)
    )
    cfg["ec"] = ec_cfg
    save_config_fn(cfg)
    return v, float(us_cm)
