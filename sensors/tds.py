from methods.adc_utils import create_adc, read_avg
from methods.utils import get_date_iso


# 初始化 TDS 感測器 ADC
def init_tds(pin):
    return create_adc(pin)


# 讀取 TDS 並依溫度補償
def tds_read(adc, temp_c, vref, temp_compensation_factor, k_factor):
    tds_raw = read_avg(adc)
    tds_v = tds_raw / 4095 * vref
    temp_comp_coeff = 1.0 + temp_compensation_factor * (temp_c - 25.0)
    # 防呆：補償係數不可為 0 或負值
    if temp_comp_coeff <= 0:
        temp_comp_coeff = 0.1
    temp_comp_v = tds_v / temp_comp_coeff
    tds_ppm = (
        133.42 * temp_comp_v**3 - 258.7 * temp_comp_v**2 + 857.39 * temp_comp_v
    ) * k_factor
    # 防呆：TDS 不允許小於 0
    if tds_ppm < 0:
        tds_ppm = 0
    return round(tds_ppm, 2), tds_raw, round(tds_v, 3)


# 計算 TDS 基準值（k=1.0）
def _tds_base_ppm(v, temp_c, temp_compensation_factor):
    temp_comp_coeff = 1.0 + temp_compensation_factor * (temp_c - 25.0)
    if temp_comp_coeff <= 0:
        temp_comp_coeff = 0.1
    temp_comp_v = v / temp_comp_coeff
    return 133.42 * temp_comp_v**3 - 258.7 * temp_comp_v**2 + 857.39 * temp_comp_v


# 依校正點計算 k 係數
def calculate_tds_k(raw, temp_c, vref, temp_compensation_factor, target_ppm):
    v = raw / 4095 * vref
    base = _tds_base_ppm(v, temp_c, temp_compensation_factor)
    if base <= 0:
        return None, round(v, 3), base
    k_val = float(target_ppm) / float(base)
    return round(k_val, 4), round(v, 3), base


# 設定 TDS 校正（計算 k_factor）
def set_tds_calibration(adc, cfg, save_config_fn, target_ppm, temp_c, sample_count=10, delay_ms=3):
    raw = int(read_avg(adc, n=sample_count, delay_ms=delay_ms))
    vref = cfg.get("tds", {}).get("vref", 3.3)
    temp_factor = cfg.get("tds", {}).get("temp_compensation_factor", 0.02)
    k_val, v, base = calculate_tds_k(raw, temp_c, vref, temp_factor, target_ppm)
    if k_val is None:
        return None, v, base
    tds_cfg = cfg.get("tds", {})
    tds_cfg["k_factor"] = k_val
    tds_cfg["cal_ppm"] = float(target_ppm)
    tds_cfg["cal_v"] = v
    tds_cfg["cal_temp"] = float(temp_c)
    tds_cfg["last_calibration_iso"] = get_date_iso(
        cfg.get("time", {}).get("timezone_offset_s", 0)
    )
    cfg["tds"] = tds_cfg
    save_config_fn(cfg)
    return k_val, v, base
