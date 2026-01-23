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
    for _ in range(n):
        total += adc.read()
        time.sleep_ms(delay_ms)
    return total // n
