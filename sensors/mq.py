import time
from methods.adc_utils import create_adc, read_avg
from methods.calibration import load_cal, save_cal


# 初始化 MQ 感測器 ADC
def init_mq(pin_135, pin_137):
    return create_adc(pin_135), create_adc(pin_137)


# 空氣中校正 MQ 感測器基準值
def mq_air_calibrate(adc135, adc137, cal_file, duration_s=30):
    t0 = time.time()
    s135, s137 = [], []
    while time.time() - t0 < duration_s:
        s135.append(read_avg(adc135, n=8))
        s137.append(read_avg(adc137, n=8))
    r0_135 = sum(s135) // len(s135)
    r0_137 = sum(s137) // len(s137)
    d = load_cal(cal_file)
    d["mq135_r0"] = r0_135
    d["mq137_r0"] = r0_137
    save_cal(cal_file, d)
    return r0_135, r0_137


# 讀取 MQ 感測器數值與倍率
def mq_read(adc135, adc137, cal_file):
    raw135 = read_avg(adc135)
    raw137 = read_avg(adc137)
    d = load_cal(cal_file)
    r0_135 = d.get("mq135_r0")
    r0_137 = d.get("mq137_r0")
    ratio135 = (raw135 / max(r0_135, 1)) if r0_135 else None
    ratio137 = (raw137 / max(r0_137, 1)) if r0_137 else None
    return {
        "raw135": raw135,
        "raw137": raw137,
        "ratio135": ratio135,
        "ratio137": ratio137,
    }
