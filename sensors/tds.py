from methods.adc_utils import create_adc, read_avg


# 初始化 TDS 感測器 ADC
def init_tds(pin):
    return create_adc(pin)


# 讀取 TDS 並依溫度補償
def tds_read(adc, temp_c, vref, temp_compensation_factor, k_factor):
    tds_raw = read_avg(adc)
    tds_v = tds_raw / 4095 * vref
    temp_comp_coeff = 1.0 + temp_compensation_factor * (temp_c - 25.0)
    temp_comp_v = tds_v / temp_comp_coeff
    tds_ppm = (
        133.42 * temp_comp_v**3 - 258.7 * temp_comp_v**2 + 857.39 * temp_comp_v
    ) * k_factor
    return round(tds_ppm, 2), tds_raw, round(tds_v, 3)
