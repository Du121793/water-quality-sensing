import time
import onewire
import ds18x20
from machine import Pin

from methods.utils import safe_print


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


# 讀取溫度並應用校正（僅對淺層感測器）
def ds_read_corrected(ds, roms, offset, scale, is_shallow=False):
    temp = ds_read(ds, roms)
    if temp == -127.0:
        return temp
    if is_shallow:
        corrected = (temp * scale) + offset
        safe_print(
            "Temp correction: raw={}, scale={}, offset={}, corrected={:.2f}".format(
                temp, scale, offset, corrected
            )
        )
        return round(corrected, 2)
    return temp


# 計算溫度校正參數
def calculate_temp_calibration(
    ds_s, roms_s, ds_d, roms_d, sample_count=10, delay_s=1
):
    safe_print("=== 溫度校正參數計算 ===")
    safe_print("請將兩個溫度感測器放在同一環境中，等待讀數穩定...")
    shallow_readings = []
    deep_readings = []
    for i in range(sample_count):
        shallow_temp = ds_read(ds_s, roms_s)
        deep_temp = ds_read(ds_d, roms_d)
        if shallow_temp != -127.0 and deep_temp != -127.0:
            shallow_readings.append(shallow_temp)
            deep_readings.append(deep_temp)
        time.sleep(delay_s)
        safe_print(
            "讀取 {}/{}: 淺層={}C, 深層={}C".format(
                i + 1, sample_count, shallow_temp, deep_temp
            )
        )
    if len(shallow_readings) < 5:
        safe_print("讀取次數不足，無法計算校正參數")
        return None, None
    avg_shallow = sum(shallow_readings) / len(shallow_readings)
    avg_deep = sum(deep_readings) / len(deep_readings)
    safe_print("\n平均溫度：")
    safe_print("  淺層感測器: {:.2f}C".format(avg_shallow))
    safe_print("  深層感測器: {:.2f}C".format(avg_deep))
    safe_print("  誤差: {:.2f}C".format(abs(avg_shallow - avg_deep)))
    offset = avg_deep - avg_shallow
    scale = 1.0
    safe_print("\n計算結果：")
    safe_print("  TEMP_SHALLOW_OFFSET = {:.3f}".format(offset))
    safe_print("  TEMP_SHALLOW_SCALE = {:.3f}".format(scale))
    safe_print(
        "  校正公式: corrected_temp = (raw_temp * {:.3f}) + {:.3f}".format(
            scale, offset
        )
    )
    corrected_shallow = (avg_shallow * scale) + offset
    error = abs(corrected_shallow - avg_deep)
    safe_print("\n驗證結果：")
    safe_print("  校正前淺層: {:.2f}C".format(avg_shallow))
    safe_print("  校正後淺層: {:.2f}C".format(corrected_shallow))
    safe_print("  深層基準: {:.2f}C".format(avg_deep))
    safe_print("  校正誤差: {:.2f}C".format(error))
    return offset, scale


# 檢查溫度校正狀態
def check_temp_calibration(ds_s, roms_s, ds_d, roms_d, offset, scale):
    safe_print("=== 溫度校正狀態檢查 ===")
    safe_print("校正參數：")
    safe_print("  TEMP_SHALLOW_OFFSET = {}".format(offset))
    safe_print("  TEMP_SHALLOW_SCALE = {}".format(scale))
    safe_print(
        "  校正公式: corrected_temp = (raw_temp * {}) + {}".format(scale, offset)
    )
    shallow_temp = ds_read(ds_s, roms_s)
    deep_temp = ds_read(ds_d, roms_d)
    corrected_shallow = ds_read_corrected(
        ds_s, roms_s, offset, scale, is_shallow=True
    )
    safe_print("\n當前讀數：")
    safe_print("  淺層原始: {}C".format(shallow_temp))
    safe_print("  淺層校正: {}C".format(corrected_shallow))
    safe_print("  深層基準: {}C".format(deep_temp))
    if shallow_temp != -127.0 and deep_temp != -127.0:
        error = abs(corrected_shallow - deep_temp)
        safe_print("  校正誤差: {:.2f}C".format(error))
    return True
