import time
from machine import ADC, Pin


# 建立 ADC 物件並設定解析度
def create_adc(pin):
    adc = ADC(Pin(pin))
    adc.atten(ADC.ATTN_11DB)
    adc.width(ADC.WIDTH_12BIT)
    return adc


# 取樣多次後回傳平均值
def read_avg(adc, n=12, delay_ms=3):
    total = 0
    valid = 0
    for _ in range(n):
        try:
            reading = adc.read()
            if reading is not None and reading >= 0:
                total += reading
                valid += 1
            time.sleep_ms(delay_ms)
        except Exception:
            continue
    return total // max(valid, 1) if valid > 0 else 0
