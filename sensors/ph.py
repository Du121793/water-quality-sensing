import time

from methods.adc_utils import create_adc, read_avg
from methods.calibration import load_cal, save_cal
from methods.utils import safe_print

_last_ph_values = []


# 初始化 pH 感測器 ADC
def init_ph(pin):
    return create_adc(pin)


# 從電壓字典計算斜率與截距
def _calculate_ph_cal_params(voltages_dict):
    ph_values = [4.01, 7.0, 10.01]
    try:
        voltages = [
            voltages_dict["ph4"],
            voltages_dict["ph7"],
            voltages_dict["ph10"],
        ]
    except Exception:
        return None, None

    n = len(ph_values)
    sum_v = sum(voltages)
    sum_ph = sum(ph_values)
    sum_v2 = sum(v ** 2 for v in voltages)
    sum_vph = sum(v * ph for v, ph in zip(voltages, ph_values))
    denominator = (n * sum_v2 - sum_v ** 2)
    if abs(denominator) < 1e-9:
        return None, None
    m = (n * sum_vph - sum_v * sum_ph) / denominator
    b = (sum_ph - m * sum_v) / n
    return m, b


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


# 計算 pH 值並回傳結果
def ph_value(adc, temp_c, cal_file, ph_cfg, adc_vref):
    raw, v = ph_read_voltage(adc, adc_vref)

    voltages = ph_cfg.get("calibration_voltages", {})
    use_code_cal = bool(ph_cfg.get("use_code_calibration", True))
    cal_m, cal_b = _calculate_ph_cal_params(voltages)

    if use_code_cal and cal_m is not None and cal_b is not None:
        ph = cal_m * v + cal_b
        if ph_cfg.get("debug"):
            safe_print("PH Debug: raw={}, v={:.3f}, temp={}".format(raw, v, temp_c))
            safe_print("Code cal: m={}, b={}, ph={:.3f}".format(cal_m, cal_b, ph))
    else:
        d = load_cal(cal_file)
        m = d.get("ph_m")
        b = d.get("ph_b")
        if isinstance(m, (int, float)) and isinstance(b, (int, float)):
            ph = m * v + b
            if ph_cfg.get("debug"):
                safe_print("File cal: m={}, b={}, ph={:.3f}".format(m, b, ph))
        else:
            # 無可用校正資料時回 7.0
            ph = 7.0
            if ph_cfg.get("debug"):
                safe_print("No calibration data, using pH 7.0")

    if not isinstance(ph, (int, float)) or ph != ph:
        if ph_cfg.get("debug"):
            safe_print("Invalid pH, setting to 7.0")
        ph = 7.0

    ph = max(ph_cfg.get("min", 0.0), min(ph_cfg.get("max", 14.0), ph))

    smoothing_window = int(ph_cfg.get("smoothing_window", 1))
    if smoothing_window > 1:
        ph = _smooth_ph_value(ph, smoothing_window)

    if ph_cfg.get("debug"):
        safe_print("Final pH: {:.2f}".format(ph))
    return round(ph, 2), raw, round(v, 3)


# 三點 pH 校準：使用 pH 4、7、10 標準緩衝液
def ph_cal_three_points(
    adc,
    adc_vref,
    cal_file,
    ph4,
    ph7,
    ph10,
    temp_c=25.0,
    sample_count=10,
    wait_s=0.5,
):
    safe_print("=== 三點pH校準開始 ===")
    safe_print("請依序將感測器放入pH 4、7、10標準緩衝液中")
    voltages = []
    ph_values = [ph4, ph7, ph10]
    for ph_val in ph_values:
        safe_print("請將感測器放入pH {}緩衝液中，按Enter繼續...".format(ph_val))
        try:
            input()
        except Exception:
            pass
        readings = []
        for _ in range(sample_count):
            _, v = ph_read_voltage(adc, adc_vref)
            readings.append(v)
            time.sleep(wait_s)
        avg_voltage = sum(readings) / len(readings)
        voltages.append(avg_voltage)
        safe_print("pH {}: 電壓 = {:.3f}V".format(ph_val, avg_voltage))

    n = len(ph_values)
    sum_v = sum(voltages)
    sum_ph = sum(ph_values)
    sum_v2 = sum(v ** 2 for v in voltages)
    sum_vph = sum(v * ph for v, ph in zip(voltages, ph_values))
    denominator = (n * sum_v2 - sum_v ** 2)
    if abs(denominator) < 1e-9:
        safe_print("校準失敗：斜率計算分母為零")
        return None, None

    m = (n * sum_vph - sum_v * sum_ph) / denominator
    b = (sum_ph - m * sum_v) / n

    d = load_cal(cal_file)
    d["ph_m"] = m
    d["ph_b"] = b
    d["ph_cal_points"] = {
        "ph4": {"ph": ph4, "voltage": voltages[0]},
        "ph7": {"ph": ph7, "voltage": voltages[1]},
        "ph10": {"ph": ph10, "voltage": voltages[2]},
    }
    d["ph_cal_temp"] = temp_c
    save_cal(cal_file, d)

    safe_print("校準完成！")
    safe_print("斜率 m = {:.6f}".format(m))
    safe_print("截距 b = {:.6f}".format(b))
    safe_print("校正公式: pH = {:.6f} * V + {:.6f}".format(m, b))

    safe_print("\n=== 校準驗證 ===")
    for ph_val, v in zip(ph_values, voltages):
        calculated_ph = m * v + b
        error = abs(calculated_ph - ph_val)
        safe_print(
            "pH {}: 實際={}, 計算={:.2f}, 誤差={:.2f}".format(
                ph_val, ph_val, calculated_ph, error
            )
        )
    return m, b


# 自動三點 pH 校準：直接提供三個電壓值
def ph_cal_three_points_auto(
    cal_file, ph4_voltage, ph7_voltage, ph10_voltage, temp_c=25.0
):
    safe_print("=== 自動三點pH校準 ===")
    ph_values = [4.0, 7.0, 10.0]
    voltages = [ph4_voltage, ph7_voltage, ph10_voltage]
    for label, v in zip(("4.0", "7.0", "10.0"), voltages):
        safe_print("pH {}: 電壓 = {:.3f}V".format(label, v))

    n = len(ph_values)
    sum_v = sum(voltages)
    sum_ph = sum(ph_values)
    sum_v2 = sum(v ** 2 for v in voltages)
    sum_vph = sum(v * ph for v, ph in zip(voltages, ph_values))
    denominator = (n * sum_v2 - sum_v ** 2)
    if abs(denominator) < 1e-9:
        safe_print("校準失敗：斜率計算分母為零")
        return None, None

    m = (n * sum_vph - sum_v * sum_ph) / denominator
    b = (sum_ph - m * sum_v) / n

    d = load_cal(cal_file)
    d["ph_m"] = m
    d["ph_b"] = b
    d["ph_cal_points"] = {
        "ph4": {"ph": 4.0, "voltage": ph4_voltage},
        "ph7": {"ph": 7.0, "voltage": ph7_voltage},
        "ph10": {"ph": 10.0, "voltage": ph10_voltage},
    }
    d["ph_cal_temp"] = temp_c
    save_cal(cal_file, d)

    safe_print("校準完成！")
    safe_print("斜率 m = {:.6f}".format(m))
    safe_print("截距 b = {:.6f}".format(b))
    safe_print("校正公式: pH = {:.6f} * V + {:.6f}".format(m, b))

    safe_print("\n=== 校準驗證 ===")
    for ph_val, v in zip(ph_values, voltages):
        calculated_ph = m * v + b
        error = abs(calculated_ph - ph_val)
        safe_print(
            "pH {}: 實際={}, 計算={:.2f}, 誤差={:.2f}".format(
                ph_val, ph_val, calculated_ph, error
            )
        )
    return m, b


# 使用配置電壓進行三點校正
def ph_cal_from_config(cal_file, ph_cfg):
    safe_print("=== 使用配置電壓進行三點校正 ===")
    voltages_cfg = ph_cfg.get("calibration_voltages", {})
    ph4_voltage = voltages_cfg.get("ph4")
    ph7_voltage = voltages_cfg.get("ph7")
    ph10_voltage = voltages_cfg.get("ph10")

    if ph4_voltage is None or ph7_voltage is None or ph10_voltage is None:
        safe_print("校準失敗：缺少校正電壓")
        return None, None

    safe_print("使用配置的校正電壓值：")
    safe_print("pH 4.01: {}V".format(ph4_voltage))
    safe_print("pH 7.0: {}V".format(ph7_voltage))
    safe_print("pH 10.01: {}V".format(ph10_voltage))

    ph_values = [4.01, 7.0, 10.01]
    voltages = [ph4_voltage, ph7_voltage, ph10_voltage]

    n = len(ph_values)
    sum_v = sum(voltages)
    sum_ph = sum(ph_values)
    sum_v2 = sum(v ** 2 for v in voltages)
    sum_vph = sum(v * ph for v, ph in zip(voltages, ph_values))
    denominator = (n * sum_v2 - sum_v ** 2)
    if abs(denominator) < 1e-9:
        safe_print("校準失敗：斜率計算分母為零")
        return None, None

    m = (n * sum_vph - sum_v * sum_ph) / denominator
    b = (sum_ph - m * sum_v) / n

    d = load_cal(cal_file)
    d["ph_m"] = m
    d["ph_b"] = b
    d["ph_cal_points"] = {
        "ph4": {"ph": 4.01, "voltage": ph4_voltage},
        "ph7": {"ph": 7.0, "voltage": ph7_voltage},
        "ph10": {"ph": 10.01, "voltage": ph10_voltage},
    }
    d["ph_cal_temp"] = 25.0
    save_cal(cal_file, d)

    safe_print("校準完成！")
    safe_print("斜率 m = {:.6f}".format(m))
    safe_print("截距 b = {:.6f}".format(b))
    safe_print("校正公式: pH = {:.6f} * V + {:.6f}".format(m, b))

    safe_print("\n=== 校準驗證 ===")
    for ph_val, v in zip(ph_values, voltages):
        calculated_ph = m * v + b
        error = abs(calculated_ph - ph_val)
        safe_print(
            "pH {}: 實際={}, 計算={:.2f}, 誤差={:.2f}".format(
                ph_val, ph_val, calculated_ph, error
            )
        )
    return m, b


# 計算校正參數（用於修改電壓值後重新計算）
def calculate_ph_calibration_params(ph_cfg):
    voltages_cfg = ph_cfg.get("calibration_voltages", {})
    ph_values = [4.01, 7.0, 10.01]
    try:
        voltages = [
            voltages_cfg["ph4"],
            voltages_cfg["ph7"],
            voltages_cfg["ph10"],
        ]
    except Exception:
        safe_print("校準失敗：缺少校正電壓")
        return None, None

    n = len(ph_values)
    sum_v = sum(voltages)
    sum_ph = sum(ph_values)
    sum_v2 = sum(v ** 2 for v in voltages)
    sum_vph = sum(v * ph for v, ph in zip(voltages, ph_values))
    denominator = (n * sum_v2 - sum_v ** 2)
    if abs(denominator) < 1e-9:
        safe_print("校準失敗：斜率計算分母為零")
        return None, None

    m = (n * sum_vph - sum_v * sum_ph) / denominator
    b = (sum_ph - m * sum_v) / n

    safe_print("=== 校正參數計算結果 ===")
    safe_print("電壓值：")
    safe_print("  pH 4.01: {}V".format(voltages[0]))
    safe_print("  pH 7.0: {}V".format(voltages[1]))
    safe_print("  pH 10.01: {}V".format(voltages[2]))
    safe_print("")
    safe_print("計算結果：")
    safe_print("PH_CAL_M = {:.6f}  # 斜率".format(m))
    safe_print("PH_CAL_B = {:.6f}  # 截距".format(b))
    safe_print("校正公式: pH = {:.6f} * V + {:.6f}".format(m, b))

    safe_print("\n驗證結果：")
    for ph_val, v in zip(ph_values, voltages):
        calculated_ph = m * v + b
        error = abs(calculated_ph - ph_val)
        safe_print(
            "pH {}: 實際={}, 計算={:.2f}, 誤差={:.2f}".format(
                ph_val, ph_val, calculated_ph, error
            )
        )
    return m, b


# 檢查 pH 校正狀態
def check_ph_calibration(ph_cfg):
    voltages_cfg = ph_cfg.get("calibration_voltages", {})
    cal_m, cal_b = _calculate_ph_cal_params(voltages_cfg)

    safe_print("=== pH校正狀態檢查 ===")
    safe_print("程式碼中的校正參數：")
    if cal_m is None or cal_b is None:
        safe_print("  尚未設定三點校正電壓")
    else:
        safe_print("  PH_CAL_M = {}".format(cal_m))
        safe_print("  PH_CAL_B = {}".format(cal_b))
        safe_print("  校正公式: pH = {} * V + {}".format(cal_m, cal_b))
    safe_print("\n校正電壓值：")
    safe_print("  pH 4.01: {}V".format(voltages_cfg.get("ph4")))
    safe_print("  pH 7.0: {}V".format(voltages_cfg.get("ph7")))
    safe_print("  pH 10.01: {}V".format(voltages_cfg.get("ph10")))
    return True
