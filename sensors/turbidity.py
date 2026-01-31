from methods.adc_utils import create_adc, read_avg
from methods.utils import safe_print, get_date_iso


# 初始化濁度感測器 ADC
def init_turbidity(pin):
    return create_adc(pin)


# 讀取濁度感測器資料（以 raw 為主）
def turbidity_read(adc, turb_cfg, vref):
    raw = read_avg(adc)
    if raw < turb_cfg.get("air_threshold", 0):
        return {"raw": raw, "percent": None, "ntu": None}

    raw0 = turb_cfg.get("raw0")
    raw_max = turb_cfg.get("raw_max")
    raw1 = turb_cfg.get("raw1")
    ntu1 = turb_cfg.get("ntu1")

    percent = None
    if isinstance(raw0, int) and isinstance(raw_max, int) and raw_max != raw0:
        # 支援遞增或遞減型輸出，統一用差值計算
        percent = (raw - raw0) * 100.0 / (raw_max - raw0)
        if percent < 0:
            percent = 0.0
        if percent > 100:
            percent = 100.0
        # 需要「數值越高越清」時，反轉百分比
        if turb_cfg.get("percent_clear_high", True):
            percent = 100.0 - percent

    ntu = None
    if (
        isinstance(raw0, int)
        and isinstance(raw1, int)
        and isinstance(ntu1, (int, float))
        and raw1 != raw0
    ):
        ntu = (raw - raw0) * (float(ntu1) / float(raw1 - raw0))
        if ntu < 0:
            ntu = 0.0

    v = raw / 4095 * vref
    if turb_cfg.get("debug"):
        safe_print(
            "Turbidity Debug: raw={}, v={:.3f}, percent={}, ntu={}".format(
                raw, v, percent, ntu
            )
        )

    return {
        "raw": raw,
        "percent": round(percent, 2) if percent is not None else None,
        "ntu": round(ntu, 2) if ntu is not None else None,
        "v": round(v, 3),
    }


# 讀取 N 次平均 raw
def _sample_raw(adc, sample_count=10, delay_ms=3):
    return int(read_avg(adc, n=sample_count, delay_ms=delay_ms))


# 設定 0 NTU 校正點（清水）
def set_turbidity_raw0(adc, cfg, save_config_fn, sample_count=10, delay_ms=3):
    raw0 = _sample_raw(adc, sample_count=sample_count, delay_ms=delay_ms)
    turb_cfg = cfg.get("turbidity", {})
    turb_cfg["raw0"] = raw0
    turb_cfg["last_calibration_iso"] = get_date_iso(
        cfg.get("time", {}).get("timezone_offset_s", 0)
    )
    cfg["turbidity"] = turb_cfg
    save_config_fn(cfg)
    return raw0


# 設定相對百分比上限點（最濁）
def set_turbidity_raw_max(adc, cfg, save_config_fn, sample_count=10, delay_ms=3):
    raw_max = _sample_raw(adc, sample_count=sample_count, delay_ms=delay_ms)
    turb_cfg = cfg.get("turbidity", {})
    turb_cfg["raw_max"] = raw_max
    turb_cfg["last_calibration_iso"] = get_date_iso(
        cfg.get("time", {}).get("timezone_offset_s", 0)
    )
    cfg["turbidity"] = turb_cfg
    save_config_fn(cfg)
    return raw_max


# 設定兩點校正第二點（raw1 -> ntu1）
def set_turbidity_two_point(
    adc, cfg, save_config_fn, ntu1, sample_count=10, delay_ms=3
):
    raw1 = _sample_raw(adc, sample_count=sample_count, delay_ms=delay_ms)
    turb_cfg = cfg.get("turbidity", {})
    turb_cfg["raw1"] = raw1
    turb_cfg["ntu1"] = float(ntu1)
    turb_cfg["last_calibration_iso"] = get_date_iso(
        cfg.get("time", {}).get("timezone_offset_s", 0)
    )
    cfg["turbidity"] = turb_cfg
    save_config_fn(cfg)
    return raw1, float(ntu1)
