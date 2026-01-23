import time
import machine
import network
import urequests

from methods.config import load_config, save_config
from methods.led import init_led, set_led_color
from methods.logger import Logger
from methods.time_sync import sync_time
from methods.utils import get_date_iso
from methods.wifi import connect_wifi, has_wifi_credentials, start_ap
from sensors.ds18b20 import ds_read, init_ds18b20
from sensors.mq import init_mq, mq_air_calibrate, mq_read
from sensors.ph import init_ph, ph_value
from sensors.tds import init_tds, tds_read
from sensors.turbidity import init_turbidity, turbidity_read
from web.admin_server import AdminServer


# 主程式入口
def main():
    cfg = load_config()
    adc_vref = cfg["adc"]["vref"]
    cal_file = cfg["calibration"]["file"]
    logger = Logger(cfg)
    logger.log("System boot")

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    init_led(cfg["led"]["pin"], cfg["led"]["num"])
    set_led_color(0, 0, 0)

    adc_ph = init_ph(cfg["ph"]["pin"])
    adc_turb = init_turbidity(cfg["turbidity"]["pin"])
    adc135, adc137 = init_mq(cfg["mq"]["pin_135"], cfg["mq"]["pin_137"])
    adc_tds = init_tds(cfg["tds"]["pin"])
    ds_s, roms_s = init_ds18b20(cfg["ds18b20"]["pin_shallow"])
    ds_d, roms_d = init_ds18b20(cfg["ds18b20"]["pin_deep"])

    status = {
        "boot_ms": time.ticks_ms(),
        "last_send_iso": "",
        "last_http_code": None,
        "last_error": "",
        "last_reading": {},
        "wifi_connected": False,
        "ip": "",
        "wifi_mode": "",
    }

    admin_server = None
    ap_iface = None
    if cfg.get("web", {}).get("enabled"):
        admin_server = AdminServer(cfg, status, save_config, logger=logger)

    last_transmission = 0
    global_failures = 0
    last_successful_transmission = time.ticks_ms()

    print("Initializing WiFi connection...")
    wifi_mode = connect_wifi(cfg, set_led_color, log_fn=logger.log)
    status["wifi_mode"] = wifi_mode
    if wifi_mode == "sta":
        set_led_color(0, 10, 0)
        sync_time(cfg)
        status["wifi_connected"] = wlan.isconnected()
        if status["wifi_connected"]:
            status["ip"] = wlan.ifconfig()[0]
        logger.log("WiFi mode: STA")
    else:
        set_led_color(10, 10, 0)
        ap_iface = network.WLAN(network.AP_IF)
        status["wifi_connected"] = False
        status["ip"] = ap_iface.ifconfig()[0]
        logger.log("WiFi mode: AP")

    while True:
        if admin_server:
            admin_server.poll()

        if wifi_mode == "sta" and not has_wifi_credentials(cfg):
            logger.log("No SSID detected, switching to AP")
            ap_iface = start_ap(cfg, log_fn=logger.log)
            wifi_mode = "ap"
            status["wifi_mode"] = wifi_mode
            status["wifi_connected"] = False
            status["ip"] = ap_iface.ifconfig()[0]

        now = time.ticks_ms()
        if (
            wifi_mode == "sta"
            and time.ticks_diff(now, last_successful_transmission)
            > cfg["watchdog"]["no_success_reset_ms"]
        ):
            print(
                "Watchdog triggered - no successful transmission for 5 minutes, resetting..."
            )
            set_led_color(10, 10, 10)
            time.sleep(2)
            machine.reset()

        wlan = network.WLAN(network.STA_IF)
        if wifi_mode == "sta" and not wlan.isconnected():
            print("\nWi-Fi disconnected. Attempting reconnect...")
            set_led_color(0, 0, 10)
            global_failures += 1
            status["wifi_connected"] = False
            status["ip"] = ""
            logger.log("WiFi disconnected")

            if global_failures > cfg["wifi"]["max_failures"]:
                print(
                    "Too many global failures ({}), resetting...".format(global_failures)
                )
                set_led_color(10, 5, 0)
                time.sleep(2)
                machine.reset()

            wifi_mode = connect_wifi(cfg, set_led_color, log_fn=logger.log)
            status["wifi_mode"] = wifi_mode
            if wifi_mode == "sta":
                set_led_color(0, 10, 0)
                sync_time(cfg)
                status["wifi_connected"] = wlan.isconnected()
                if status["wifi_connected"]:
                    status["ip"] = wlan.ifconfig()[0]
                logger.log("WiFi reconnected: STA")
            else:
                set_led_color(10, 10, 0)
                ap_iface = network.WLAN(network.AP_IF)
                status["wifi_connected"] = False
                status["ip"] = ap_iface.ifconfig()[0]
                logger.log("WiFi mode: AP")

        if (
            time.ticks_diff(now, last_transmission)
            < cfg["intervals"]["data_interval_s"] * 1000
        ):
            if admin_server:
                admin_server.poll()
            time.sleep_ms(50)
            continue
        last_transmission = now

        if wifi_mode != "sta":
            time.sleep_ms(200)
            continue

        t_shallow = ds_read(ds_s, roms_s)
        t_deep = ds_read(ds_d, roms_d)
        if t_shallow != -127.0:
            temp_for_ph_tds = t_shallow
        elif t_deep != -127.0:
            temp_for_ph_tds = t_deep
        else:
            temp_for_ph_tds = 25.0

        date_iso = get_date_iso(cfg["time"]["timezone_offset_s"])
        ph, ph_raw, ph_v = ph_value(
            adc_ph, temp_for_ph_tds, cal_file, cfg["ph"], adc_vref
        )
        tu_v, tu_raw, _ = turbidity_read(
            adc_turb, adc_vref, cfg["turbidity"]["air_threshold"]
        )
        mq = mq_read(adc135, adc137, cal_file)
        tds_ppm, tds_raw, tds_v = tds_read(
            adc_tds,
            temp_for_ph_tds,
            cfg["tds"]["vref"],
            cfg["tds"]["temp_compensation_factor"],
            cfg["tds"]["k_factor"],
        )
        status["last_reading"] = {
            "溫度(淺)": t_shallow,
            "溫度(深)": t_deep,
            "pH": ph,
            "濁度(raw)": tu_raw,
            "TDS(ppm)": tds_ppm,
            "MQ135(raw)": mq["raw135"],
            "MQ137(raw)": mq["raw137"],
        }

        payload = {
            "sensorId": cfg["payload"]["sensor_id"],
            "date": date_iso,
            "ph": ph,
            "turbidity": tu_raw,
            "hardness": tds_ppm,
            "mq135": mq["raw135"],
            "mq137": mq["raw137"],
            "temp_deep": t_deep,
            "temp_shallow": t_shallow,
            "RGB": cfg["payload"]["rgb"],
            "msg": "pH(raw={},V={},T={});TU(raw={});".format(
                ph_raw, ph_v, temp_for_ph_tds, tu_raw
            )
            + "TDS(ppm={},raw={},V={});".format(tds_ppm, tds_raw, tds_v)
            + "MQ(r135={},r137={});".format(mq["raw135"], mq["raw137"])
            + "DS(S={},D={})".format(t_shallow, t_deep),
        }

        print("SEND:", payload)
        set_led_color(0, 0, 10)

        success = False
        retry_count = 0
        max_retry_interval = cfg["api"]["max_retry_interval_s"]
        max_retries_before_wifi_reconnect = cfg["api"][
            "max_retries_before_wifi_reconnect"
        ]

        while not success:
            if admin_server:
                admin_server.poll()
            try:
                r = urequests.post(
                    cfg["api"]["url"],
                    json=payload,
                    headers=cfg["api"]["headers"],
                    timeout=cfg["api"]["post_timeout_s"],
                )
                status_code = r.status_code
                print("HTTP code:", status_code)
                r.close()
                status["last_http_code"] = status_code

                if status_code == 200:
                    print("Data sent successfully!")
                    set_led_color(0, 10, 0)
                    success = True
                    global_failures = 0
                    last_successful_transmission = time.ticks_ms()
                    status["last_send_iso"] = date_iso
                    status["last_error"] = ""
                    logger.log("HTTP 200 sent")
                else:
                    print("HTTP error {}, retrying...".format(status_code))
                    set_led_color(10, 0, 0)
                    status["last_error"] = "HTTP {}".format(status_code)
                    logger.log("HTTP error {}".format(status_code))

            except Exception as e:
                retry_count += 1
                error_msg = str(e)
                print("POST error (attempt {}): {}".format(retry_count, error_msg))
                set_led_color(10, 0, 0)
                status["last_error"] = error_msg
                logger.log("POST error: {}".format(error_msg))

                now = time.ticks_ms()
                if (
                    time.ticks_diff(now, last_transmission)
                    >= cfg["intervals"]["data_interval_s"] * 1000
                ):
                    print("Skipping retry - time for next data collection")
                    break

                if retry_count >= max_retries_before_wifi_reconnect:
                    print("Too many failures, reconnecting WiFi...")
                    set_led_color(0, 0, 10)
                    wlan = network.WLAN(network.STA_IF)
                    wlan.disconnect()
                    time.sleep(2)
                    connect_wifi(cfg, set_led_color)
                    set_led_color(0, 10, 0)
                    retry_count = 0
                    continue

                if (
                    "-202" in error_msg
                    or "SSL" in error_msg
                    or "TLS" in error_msg
                    or "MBEDTLS" in error_msg
                ):
                    retry_delay = min(retry_count * 2, 8)
                    print(
                        "SSL error detected, retrying in {} seconds...".format(
                            retry_delay
                        )
                    )
                else:
                    retry_delay = min(retry_count, max_retry_interval)
                    print("Retrying in {} seconds...".format(retry_delay))

                time.sleep(retry_delay)

            time.sleep_ms(100)
            set_led_color(0, 0, 0)


if __name__ == "__main__":
    main()
