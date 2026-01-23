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

API_URL = "https://predict.du1217.club/api/include"
USE_STATIC_IP = False
# STATIC_IFCFG = ("192.168.1.123", "255.255.255.0", "192.168.1.1", "8.8.8.8")

# Data transmission interval (seconds)
DATA_INTERVAL = 30

# Auto reset settings
MAX_WIFI_FAILURES = 5  # 最大 WiFi 失敗次數
MAX_CONNECTION_ATTEMPTS = 10  # 最大連接嘗試次數
RESET_AFTER_FAILURES = 3  # 失敗多少次後軟重置

CAL_FILE = "cal.json"
PH_MAX = 14.0
PH_MIN = 0.0
DEFAULT_PH_K_25C = 0.18  # 恢復原始係數

TIMEZONE_OFFSET = 8 * 3600

# -------- Pins --------
PH_PIN = 4
TURB_PIN = 7
MQ135_PIN = 5
MQ137_PIN = 6
DS_S_PIN, DS_D_PIN = 16, 17
TDS_PIN = 15
TURBIDITY_AIR_THRESHOLD = 120

# -------- TDS --------
TDS_VREF = 3.3
TDS_TEMP_COMPENSATION_FACTOR = 0.5
TDS_K_FACTOR = 0.5

# -------- LED --------
LED_PIN = 48
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
def safe_print(*a, **kw):
    try:
        print(*a, **kw)
    except Exception:
        pass


def read_avg(adc, n=12, delay_ms=3):
    s = 0
    for _ in range(n):
        s += adc.read()
        time.sleep_ms(delay_ms)
    return s // n


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


# -------- pH --------
# pH 平滑處理變數
_last_ph_values = []
PH_SMOOTHING_WINDOW = 5  # 增加平滑窗口大小

def _smooth_ph_value(ph):
    """使用移動平均來平滑 pH 值"""
    global _last_ph_values
    _last_ph_values.append(ph)
    
    # 保持窗口大小
    if len(_last_ph_values) > PH_SMOOTHING_WINDOW:
        _last_ph_values.pop(0)
    
    # 計算移動平均
    if len(_last_ph_values) >= 2:
        return sum(_last_ph_values) / len(_last_ph_values)
    else:
        return ph

def _k_at_T(k25, temp_c):
    """溫度補償係數計算"""
    T = (temp_c if temp_c is not None else 25.0) + 273.15
    return k25 * (T / 298.15)


def ph_read_voltage():
    raw = read_avg(adc_ph)
    v = raw / 4095 * 3.3
    return raw, v


def ph_value(temp_c):
    d = load_cal()
    raw, v = ph_read_voltage()
    m = d.get("ph_m")
    b = d.get("ph_b")
    
    if isinstance(m, (int, float)) and isinstance(b, (int, float)):
        # 使用線性校準公式
        ph = m * v + b
    else:
        # 使用簡化的 pH 計算
        V7 = d.get("ph_V7", 2.500)  # pH 7 時的電壓
        k25 = d.get("ph_k25", DEFAULT_PH_K_25C)
        kT = max(_k_at_T(k25, temp_c), 1e-6)
        ph = 7.0 - (v - V7) / kT
        
        # 添加更強的平滑處理
        smoothing_factor = 0.5  # 降低平滑因子，減少變化幅度
        ph = 7.0 + (ph - 7.0) * smoothing_factor
    
    # 檢查結果有效性
    if not isinstance(ph, (int, float)) or ph != ph:
        ph = 7.0
    
    # 限制 pH 範圍
    ph = max(PH_MIN, min(PH_MAX, ph))
    
    # 應用平滑處理
    ph_smoothed = _smooth_ph_value(ph)
    
    return round(ph_smoothed, 2), raw, round(v, 3)


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
    return {
        "raw135": raw135,
        "raw137": raw137,
        "ratio135": ratio135,
        "ratio137": ratio137,
    }


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
    tds_ppm = (
        133.42 * temp_comp_v**3 - 258.7 * temp_comp_v**2 + 857.39 * temp_comp_v
    ) * TDS_K_FACTOR
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


# -------- Wi-Fi --------
def connect_wifi_with_credentials(ssid, password, max_attempts=1):
    """Try to connect to WiFi with given credentials (single attempt for alternating)"""
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        if USE_STATIC_IP:
            wlan.ifconfig(STATIC_IFCFG)
        wlan.disconnect()
        time.sleep(0.5)
        
        print(f"Connecting to {ssid}...")
        wlan.connect(ssid, password)
        
        # 連接等待時間
        t0 = time.ticks_ms()
        while not wlan.isconnected() and time.ticks_diff(time.ticks_ms(), t0) < 15000:
            print(".", end="")
            time.sleep(0.5)
            
        if wlan.isconnected():
            print(f"\nWiFi connected to {ssid}:", wlan.ifconfig())
            return True
        else:
            print(f"\nFailed to connect to {ssid}")
            return False
            
    except Exception as e:
        print(f"\nConnection error: {e}")
        return False

def connect_wifi():
    """Try to connect to WiFi with alternating primary/backup retry"""
    wifi_failures = 0
    connection_attempts = 0
    use_primary = True  # 輪流標記
    
    while True:
        connection_attempts += 1
        
        # 如果嘗試次數過多，軟重置系統
        if connection_attempts > MAX_CONNECTION_ATTEMPTS:
            print("Too many connection attempts, performing soft reset...")
            set_led_color(10, 10, 0)  # 黃色表示即將重置
            time.sleep(2)
            machine.reset()
        
        # 輪流嘗試主要和備用 WiFi
        if use_primary:
            print(f"Attempting primary WiFi ({connection_attempts})...")
            if connect_wifi_with_credentials(SSID_PRIMARY, PASSWORD_PRIMARY):
                wifi_failures = 0  # 重置失敗計數
                return True
            print("Primary WiFi failed")
        else:
            print(f"Attempting backup WiFi ({connection_attempts})...")
            if connect_wifi_with_credentials(SSID_BACKUP, PASSWORD_BACKUP):
                wifi_failures = 0  # 重置失敗計數
                return True
            print("Backup WiFi failed")
        
        wifi_failures += 1
        use_primary = not use_primary  # 切換到另一個 WiFi
        
        # 如果 WiFi 失敗次數過多，軟重置
        if wifi_failures >= RESET_AFTER_FAILURES:
            print(f"WiFi failed {wifi_failures} times, performing soft reset...")
            set_led_color(10, 0, 10)  # 紫色表示 WiFi 重置
            time.sleep(2)
            machine.reset()
        
        # 等待後繼續輪流重試
        print(f"WiFi failed (failures: {wifi_failures}), retrying in 3 seconds...")
        set_led_color(10, 0, 0)  # 紅色表示失敗
        time.sleep(3)


# -------- SSL 配置 --------
# MicroPython 的 SSL 配置較為簡單，直接使用預設設定

# -------- HTTP Date 解析 --------
_MONTH = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


def _http_head_date(host):
    try:
        url = "http://" + host
        r = urequests.head(url)
        if "Date" in r.headers:
            return r.headers["Date"]
        r.close()
    except Exception as e:
        safe_print("[HTTP-TIME] error:", e)
    return None


# -------- 時間同步 --------
def sync_time():
    # 優先 NTP
    try:
        ntptime.host = "pool.ntp.org"
        ntptime.settime()
        y, mo, d, hh, mm, ss, _, _ = time.gmtime()
        safe_print(
            "[NTP] synced:", "%04d-%02d-%02dT%02d:%02d:%02dZ" % (y, mo, d, hh, mm, ss)
        )
        return True
    except Exception as e:
        safe_print("[NTP] failed:", e)

    # 備援 HTTP Date
    for h in (
        "connectivitycheck.gstatic.com",
        "example.com",
        "google.com",
        "cloudflare.com",
    ):
        ds = _http_head_date(h)
        if not ds:
            continue
        try:
            # 'Wed, 11 Sep 2025 09:04:55 GMT'
            p = ds.split()
            day = int(p[1])
            mon = _MONTH[p[2]]
            year = int(p[3])
            hh, mm, ss = map(int, p[4].split(":"))
            epoch = time.mktime((year, mon, day, hh, mm, ss, 0, 0))
            y, mo, d, hh, mm, ss, wd, yd = time.gmtime(epoch)
            machine.RTC().datetime((y, mo, d, wd, hh, mm, ss, 0))
            safe_print(
                "[HTTP-TIME] synced via",
                h,
                "%04d-%02d-%02dT%02d:%02d:%02dZ" % (y, mo, d, hh, mm, ss),
            )
            return True
        except Exception as e:
            safe_print("[HTTP-TIME] parse failed:", e)

    safe_print("[TIME] sync failed")
    return False


# -------- Main --------
HTTP_HEADERS = {
    "Content-Type": "application/json",
    "Connection": "close",
    "Authorization": "Bearer replace_with_local_secret",
}


def main():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    set_led_color(0, 0, 0)
    last_transmission = 0
    global_failures = 0  # 全局失敗計數
    last_successful_transmission = time.ticks_ms()  # 上次成功傳輸時間

    # Initial WiFi connection
    print("Initializing WiFi connection...")
    connect_wifi()
    set_led_color(0, 10, 0)
    sync_time()

    while True:
        # 看門狗檢查：如果超過5分鐘沒有成功傳輸，軟重置
        now = time.ticks_ms()
        if time.ticks_diff(now, last_successful_transmission) > 5 * 60 * 1000:  # 5分鐘
            print("Watchdog triggered - no successful transmission for 5 minutes, resetting...")
            set_led_color(10, 10, 10)  # 白色表示看門狗重置
            time.sleep(2)
            machine.reset()
        
        wlan = network.WLAN(network.STA_IF)
        if not wlan.isconnected():
            print("\nWi-Fi disconnected. Attempting reconnect...")
            set_led_color(0, 0, 10)
            global_failures += 1
            
            # 如果全局失敗次數過多，軟重置
            if global_failures > MAX_WIFI_FAILURES:
                print(f"Too many global failures ({global_failures}), resetting...")
                set_led_color(10, 5, 0)  # 橙色表示全局重置
                time.sleep(2)
                machine.reset()
            
            connect_wifi()  # This will retry infinitely
            set_led_color(0, 10, 0)
            sync_time()

        # Check if it's time to send data (30 seconds interval)
        if time.ticks_diff(now, last_transmission) < DATA_INTERVAL * 1000:
            time.sleep_ms(50)
            continue
        last_transmission = now

        t_shallow = ds_read(ds_s, roms_s)
        t_deep = ds_read(ds_d, roms_d)
        temp_for_ph_tds = (
            t_shallow if t_shallow != -127.0 else (t_deep if t_deep != -127.0 else 25.0)
        )

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
            "msg": f"pH(raw={ph_raw},V={ph_v},T={temp_for_ph_tds});TU(raw={tu_raw});"
            f"TDS(ppm={tds_ppm},raw={tds_raw},V={tds_v});"
            f"MQ(r135={mq['raw135']},r137={mq['raw137']});"
            f"DS(S={t_shallow},D={t_deep})",
        }

        print("SEND:", payload)
        set_led_color(0, 0, 10)
        
        # 不斷重試直到成功或下次資料採集時間
        success = False
        retry_count = 0
        max_retry_interval = 5  # 最大重試間隔秒數
        max_retries_before_wifi_reconnect = 3  # 最多重試3次後重新連接WiFi
        
        while not success:
            try:
                # 添加更長的超時時間，使用預設 SSL 設定
                r = urequests.post(API_URL, json=payload, headers=HTTP_HEADERS, timeout=30)
                status_code = r.status_code
                print("HTTP code:", status_code)
                r.close()
                
                if status_code == 200:
                    print("Data sent successfully!")
                    set_led_color(0, 10, 0)
                    success = True
                    global_failures = 0  # 重置全局失敗計數
                    last_successful_transmission = time.ticks_ms()  # 更新成功傳輸時間
                else:
                    print(f"HTTP error {status_code}, retrying...")
                    set_led_color(10, 0, 0)
                    
            except Exception as e:
                retry_count += 1
                error_msg = str(e)
                print(f"POST error (attempt {retry_count}): {error_msg}")
                set_led_color(10, 0, 0)
                
                # 檢查是否到了下次資料採集時間
                now = time.ticks_ms()
                if time.ticks_diff(now, last_transmission) >= DATA_INTERVAL * 1000:
                    print("Skipping retry - time for next data collection")
                    break
                
                # 如果重試次數過多，重新連接WiFi
                if retry_count >= max_retries_before_wifi_reconnect:
                    print("Too many failures, reconnecting WiFi...")
                    set_led_color(0, 0, 10)  # 藍色表示重新連接
                    wlan = network.WLAN(network.STA_IF)
                    wlan.disconnect()
                    time.sleep(2)
                    connect_wifi()
                    set_led_color(0, 10, 0)  # 綠色表示重新連接成功
                    retry_count = 0  # 重置重試計數
                    continue
                
                # 針對 SSL 錯誤增加更長的重試間隔
                if "-202" in error_msg or "SSL" in error_msg or "TLS" in error_msg or "MBEDTLS" in error_msg:
                    retry_delay = min(retry_count * 2, 8)  # SSL 錯誤需要更長等待時間
                    print(f"SSL error detected, retrying in {retry_delay} seconds...")
                else:
                    retry_delay = min(retry_count, max_retry_interval)
                    print(f"Retrying in {retry_delay} seconds...")
                
                time.sleep(retry_delay)
            
            # 短暫延遲後清除LED
            time.sleep_ms(100)
            set_led_color(0, 0, 0)


# ---- REPL 校正便捷 ----
# from main import ph_cal_single_point; ph_cal_single_point(7.0, 25.0)
# from main import ph_cal_two_points;  ph_cal_two_points(7.0, 10.0)
# from main import mq_air_calibrate;   mq_air_calibrate(30)

if __name__ == "__main__":
    main()
