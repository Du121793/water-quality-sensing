import time
import onewire
import ds18x20
from machine import Pin


# 初始化 DS18B20 感測器
def init_ds18b20(pin):
    ow = onewire.OneWire(Pin(pin))
    ds = ds18x20.DS18X20(ow)
    roms = ds.scan()
    return ds, roms


# 讀取 DS18B20 溫度值
def ds_read(ds, roms):
    try:
        ds.convert_temp()
        time.sleep_ms(750)
        if roms:
            t = ds.read_temp(roms[0])
            return round(t, 2) if t is not None else -127.0
        return -127.0
    except Exception:
        return -127.0
