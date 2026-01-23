import json, time, network, machine
from machine import Pin, ADC
import onewire, ds18x20
import urequests
import neopixel
import ntptime
import esp

# -------- Wi-Fi / API --------
# Primary WiFi credentials
SSID_BACKUP = "YOUR_WIFI_SSID"
PASSWORD_BACKUP = "replace_with_local_secret"

# Backup WiFi credentials
SSID_PRIMARY = "YOUR_WIFI_SSID"
PASSWORD_PRIMARY = "replace_with_local_secret"

API_URL = "http://192.168.100.142:3002/include"
USE_STATIC_IP = False
# STATIC_IFCFG = ("192.168.1.123", "255.255.255.0", "192.168.1.1", "8.8.8.8")

# Data transmission interval (seconds)
DATA_INTERVAL = 30

# Auto reset settings
MAX_CONNECTION_ATTEMPTS = 10  # 最大連接嘗試次數

CAL_FILE = "cal.json"
PH_MAX = 14.0
PH_MIN = 0.0
DEFAULT_PH_K_25C = 0.0592  # 標準pH感測器斜率 (59.2mV/pH at 25°C)

TIMEZONE_OFFSET = 8 * 3600

# -------- ESP32 GPIO Pins --------
# 根據 NodeMCU-32S 引腳圖修改
PH_PIN = 36        # GPIO36 (ADC0) - pH 感測器
TURB_PIN = 39      # GPIO39 (ADC3) - 濁度感測器
MQ135_PIN = 32     # GPIO32 (ADC4) - MQ135 感測器
MQ137_PIN = 33     # GPIO33 (ADC5) - MQ137 感測器
DS_S_PIN = 14      # GPIO14 (TOUCH6) - 淺層溫度感測器
DS_D_PIN = 27      # GPIO27 (TOUCH7) - 深層溫度感測器
TDS_PIN = 34       # GPIO34 (ADC6) - TDS 感測器
TURBIDITY_AIR_THRESHOLD = 120

# -------- TDS --------
TDS_VREF = 3.3
TDS_TEMP_COMPENSATION_FACTOR = 0.5
TDS_K_FACTOR = 0.5

# -------- LED --------
LED_PIN = 2        # GPIO2 (TOUCH2) - NeoPixel LED
LED_NUM = 1
np = neopixel.NeoPixel(Pin(LED_PIN), LED_NUM)

def set_led_color(r, g, b):
    np[0] = (r, g, b)
    np.write()

# -------- ADC --------
def _adc(pin):
    a = ADC(Pin(pin))
    a.atten(ADC.ATTN_11DB)
    a.width(ADC.WIDTH_12BIT)
    return a

adc_ph = _adc(PH_PIN)
adc_turb = _adc(TURB_PIN)
adc135 = _adc(MQ135_PIN)
adc137 = _adc(MQ137_PIN)
adc_tds = _adc(TDS_PIN)

# -------- DS18B20 --------
ow_s = onewire.OneWire(Pin(DS_S_PIN))
ds_s = ds18x20.DS18X20(ow_s)
roms_s = ds_s.scan()
ow_d = onewire.OneWire(Pin(DS_D_PIN))
ds_d = ds18x20.DS18X20(ow_d)
roms_d = ds_d.scan()

# -------- Utils --------
def check_power_stability():
    """檢查電源穩定性"""
    try:
        test_adc = ADC(Pin(36))
        test_adc.atten(ADC.ATTN_11DB)
        test_reading = test_adc.read()
        if test_reading is None or test_reading < 0:
            return False
        readings = []
        for _ in range(5):
            readings.append(test_adc.read())
            time.sleep_ms(10)
        if max(readings) - min(readings) > 100:
            return False
        return True
    except:
        return False

def safe_print(*a, **kw):
    try:
        output = ' '.join(str(arg) for arg in a)
        output = ''.join(ch for ch in output if ord(ch) < 128)
        print(output)
    except Exception:
        pass

def read_avg(adc, n=12, delay_ms=3):
    s = 0
    valid = 0
    for _ in range(n):
        try:
            reading = adc.read()
            if reading is not None and reading >= 0:
                s += reading
                valid += 1
            time.sleep_ms(delay_ms)
        except:
            continue
    return s // max(valid, 1) if valid > 0 else 0

def get_date_iso():
    ts = time.time() + TIMEZONE_OFFSET
    y, m, d, hh, mm, ss, _, _ = time.localtime(ts)
    return "%04d-%02d-%02dT%02d:%02d:%02d" % (y, m, d, hh, mm, ss)

def load_cal():
    try:
        with open(CAL_FILE) as f:
            return json.load(f)
    except:
        return {}

def save_cal(d):
    with open(CAL_FILE, "w") as f:
        json.dump(d, f)

# -------- pH 校正參數 --------
PH_CAL_VOLTAGES = {
    "ph7": 1.584,      # pH 7.0 對應的電壓
    "ph4": 2.110,    # pH 4.01 對應的電壓
    "ph10": 1.121    # pH 10.01 對應的電壓
}

# 根據 PH_CAL_VOLTAGES 動態計算校正參數
def _calculate_ph_cal_params(voltages_dict):
    """從電壓字典計算斜率和截距的輔助函數"""
    ph_values = [4.01, 7.0, 10.01]
    try:
        voltages = [voltages_dict["ph4"], voltages_dict["ph7"], voltages_dict["ph10"]]
    except KeyError:
        return -5.660064, 16.085410

    n = len(ph_values)
    sum_v = sum(voltages)
    sum_ph = sum(ph_values)
    sum_v2 = sum(v**2 for v in voltages)
    sum_vph = sum(v * ph for v, ph in zip(voltages, ph_values))
    denominator = (n * sum_v2 - sum_v**2)
    if abs(denominator) < 1e-9:
        return -5.660064, 16.085410
    m = (n * sum_vph - sum_v * sum_ph) / denominator
    b = (sum_ph - m * sum_v) / n
    return m, b

PH_CAL_M, PH_CAL_B = _calculate_ph_cal_params(PH_CAL_VOLTAGES)

# -------- 溫度校正參數 --------
# 溫度感測器校正參數（以temp_deep為基準）
TEMP_SHALLOW_OFFSET = 0.560  # 淺層溫度感測器偏移量
TEMP_SHALLOW_SCALE = 1.0     # 淺層溫度感測器比例係數

# -------- pH --------
def _k_at_T(k25, temp_c):
    """溫度補償係數計算"""
    T = (temp_c if temp_c is not None else 25.0) + 273.15
    return k25 * (298.15 / T)

def ph_read_voltage():
    raw = read_avg(adc_ph)
    v = raw / 4095 * 3.3
    return raw, v

def ph_value(temp_c):
    raw, v = ph_read_voltage()
    safe_print(f"PH Debug: raw={raw}, v={v:.3f}, temp={temp_c}")
    if PH_CAL_M is not None and PH_CAL_B is not None:
        ph = PH_CAL_M * v + PH_CAL_B
        safe_print(f"Code cal: m={PH_CAL_M}, b={PH_CAL_B}, ph={ph:.3f}")
    else:
        d = load_cal()
        m = d.get("ph_m")
        b = d.get("ph_b")
        if isinstance(m, (int, float)) and isinstance(b, (int, float)):
            ph = m * v + b
            safe_print(f"File cal: m={m}, b={b}, ph={ph:.3f}")
        else:
            V7 = d.get("ph_V7", 0.500)
            k25 = d.get("ph_k25", DEFAULT_PH_K_25C)
            kT = max(_k_at_T(k25, temp_c), 1e-6)
            ph = 14.0 - (v / 3.3) * 14.0
            safe_print(f"Default cal: V7={V7}, k25={k25}, kT={kT:.6f}, ph={ph:.3f}")
    if not isinstance(ph, (int, float)) or ph != ph:
        safe_print("Invalid pH, setting to 7.0")
        ph = 7.0
    ph = max(PH_MIN, min(PH_MAX, ph))
    safe_print(f"Final pH: {ph:.2f}")
    return round(ph, 2), raw, round(v, 3)

def ph_cal_three_points(ph4, ph7, ph10, temp_c=25.0):
    """三點pH校準：使用pH 4、7、10標準緩衝液"""
    safe_print("=== 三點pH校準開始 ===")
    safe_print("請依序將感測器放入pH 4、7、10標準緩衝液中")
    voltages = []
    ph_values = [ph4, ph7, ph10]
    for ph_val in ph_values:
        safe_print(f"請將感測器放入pH {ph_val}緩衝液中，按Enter繼續...")
        # 注意：MicroPython 上沒有接鍵盤時，請不要呼叫 input()
        # 若要用 REPL 操作，可手動呼叫下一段測量程式。
        try:
            input()
        except:
            pass
        readings = []
        for _ in range(10):
            _, v = ph_read_voltage()
            readings.append(v)
            time.sleep(0.5)
        avg_voltage = sum(readings) / len(readings)
        voltages.append(avg_voltage)
        safe_print(f"pH {ph_val}: 電壓 = {avg_voltage:.3f}V")

    n = len(ph_values)
    sum_v = sum(voltages)
    sum_ph = sum(ph_values)
    sum_v2 = sum(v**2 for v in voltages)
    sum_vph = sum(v * ph for v, ph in zip(voltages, ph_values))
    m = (n * sum_vph - sum_v * sum_ph) / (n * sum_v2 - sum_v**2)
    b = (sum_ph - m * sum_v) / n

    d = load_cal()
    d["ph_m"] = m
    d["ph_b"] = b
    d["ph_cal_points"] = {
        "ph4": {"ph": ph4, "voltage": voltages[0]},
        "ph7": {"ph": ph7, "voltage": voltages[1]},
        "ph10": {"ph": ph10, "voltage": voltages[2]},
    }
    d["ph_cal_temp"] = temp_c
    save_cal(d)

    safe_print("校準完成！")
    safe_print(f"斜率 m = {m:.6f}")
    safe_print(f"截距 b = {b:.6f}")
    safe_print(f"校正公式: pH = {m:.6f} * V + {b:.6f}")

    safe_print("\n=== 校準驗證 ===")
    for ph_val, v in zip(ph_values, voltages):
        calculated_ph = m * v + b
        error = abs(calculated_ph - ph_val)
        safe_print(f"pH {ph_val}: 實際={ph_val}, 計算={calculated_ph:.2f}, 誤差={error:.2f}")
    return m, b

def ph_cal_three_points_auto(ph4_voltage, ph7_voltage, ph10_voltage, temp_c=25.0):
    """自動三點pH校準：直接提供三個電壓值"""
    safe_print("=== 自動三點pH校準 ===")
    ph_values = [4.0, 7.0, 10.0]
    voltages = [ph4_voltage, ph7_voltage, ph10_voltage]
    for label, v in zip(("4.0", "7.0", "10.0"), voltages):
        safe_print(f"pH {label}: 電壓 = {v:.3f}V")

    n = len(ph_values)
    sum_v = sum(voltages)
    sum_ph = sum(ph_values)
    sum_v2 = sum(v**2 for v in voltages)
    sum_vph = sum(v * ph for v, ph in zip(voltages, ph_values))
    m = (n * sum_vph - sum_v * sum_ph) / (n * sum_v2 - sum_v**2)
    b = (sum_ph - m * sum_v) / n

    d = load_cal()
    d["ph_m"] = m
    d["ph_b"] = b
    d["ph_cal_points"] = {
        "ph4": {"ph": 4.0, "voltage": ph4_voltage},
        "ph7": {"ph": 7.0, "voltage": ph7_voltage},
        "ph10": {"ph": 10.0, "voltage": ph10_voltage},
    }
    d["ph_cal_temp"] = temp_c
    save_cal(d)

    safe_print("校準完成！")
    safe_print(f"斜率 m = {m:.6f}")
    safe_print(f"截距 b = {b:.6f}")
    safe_print(f"校正公式: pH = {m:.6f} * V + {b:.6f}")

    safe_print("\n=== 校準驗證 ===")
    for ph_val, v in zip(ph_values, voltages):
        calculated_ph = m * v + b
        error = abs(calculated_ph - ph_val)
        safe_print(f"pH {ph_val}: 實際={ph_val}, 計算={calculated_ph:.2f}, 誤差={error:.2f}")
    return m, b

def ph_cal_from_config():
    """使用配置的電壓值進行三點校正"""
    safe_print("=== 使用配置電壓進行三點校正 ===")
    ph4_voltage = PH_CAL_VOLTAGES["ph4"]
    ph7_voltage = PH_CAL_VOLTAGES["ph7"]
    ph10_voltage = PH_CAL_VOLTAGES["ph10"]

    safe_print("使用配置的校正電壓值：")
    safe_print(f"pH 4.01: {ph4_voltage}V")
    safe_print(f"pH 7.0: {ph7_voltage}V")
    safe_print(f"pH 10.01: {ph10_voltage}V")

    ph_values = [4.01, 7.0, 10.01]
    voltages = [ph4_voltage, ph7_voltage, ph10_voltage]

    n = len(ph_values)
    sum_v = sum(voltages)
    sum_ph = sum(ph_values)
    sum_v2 = sum(v**2 for v in voltages)
    sum_vph = sum(v * ph for v, ph in zip(voltages, ph_values))
    m = (n * sum_vph - sum_v * sum_ph) / (n * sum_v2 - sum_v**2)
    b = (sum_ph - m * sum_v) / n

    d = load_cal()
    d["ph_m"] = m
    d["ph_b"] = b
    d["ph_cal_points"] = {
        "ph4": {"ph": 4.01, "voltage": ph4_voltage},
        "ph7": {"ph": 7.0, "voltage": ph7_voltage},
        "ph10": {"ph": 10.01, "voltage": ph10_voltage},
    }
    d["ph_cal_temp"] = 25.0
    save_cal(d)

    safe_print("校準完成！")
    safe_print(f"斜率 m = {m:.6f}")
    safe_print(f"截距 b = {b:.6f}")
    safe_print(f"校正公式: pH = {m:.6f} * V + {b:.6f}")

    safe_print("\n=== 校準驗證 ===")
    for ph_val, v in zip(ph_values, voltages):
        calculated_ph = m * v + b
        error = abs(calculated_ph - ph_val)
        safe_print(f"pH {ph_val}: 實際={ph_val}, 計算={calculated_ph:.2f}, 誤差={error:.2f}")
    return m, b

def calculate_ph_calibration_params():
    """計算校正參數（用於修改電壓值後重新計算）"""
    ph_values = [4.01, 7.0, 10.01]
    voltages = [PH_CAL_VOLTAGES["ph4"], PH_CAL_VOLTAGES["ph7"], PH_CAL_VOLTAGES["ph10"]]

    n = len(ph_values)
    sum_v = sum(voltages)
    sum_ph = sum(ph_values)
    sum_v2 = sum(v**2 for v in voltages)
    sum_vph = sum(v * ph for v, ph in zip(voltages, ph_values))
    m = (n * sum_vph - sum_v * sum_ph) / (n * sum_v2 - sum_v**2)
    b = (sum_ph - m * sum_v) / n

    safe_print("=== 校正參數計算結果 ===")
    safe_print("電壓值：")
    safe_print(f"  pH 4.01: {voltages[0]}V")
    safe_print(f"  pH 7.0: {voltages[1]}V")
    safe_print(f"  pH 10.01: {voltages[2]}V")
    safe_print("")
    safe_print("計算結果：")
    safe_print(f"PH_CAL_M = {m:.6f}  # 斜率")
    safe_print(f"PH_CAL_B = {b:.6f}  # 截距")
    safe_print(f"校正公式: pH = {m:.6f} * V + {b:.6f}")

    safe_print("\n驗證結果：")
    for ph_val, v in zip(ph_values, voltages):
        calculated_ph = m * v + b
        error = abs(calculated_ph - ph_val)
        safe_print(f"pH {ph_val}: 實際={ph_val}, 計算={calculated_ph:.2f}, 誤差={error:.2f}")
    return m, b

def check_ph_calibration():
    """檢查pH校正狀態"""
    safe_print("=== pH校正狀態檢查 ===")
    safe_print("程式碼中的校正參數：")
    safe_print(f"  PH_CAL_M = {PH_CAL_M}")
    safe_print(f"  PH_CAL_B = {PH_CAL_B}")
    safe_print(f"  校正公式: pH = {PH_CAL_M} * V + {PH_CAL_B}")
    safe_print("\n校正電壓值：")
    safe_print(f"  pH 4.01: {PH_CAL_VOLTAGES['ph4']}V")
    safe_print(f"  pH 7.0: {PH_CAL_VOLTAGES['ph7']}V")
    safe_print(f"  pH 10.01: {PH_CAL_VOLTAGES['ph10']}V")
    return True

def calculate_temp_calibration():
    """計算溫度校正參數"""
    safe_print("=== 溫度校正參數計算 ===")
    safe_print("請將兩個溫度感測器放在同一環境中，等待讀數穩定...")
    shallow_readings = []
    deep_readings = []
    for i in range(10):
        shallow_temp = ds_read(ds_s, roms_s)
        deep_temp = ds_read(ds_d, roms_d)
        if shallow_temp != -127.0 and deep_temp != -127.0:
            shallow_readings.append(shallow_temp)
            deep_readings.append(deep_temp)
        time.sleep(1)
        safe_print(f"讀取 {i+1}/10: 淺層={shallow_temp}C, 深層={deep_temp}C")
    if len(shallow_readings) < 5:
        safe_print("讀取次數不足，無法計算校正參數")
        return None, None
    avg_shallow = sum(shallow_readings) / len(shallow_readings)
    avg_deep = sum(deep_readings) / len(deep_readings)
    safe_print("\n平均溫度：")
    safe_print(f"  淺層感測器: {avg_shallow:.2f}C")
    safe_print(f"  深層感測器: {avg_deep:.2f}C")
    safe_print(f"  誤差: {abs(avg_shallow - avg_deep):.2f}C")
    offset = avg_deep - avg_shallow
    scale = 1.0
    safe_print("\n計算結果：")
    safe_print(f"  TEMP_SHALLOW_OFFSET = {offset:.3f}")
    safe_print(f"  TEMP_SHALLOW_SCALE = {scale:.3f}")
    safe_print(f"  校正公式: corrected_temp = (raw_temp * {scale}) + {offset:.3f}")
    corrected_shallow = (avg_shallow * scale) + offset
    error = abs(corrected_shallow - avg_deep)
    safe_print("\n驗證結果：")
    safe_print(f"  校正前淺層: {avg_shallow:.2f}C")
    safe_print(f"  校正後淺層: {corrected_shallow:.2f}C")
    safe_print(f"  深層基準: {avg_deep:.2f}C")
    safe_print(f"  校正誤差: {error:.2f}C")
    return offset, scale

def check_temp_calibration():
    """檢查溫度校正狀態"""
    safe_print("=== 溫度校正狀態檢查 ===")
    safe_print("校正參數：")
    safe_print(f"  TEMP_SHALLOW_OFFSET = {TEMP_SHALLOW_OFFSET}")
    safe_print(f"  TEMP_SHALLOW_SCALE = {TEMP_SHALLOW_SCALE}")
    safe_print(f"  校正公式: corrected_temp = (raw_temp * {TEMP_SHALLOW_SCALE}) + {TEMP_SHALLOW_OFFSET}")
    shallow_temp = ds_read(ds_s, roms_s)
    deep_temp = ds_read(ds_d, roms_d)
    corrected_shallow = ds_read_corrected(ds_s, roms_s, is_shallow=True)
    safe_print("\n當前讀數：")
    safe_print(f"  淺層原始: {shallow_temp}C")
    safe_print(f"  淺層校正: {corrected_shallow}C")
    safe_print(f"  深層基準: {deep_temp}C")
    if shallow_temp != -127.0 and deep_temp != -127.0:
        error = abs(corrected_shallow - deep_temp)
        safe_print(f"  校正誤差: {error:.2f}C")
    return True

# -------- MQ135/137 --------
def mq_air_calibrate(duration_s=30):
    t0 = time.time()
    s135, s137 = [], []
    while time.time() - t0 < duration_s:
        s135.append(read_avg(adc135, n=8))
        s137.append(read_avg(adc137, n=8))
    r0_135 = sum(s135) // len(s135)
    r0_137 = sum(s137) // len(s137)
    d = load_cal()
    d["mq135_r0"] = r0_135
    d["mq137_r0"] = r0_137
    save_cal(d)
    return r0_135, r0_137

def mq_read():
    raw135 = read_avg(adc135)
    raw137 = read_avg(adc137)
    d = load_cal()
    r0_135 = d.get("mq135_r0")
    r0_137 = d.get("mq137_r0")
    ratio135 = (raw135 / max(r0_135, 1)) if r0_135 else None
    ratio137 = (raw137 / max(r0_137, 1)) if r0_137 else None
    return {"raw135": raw135, "raw137": raw137, "ratio135": ratio135, "ratio137": ratio137}

# -------- 濁度 --------
def turbidity_read():
    raw = read_avg(adc_turb)
    if raw < TURBIDITY_AIR_THRESHOLD:
        return None, raw, 0.0
    v = raw / 4095 * 3.3
    return round(v, 3), raw, v

# -------- TDS --------
def tds_read(temp_c):
    tds_raw = read_avg(adc_tds)
    tds_v = tds_raw / 4095 * TDS_VREF
    temp_comp_coeff = 1.0 + TDS_TEMP_COMPENSATION_FACTOR * (temp_c - 25.0)
    temp_comp_v = tds_v / temp_comp_coeff
    tds_ppm = (133.42 * temp_comp_v**3 - 258.7 * temp_comp_v**2 + 857.39 * temp_comp_v) * TDS_K_FACTOR
    return round(tds_ppm, 2), tds_raw, round(tds_v, 3)

# -------- DS18B20 --------
def ds_read(ds, roms):
    try:
        ds.convert_temp()
        time.sleep_ms(750)
        if roms:
            t = ds.read_temp(roms[0])
            return round(t, 2) if t is not None else -127.0
        return -127.0
    except:
        return -127.0

def ds_read_corrected(ds, roms, is_shallow=False):
    """讀取溫度並應用校正（僅對淺層感測器）"""
    temp = ds_read(ds, roms)
    if temp == -127.0:
        return temp
    if is_shallow:
        corrected = (temp * TEMP_SHALLOW_SCALE) + TEMP_SHALLOW_OFFSET
        safe_print(f"Temp correction: raw={temp}, scale={TEMP_SHALLOW_SCALE}, offset={TEMP_SHALLOW_OFFSET}, corrected={corrected:.2f}")
        return round(corrected, 2)
    return temp

# -------- HTTP Date 解析 --------
_MONTH = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,"Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}

def _http_head_date(host):
    try:
        url = "http://" + host
        # 有些 urequests 沒有 head()，但 request("HEAD", ...) 可行
        try:
            r = urequests.request("HEAD", url)
        except:
            r = urequests.get(url)
        try:
            if hasattr(r, "headers") and "Date" in r.headers:
                return r.headers["Date"]
            return None
        finally:
            try:
                r.close()
            except:
                pass
    except Exception as e:
        safe_print("[HTTP-TIME] error:", e)
    return None

# -------- 時間同步 --------
def sync_time():
    # 優先 NTP
    try:
        ntptime.host = "192.168.100.1"
        ntptime.settime()
        y, mo, d, hh, mm, ss, _, _ = time.gmtime()
        safe_print("[NTP] synced:", "%04d-%02d-%02dT%02d:%02d:%02dZ" % (y, mo, d, hh, mm, ss))
        return True
    except Exception as e:
        safe_print("[NTP] failed:", e)
        for h in ("connectivitycheck.gstatic.com","example.com","google.com","cloudflare.com"):
            ds = _http_head_date(h)
            if not ds:
                continue
            try:
                # 'Wed, 11 Sep 2025 09:04:55 GMT'
                p = ds.split()
                day = int(p[1]); mon = _MONTH[p[2]]; year = int(p[3])
                hh, mm, ss = map(int, p[4].split(":"))
                epoch = time.mktime((year, mon, day, hh, mm, ss, 0, 0))
                y, mo, d, hh, mm, ss, wd, yd = time.gmtime(epoch)
                machine.RTC().datetime((y, mo, d, wd, hh, mm, ss, 0))
                safe_print("[HTTP-TIME] synced via", h, "%04d-%02d-%02dT%02d:%02d:%02dZ" % (y, mo, d, hh, mm, ss))
                return True
            except Exception as e2:
                safe_print("[HTTP-TIME] parse failed:", e2)
        safe_print("[TIME] sync failed")
        return False

# -------- Main --------
HTTP_HEADERS = {
    "Content-Type": "application/json",
    "Connection": "close",
    "Authorization": "Bearer replace_with_local_secret",
}

def connect_wifi_with_credentials(ssid, password, max_attempts=1):
    """Try to connect to WiFi with given credentials"""
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        if USE_STATIC_IP:
            wlan.ifconfig(STATIC_IFCFG)
        try:
            wlan.disconnect()
        except:
            pass
        time.sleep(0.5)
        safe_print(f"Connecting to {ssid}...")
        wlan.connect(ssid, password)
        t0 = time.ticks_ms()
        while not wlan.isconnected() and time.ticks_diff(time.ticks_ms(), t0) < 15000:
            safe_print(".", end="")
            time.sleep(0.5)
        if wlan.isconnected():
            safe_print("\nWiFi connected to", ssid, wlan.ifconfig())
            return True
        safe_print("\nFailed to connect to", ssid)
        return False
    except Exception as e:
        safe_print("\nConnection error:", e)
        return False

def connect_wifi():
    """Try to connect to WiFi with alternating primary/backup retry"""
    wifi_failures = 0
    connection_attempts = 0
    use_primary = True
    while True:
        connection_attempts += 1
        if connection_attempts > MAX_CONNECTION_ATTEMPTS:
            safe_print("Too many connection attempts, performing soft reset...")
            set_led_color(10, 10, 0)
            time.sleep(2)
            machine.reset()
        if use_primary:
            safe_print(f"Attempting primary WiFi ({connection_attempts})...")
            if connect_wifi_with_credentials(SSID_PRIMARY, PASSWORD_PRIMARY):
                wifi_failures = 0
                return True
            safe_print("Primary WiFi failed")
        else:
            safe_print(f"Attempting backup WiFi ({connection_attempts})...")
            if connect_wifi_with_credentials(SSID_BACKUP, PASSWORD_BACKUP):
                wifi_failures = 0
                return True
            safe_print("Backup WiFi failed")
        wifi_failures += 1
        use_primary = not use_primary
        safe_print(f"WiFi failed (failures: {wifi_failures}), retrying in 3 seconds...")
        set_led_color(10, 0, 0)
        time.sleep(3)

def main():
    # 啟動ESP32
    safe_print("ESP32 Starting...")
    time.sleep(2)
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    set_led_color(0, 0, 0)
    last_transmission = 0
    last_successful_transmission = time.ticks_ms()

    # Initial WiFi connection
    safe_print("Initializing WiFi connection...")
    connect_wifi()
    set_led_color(0, 10, 0)
    sync_time()

    while True:
        # 看門狗：5 分鐘無成功傳輸則重開
        now = time.ticks_ms()
        if time.ticks_diff(now, last_successful_transmission) > 5 * 60 * 1000:
            safe_print("Watchdog triggered - no successful transmission for 5 minutes, resetting...")
            set_led_color(10, 10, 10)
            time.sleep(2)
            machine.reset()

        wlan = network.WLAN(network.STA_IF)
        if not wlan.isconnected():
            safe_print("\nWi-Fi disconnected. Attempting reconnect...")
            set_led_color(0, 0, 10)
            connect_wifi()
            set_led_color(0, 10, 0)
            sync_time()

        # 是否到採樣/傳送時間
        if time.ticks_diff(now, last_transmission) < DATA_INTERVAL * 1000:
            time.sleep_ms(50)
            continue
        last_transmission = now

        t_shallow = ds_read_corrected(ds_s, roms_s, is_shallow=True)
        t_deep = ds_read_corrected(ds_d, roms_d, is_shallow=False)
        temp_for_ph_tds = t_shallow if t_shallow != -127.0 else (t_deep if t_deep != -127.0 else 25.0)

        date_iso = get_date_iso()
        ph, ph_raw, ph_v = ph_value(temp_for_ph_tds)
        tu_v, tu_raw, _ = turbidity_read()
        mq = mq_read()
        tds_ppm, tds_raw, tds_v = tds_read(temp_for_ph_tds)

        payload = {
            "sensorId": "S1",
            "date": date_iso,
            "ph": ph,
            "turbidity": tu_raw,
            "hardness": tds_ppm,
            "mq135": mq["raw135"],
            "mq137": mq["raw137"],
            "temp_deep": t_deep,
            "temp_shallow": t_shallow,
            "RGB": [0, 0, 0],
            "msg": (
                f"pH(raw={ph_raw},V={ph_v},T={temp_for_ph_tds});"
                f"TU(raw={tu_raw});"
                f"TDS(ppm={tds_ppm},raw={tds_raw},V={tds_v});"
                f"MQ(r135={mq['raw135']},r137={mq['raw137']});"
                f"DS(S={t_shallow},D={t_deep})"
            ),
        }

        safe_print("SEND:", payload)
        set_led_color(0, 0, 10)

        success = False
        retry_count = 0
        max_retries = 6
        max_retry_interval = 3
        last_error = ""

        while not success and retry_count < max_retries:
            try:
                try:
                    r = urequests.post(API_URL, json=payload, headers=HTTP_HEADERS, timeout=15)
                except TypeError:
                    # 某些 urequests 版本沒有 timeout 參數
                    r = urequests.post(API_URL, json=payload, headers=HTTP_HEADERS)
                status_code = r.status_code
                safe_print("HTTP code:", status_code)
                r.close()
                if status_code == 200:
                    safe_print("Data sent successfully!")
                    set_led_color(0, 10, 0)
                    success = True
                    last_successful_transmission = time.ticks_ms()
                else:
                    retry_count += 1
                    last_error = f"HTTP {status_code}"
                    safe_print(f"HTTP error {status_code}, retrying... ({retry_count}/{max_retries})")
                    set_led_color(10, 0, 0)
            except Exception as e:
                retry_count += 1
                last_error = str(e)
                safe_print(f"POST error (attempt {retry_count}/{max_retries}): {last_error}")
                set_led_color(10, 0, 0)

            # 到下一輪採樣了就跳出重試
            now = time.ticks_ms()
            if time.ticks_diff(now, last_transmission) >= DATA_INTERVAL * 1000:
                safe_print("Skipping retry - time for next data collection")
                break

            if not success and retry_count < max_retries:
                if ("-202" in last_error) or ("SSL" in last_error) or ("TLS" in last_error) or ("MBEDTLS" in last_error):
                    retry_delay = min(retry_count * 2, 6)
                    safe_print(f"SSL error detected, retrying in {retry_delay} seconds...")
                else:
                    retry_delay = min(retry_count, max_retry_interval)
                    safe_print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            elif retry_count >= max_retries:
                safe_print(f"Max retries ({max_retries}) reached, giving up for this cycle")
                break

            time.sleep_ms(100)
            set_led_color(0, 0, 0)

# ---- REPL 校正便捷 ----
# pH校正：
#   from main import check_ph_calibration; check_ph_calibration()
#   from main import calculate_ph_calibration_params; calculate_ph_calibration_params()
# 溫度校正：
#   from main import check_temp_calibration; check_temp_calibration()
#   from main import calculate_temp_calibration; calculate_temp_calibration()
# 其他校正：
#   from main import ph_cal_from_config; ph_cal_from_config()
#   from main import mq_air_calibrate; mq_air_calibrate(30)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import sys, io
        buf = io.StringIO()
        sys.print_exception(e, buf)
        msg_err = buf.getvalue()

        safe_print("--- CRASH DETECTED ---")
        safe_print(msg_err)

        try:
            wlan = network.WLAN(network.STA_IF)
            if not wlan.isconnected():
                safe_print("Crash Handler: WiFi disconnected, attempting reconnect...")
                connect_wifi()

            if wlan.isconnected():
                safe_print("Crash Handler: WiFi connected, sending report.")
                # Re-use date function if time is synced
                try:
                    date_iso = get_date_iso()
                except Exception:
                    date_iso = "unknown"

                error_payload = {
                    "sensorId": "S1",
                    "date": date_iso,
                    "msg_err": msg_err
                }
                try:
                    # Use a shorter timeout for crash reporting
                    r = urequests.post(API_URL, json=error_payload, headers=HTTP_HEADERS, timeout=5)
                    r.close()
                    safe_print("Crash Handler: Report sent.")
                except Exception as post_e:
                    safe_print(f"Crash Handler: Failed to send report: {post_e}")
            else:
                safe_print("Crash Handler: Could not connect to WiFi, unable to send report.")

        except Exception as report_e:
            safe_print(f"Crash Handler: Error during reporting: {report_e}")

        safe_print("Crash Handler: Rebooting in 5 seconds...")
        time.sleep(5)
        machine.reset()
