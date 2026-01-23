from methods.adc_utils import create_adc, read_avg


# 初始化濁度感測器 ADC
def init_turbidity(pin):
    return create_adc(pin)


# 讀取濁度感測器電壓與原始值
def turbidity_read(adc, vref, air_threshold):
    raw = read_avg(adc)
    if raw < air_threshold:
        return None, raw, 0.0
    v = raw / 4095 * vref
    return round(v, 3), raw, v
