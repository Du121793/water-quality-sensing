from methods.adc_utils import create_adc, read_avg
from methods.calibration import load_cal

_last_ph_values = []


# 初始化 pH 感測器 ADC
def init_ph(pin):
    return create_adc(pin)


# 依據電壓與溫度修正係數計算 k 值
def _k_at_T(k25, temp_c):
    temp_k = (temp_c if temp_c is not None else 25.0) + 273.15
    return k25 * (temp_k / 298.15)


# 平滑 pH 讀值以降低波動
def _smooth_ph_value(ph, smoothing_window):
    _last_ph_values.append(ph)
    if len(_last_ph_values) > smoothing_window:
        _last_ph_values.pop(0)

    if len(_last_ph_values) >= 2:
        return sum(_last_ph_values) / len(_last_ph_values)
    return ph


# 讀取 pH 感測器電壓
def ph_read_voltage(adc, vref):
    raw = read_avg(adc)
    v = raw / 4095 * vref
    return raw, v


# 計算 pH 值並回傳平滑後結果
def ph_value(adc, temp_c, cal_file, ph_cfg, adc_vref):
    d = load_cal(cal_file)
    raw, v = ph_read_voltage(adc, adc_vref)
    m = d.get("ph_m")
    b = d.get("ph_b")

    if isinstance(m, (int, float)) and isinstance(b, (int, float)):
        ph = m * v + b
    else:
        v7 = d.get("ph_V7", ph_cfg["v7_default"])
        k25 = d.get("ph_k25", ph_cfg["default_k25"])
        kT = max(_k_at_T(k25, temp_c), 1e-6)
        ph = 7.0 - (v - v7) / kT
        ph = 7.0 + (ph - 7.0) * ph_cfg["smoothing_factor"]

    if not isinstance(ph, (int, float)) or ph != ph:
        ph = 7.0

    ph = max(ph_cfg["min"], min(ph_cfg["max"], ph))
    ph_smoothed = _smooth_ph_value(ph, ph_cfg["smoothing_window"])
    return round(ph_smoothed, 2), raw, round(v, 3)
