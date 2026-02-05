import time
import machine
import network
import urequests

from methods.config import load_config, save_config
from methods.logger import Logger
from methods.sampling import agg_add, agg_avg, should_sample
from methods.time_sync import sync_time
from methods.utils import get_date_iso, safe_print, log_mem
from methods.wifi import connect_wifi, has_wifi_credentials, start_ap
from methods.mcp3208 import MCP3208, MCP3208ADC
from sensors.ds18b20 import (
    calculate_temp_calibration,
    check_temp_calibration,
    ds_read,
    ds_read_corrected,
    init_ds18b20,
)
from sensors.mq import init_mq, mq_air_calibrate, mq_read
from sensors.ph import (
    calculate_ph_calibration_params,
    check_ph_calibration,
    init_ph,
    ph_cal_from_config,
    ph_cal_three_points,
    ph_cal_three_points_auto,
    ph_value,
)
from sensors.tds import init_tds, tds_read
from sensors.turbidity import init_turbidity, turbidity_read
from sensors.orp import init_orp, orp_read
from sensors.ec import init_ec, ec_read
from web.admin_server import AdminServer
from modes.manager import get_mode_settings


# 主程式入口
def main():
    cfg = load_config()
    adc_vref = cfg["adc"]["vref"]
    cal_file = cfg["calibration"]["file"]
    logger = Logger(cfg)
    logger.log("System boot")

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    mcp_cfg = cfg.get("mcp3208", {})
    mcp_enabled = bool(mcp_cfg.get("enabled", False))

    if mcp_enabled:
        spi_id = int(mcp_cfg.get("spi_id", 2))
        baudrate = int(mcp_cfg.get("baudrate", 1000000))
        sck_pin = int(mcp_cfg.get("sck", 12))
        mosi_pin = int(mcp_cfg.get("mosi", 11))
        miso_pin = int(mcp_cfg.get("miso", 13))
        cs_pin = int(mcp_cfg.get("cs", 14))
        spi = machine.SPI(
            spi_id,
            baudrate=baudrate,
            polarity=0,
            phase=0,
            sck=machine.Pin(sck_pin),
            mosi=machine.Pin(mosi_pin),
            miso=machine.Pin(miso_pin),
        )
        mcp = MCP3208(spi, machine.Pin(cs_pin, machine.Pin.OUT, value=1))

        ph_cfg = cfg.get("ph", {})
        turb_cfg = cfg.get("turbidity", {})
        mq_cfg = cfg.get("mq", {})
        tds_cfg = cfg.get("tds", {})
        ec_cfg = cfg.get("ec", {})
        orp_cfg = cfg.get("orp", {})

        adc_ph = MCP3208ADC(mcp, ph_cfg.get("ch", 0))
        adc_turb = MCP3208ADC(mcp, turb_cfg.get("ch", 1))
        adc135 = MCP3208ADC(mcp, mq_cfg.get("ch_135", 2))
        adc137 = MCP3208ADC(mcp, mq_cfg.get("ch_137", 3))
        adc_tds = MCP3208ADC(mcp, tds_cfg.get("ch", 4))
        adc_ec = MCP3208ADC(mcp, ec_cfg.get("ch", 5))
        adc_orp = MCP3208ADC(mcp, orp_cfg.get("ch", 6))
    else:
        adc_ph = init_ph(cfg["ph"]["pin"])
        adc_turb = init_turbidity(cfg["turbidity"]["pin"])
        adc135, adc137 = init_mq(cfg["mq"]["pin_135"], cfg["mq"]["pin_137"])
        adc_tds = init_tds(cfg["tds"]["pin"])
        adc_ec = init_ec(cfg.get("ec", {}).get("pin", 0))
        adc_orp = init_orp(cfg.get("orp", {}).get("pin", 0))
    ds_s, roms_s = init_ds18b20(cfg["ds18b20"]["pin_shallow"])
    ds_d, roms_d = init_ds18b20(cfg["ds18b20"]["pin_deep"])

    temp_offset = cfg["ds18b20"].get("shallow_offset", 0.0)
    temp_scale = cfg["ds18b20"].get("shallow_scale", 1.0)

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
    last_send_ms = None
    last_sample_ms = 0
    agg = {}
    last_sample = {}
    global_failures = 0
    last_successful_transmission = time.ticks_ms()

    debug_cfg = cfg.get("debug", {})
    mem_trace = bool(debug_cfg.get("mem_trace", False))
    mem_trace_force_gc = bool(debug_cfg.get("mem_trace_force_gc", False))

    mode_cfg = get_mode_settings(cfg)
    web_mode = mode_cfg["mode"]
    send_enabled = mode_cfg["send_enabled"]
    refresh_s = mode_cfg["refresh_s"]
    intervals_cfg = cfg.get("intervals", {})
    sample_interval_s = int(intervals_cfg.get("sample_interval_s", 1))
    wifi_quiet_s = int(intervals_cfg.get("wifi_quiet_s", 3))

    # 記錄記憶體使用狀態（除錯用）
    def _mem(tag):
        if mem_trace:
            log_mem(tag, log_fn=logger.log, force_gc=mem_trace_force_gc)

    safe_print("Initializing WiFi connection...")
    wifi_mode = connect_wifi(cfg, log_fn=logger.log)
    status["wifi_mode"] = wifi_mode
    if wifi_mode == "sta":
        sync_time(cfg)
        status["wifi_connected"] = wlan.isconnected()
        if status["wifi_connected"]:
            status["ip"] = wlan.ifconfig()[0]
        logger.log("WiFi mode: STA")
    else:
        ap_iface = network.WLAN(network.AP_IF)
        status["wifi_connected"] = False
        status["ip"] = ap_iface.ifconfig()[0]
        logger.log("WiFi mode: AP")

    _mem("after_wifi_init")

    while True:
        _mem("loop_start")
        if admin_server:
            admin_server.poll()

        mode_cfg = get_mode_settings(cfg)
        web_mode = mode_cfg["mode"]
        send_enabled = mode_cfg["send_enabled"]
        refresh_s = mode_cfg["refresh_s"]
        intervals_cfg = cfg.get("intervals", {})
        sample_interval_s = int(intervals_cfg.get("sample_interval_s", 1))
        wifi_quiet_s = int(intervals_cfg.get("wifi_quiet_s", 3))

        if wifi_mode == "sta" and not has_wifi_credentials(cfg):
            logger.log("No SSID detected, switching to AP")
            ap_iface = start_ap(cfg, log_fn=logger.log)
            wifi_mode = "ap"
            status["wifi_mode"] = wifi_mode
            status["wifi_connected"] = False
            status["ip"] = ap_iface.ifconfig()[0]

        now = time.ticks_ms()
        if (
            send_enabled
            and wifi_mode == "sta"
            and time.ticks_diff(now, last_successful_transmission)
            > cfg["watchdog"]["no_success_reset_ms"]
        ):
            safe_print(
                "Watchdog triggered - no successful transmission for 5 minutes, resetting..."
            )
            time.sleep(2)
            machine.reset()

        wlan = network.WLAN(network.STA_IF)
        if wifi_mode == "sta" and not wlan.isconnected():
            safe_print("\nWi-Fi disconnected. Attempting reconnect...")
            global_failures += 1
            status["wifi_connected"] = False
            status["ip"] = ""
            logger.log("WiFi disconnected")

            if global_failures > cfg["wifi"]["max_failures"]:
                safe_print(
                    "Too many global failures ({}), resetting...".format(
                        global_failures
                    )
                )
                time.sleep(2)
                machine.reset()

            wifi_mode = connect_wifi(cfg, log_fn=logger.log)
            status["wifi_mode"] = wifi_mode
            if wifi_mode == "sta":
                sync_time(cfg)
                status["wifi_connected"] = wlan.isconnected()
                if status["wifi_connected"]:
                    status["ip"] = wlan.ifconfig()[0]
                logger.log("WiFi reconnected: STA")
            else:
                ap_iface = network.WLAN(network.AP_IF)
                status["wifi_connected"] = False
                status["ip"] = ap_iface.ifconfig()[0]
                logger.log("WiFi mode: AP")

        interval_s = mode_cfg["interval_s"]

        interval_ms = int(interval_s * 1000)
        quiet_ms = int(wifi_quiet_s * 1000)
        now = time.ticks_ms()

        if (
            time.ticks_diff(now, last_sample_ms) >= sample_interval_s * 1000
            and should_sample(now, last_send_ms, interval_ms, quiet_ms, send_enabled)
        ):
            last_sample_ms = now
            reading_iso = get_date_iso(cfg["time"]["timezone_offset_s"])

            t_shallow = ds_read_corrected(
                ds_s, roms_s, temp_offset, temp_scale, is_shallow=True
            )
            t_deep = ds_read_corrected(ds_d, roms_d, temp_offset, temp_scale)
            if t_shallow != -127.0:
                temp_for_ph_tds = t_shallow
            elif t_deep != -127.0:
                temp_for_ph_tds = t_deep
            else:
                temp_for_ph_tds = 25.0

            ph, ph_raw, ph_v = ph_value(
                adc_ph, temp_for_ph_tds, cal_file, cfg["ph"], adc_vref
            )
            turb = turbidity_read(adc_turb, cfg["turbidity"], adc_vref)
            turb_raw = turb.get("raw")
            turb_percent = turb.get("percent")
            turb_ntu = turb.get("ntu")
            mq = mq_read(adc135, adc137, cal_file)
            tds_ppm, tds_raw, tds_v = tds_read(
                adc_tds,
                temp_for_ph_tds,
                cfg["tds"]["vref"],
                cfg["tds"]["temp_compensation_factor"],
                cfg["tds"]["k_factor"],
            )
            ec = ec_read(adc_ec, cfg.get("ec", {}), adc_vref)
            ec_us = ec.get("ec_us")
            orp = orp_read(adc_orp, cfg.get("orp", {}), adc_vref)
            orp_mv = orp.get("orp_mv")
            orp_v_sensor = orp.get("v_sensor")
            orp_valid = orp.get("valid")
            orp_reason = orp.get("reason")

            last_sample = {
                "t_shallow": t_shallow,
                "t_deep": t_deep,
                "ph": ph,
                "turb_raw": turb_raw,
                "turb_percent": turb_percent,
                "turb_ntu": turb_ntu,
                "tds_ppm": tds_ppm,
                "ec_us": ec_us,
                "mq135": mq["raw135"],
                "mq137": mq["raw137"],
                "orp_mv": orp_mv,
                "orp_v_sensor": orp_v_sensor,
                "ph_raw": ph_raw,
                "ph_v": ph_v,
                "tds_raw": tds_raw,
                "tds_v": tds_v,
                "temp_for_ph_tds": temp_for_ph_tds,
                "ec_raw": ec.get("raw"),
                "ec_v": ec.get("v"),
                "orp_raw": orp.get("raw"),
                "orp_mv_no_offset": orp.get("orp_mv_no_offset"),
                "orp_valid": orp_valid,
                "orp_reason": orp_reason,
                "reading_ms": now,
                "reading_iso": reading_iso,
            }

            agg_add(agg, "t_shallow", t_shallow)
            agg_add(agg, "t_deep", t_deep)
            agg_add(agg, "ph", ph)
            agg_add(agg, "turb_raw", turb_raw)
            agg_add(agg, "turb_percent", turb_percent)
            agg_add(agg, "turb_ntu", turb_ntu)
            agg_add(agg, "tds_ppm", tds_ppm)
            agg_add(agg, "ec_us", ec_us)
            agg_add(agg, "mq135", mq["raw135"])
            agg_add(agg, "mq137", mq["raw137"])
            if orp_valid:
                agg_add(agg, "orp_mv", orp_mv)
                agg_add(agg, "orp_v_sensor", orp_v_sensor)
                agg_add(agg, "orp_raw", orp.get("raw"))

            status["last_reading"] = {
                "溫度(淺)": t_shallow,
                "溫度(深)": t_deep,
                "pH": ph,
                "濁度(raw)": turb_raw,
                "清澈度(%)": "NA" if turb_percent is None else turb_percent,
                "濁度(NTU)": "NA" if turb_ntu is None else turb_ntu,
                "TDS(ppm)": tds_ppm,
                "EC(uS/cm)": "NA" if ec_us is None else ec_us,
                "ORP(mV)": "NA" if orp_mv is None else orp_mv,
                "ORP(V)": "NA" if orp_v_sensor is None else orp_v_sensor,
                "MQ135(raw)": mq["raw135"],
                "MQ137(raw)": mq["raw137"],
            }
            status["last_reading_detail"] = {
                "ph_raw": ph_raw,
                "ph_v": ph_v,
                "turbidity_raw": turb_raw,
                "turbidity_percent": turb_percent,
                "turbidity_ntu": turb_ntu,
                "tds_raw": tds_raw,
                "tds_v": tds_v,
                "temp_for_ph_tds": temp_for_ph_tds,
                "temp_shallow": t_shallow,
                "temp_deep": t_deep,
                "reading_ms": now,
                "reading_iso": reading_iso,
                "ec_raw": ec.get("raw"),
                "ec_v": ec.get("v"),
                "ec_us": ec_us,
                "orp_raw": orp.get("raw"),
                "orp_v_adc": orp.get("v_adc"),
                "orp_v_sensor": orp_v_sensor,
                "orp_mv": orp_mv,
                "orp_mv_no_offset": orp.get("orp_mv_no_offset"),
                "orp_valid": orp_valid,
                "orp_reason": orp_reason,
            }
            status["last_calibration"] = {
                "pH": cfg.get("ph", {}).get("last_calibration_iso"),
                "濁度": cfg.get("turbidity", {}).get("last_calibration_iso"),
                "MQ": cfg.get("mq", {}).get("last_calibration_iso"),
                "溫度": cfg.get("ds18b20", {}).get("last_calibration_iso"),
                "TDS": cfg.get("tds", {}).get("last_calibration_iso"),
                "EC": cfg.get("ec", {}).get("last_calibration_iso"),
                "ORP": cfg.get("orp", {}).get("last_calibration_iso"),
            }
            status["web_mode"] = web_mode
            status["web_refresh_s"] = refresh_s

        if time.ticks_diff(now, last_transmission) < interval_s * 1000:
            if admin_server:
                admin_server.poll()
            time.sleep_ms(50)
            continue
        last_transmission = now

        if wifi_mode != "sta" and send_enabled:
            time.sleep_ms(200)
            continue

        date_iso = get_date_iso(cfg["time"]["timezone_offset_s"])
        avg_t_shallow = agg_avg(agg, "t_shallow")
        avg_t_deep = agg_avg(agg, "t_deep")
        avg_ph = agg_avg(agg, "ph")
        avg_turb_raw = agg_avg(agg, "turb_raw")
        avg_turb_percent = agg_avg(agg, "turb_percent")
        avg_turb_ntu = agg_avg(agg, "turb_ntu")
        avg_tds_ppm = agg_avg(agg, "tds_ppm")
        avg_ec_us = agg_avg(agg, "ec_us")
        avg_mq135 = agg_avg(agg, "mq135")
        avg_mq137 = agg_avg(agg, "mq137")
        avg_orp_mv = agg_avg(agg, "orp_mv")
        avg_orp_v = agg_avg(agg, "orp_v_sensor")

        t_shallow = avg_t_shallow if avg_t_shallow is not None else last_sample.get("t_shallow", -127.0)
        t_deep = avg_t_deep if avg_t_deep is not None else last_sample.get("t_deep", -127.0)
        ph = avg_ph if avg_ph is not None else last_sample.get("ph", 7.0)
        turb_raw = avg_turb_raw if avg_turb_raw is not None else last_sample.get("turb_raw", 0)
        turb_percent = avg_turb_percent if avg_turb_percent is not None else last_sample.get("turb_percent")
        turb_ntu = avg_turb_ntu if avg_turb_ntu is not None else last_sample.get("turb_ntu")
        tds_ppm = avg_tds_ppm if avg_tds_ppm is not None else last_sample.get("tds_ppm", 0)
        ec_us = avg_ec_us if avg_ec_us is not None else last_sample.get("ec_us")
        mq135 = avg_mq135 if avg_mq135 is not None else last_sample.get("mq135", 0)
        mq137 = avg_mq137 if avg_mq137 is not None else last_sample.get("mq137", 0)
        orp_mv = avg_orp_mv if avg_orp_mv is not None else last_sample.get("orp_mv")
        orp_v_sensor = avg_orp_v if avg_orp_v is not None else last_sample.get("orp_v_sensor")
        ph_raw = last_sample.get("ph_raw")
        ph_v = last_sample.get("ph_v")
        tds_raw = last_sample.get("tds_raw")
        tds_v = last_sample.get("tds_v")
        temp_for_ph_tds = last_sample.get("temp_for_ph_tds", 25.0)

        if not send_enabled:
            time.sleep_ms(10)
            continue

        last_send_ms = now
        local_ip = status.get("ip") or ""
        payload = {
            "sensorId": cfg["payload"]["sensor_id"],
            "date": date_iso,
            "local_ip": local_ip,
            "ph": ph,
            "turbidity_raw": turb_raw,
            "turbidity_percent": 0 if turb_percent is None else turb_percent,
            "turbidity_ntu": 0 if turb_ntu is None else turb_ntu,
            "hardness": tds_ppm,
            "ec_us_cm": 0 if ec_us is None else ec_us,
            "orp_mv": 0 if orp_mv is None else orp_mv,
            "mq135": mq135,
            "mq137": mq137,
            "temp_deep": t_deep,
            "temp_shallow": t_shallow,
            "RGB": [0, 0, 0],
            "msg": "pH(raw={},V={},T={});TU(raw={},%={},NTU={});".format(
                ph_raw,
                ph_v,
                temp_for_ph_tds,
                turb_raw,
                "NA" if turb_percent is None else turb_percent,
                "NA" if turb_ntu is None else turb_ntu,
            )
            + "TDS(ppm={},raw={},V={});".format(tds_ppm, tds_raw, tds_v)
            + "EC(uS/cm={},V={});".format(
                "NA" if ec_us is None else ec_us,
                last_sample.get("ec_v"),
            )
            + "ORP(mV={},V={});".format(
                "NA" if orp_mv is None else orp_mv,
                "NA" if orp_v_sensor is None else orp_v_sensor,
            )
            + "MQ(r135={},r137={});".format(mq135, mq137)
            + "DS(S={},D={})".format(t_shallow, t_deep),
        }

        safe_print("SEND:", payload)

        success = False
        retry_count = 0
        max_retries = int(cfg["api"].get("max_retries", 6))
        max_retry_interval = int(cfg["api"].get("max_retry_interval_s", 3))
        ssl_retry_max = int(cfg["api"].get("ssl_retry_max_s", 6))
        last_error = ""

        while not success and retry_count < max_retries:
            if admin_server:
                admin_server.poll()
            try:
                _mem("http_post_start")
                try:
                    r = urequests.post(
                        cfg["api"]["url"],
                        json=payload,
                        headers=cfg["api"]["headers"],
                        timeout=cfg["api"]["post_timeout_s"],
                    )
                except TypeError:
                    r = urequests.post(
                        cfg["api"]["url"],
                        json=payload,
                        headers=cfg["api"]["headers"],
                    )
                status_code = r.status_code
                safe_print("HTTP code:", status_code)
                r.close()
                status["last_http_code"] = status_code
                _mem("http_post_end")

                if status_code == 200:
                    safe_print("Data sent successfully!")
                    success = True
                    global_failures = 0
                    last_successful_transmission = time.ticks_ms()
                    status["last_send_iso"] = date_iso
                    status["last_error"] = ""
                    logger.log("HTTP 200 sent")
                else:
                    retry_count += 1
                    last_error = "HTTP {}".format(status_code)
                    safe_print("HTTP error {}, retrying...".format(status_code))
                    status["last_error"] = last_error
                    logger.log("HTTP error {}".format(status_code))

            except Exception as e:
                retry_count += 1
                last_error = str(e)
                safe_print("POST error (attempt {}): {}".format(retry_count, last_error))
                status["last_error"] = last_error
                logger.log("POST error: {}".format(last_error))
                _mem("http_post_error")

            now = time.ticks_ms()
            if (
                time.ticks_diff(now, last_transmission)
                >= cfg["intervals"]["data_interval_s"] * 1000
            ):
                safe_print("Skipping retry - time for next data collection")
                break

            if not success and retry_count < max_retries:
                if (
                    "-202" in last_error
                    or "SSL" in last_error
                    or "TLS" in last_error
                    or "MBEDTLS" in last_error
                ):
                    retry_delay = min(retry_count * 2, ssl_retry_max)
                    safe_print(
                        "SSL error detected, retrying in {} seconds...".format(
                            retry_delay
                        )
                    )
                else:
                    retry_delay = min(retry_count, max_retry_interval)
                    safe_print("Retrying in {} seconds...".format(retry_delay))
                time.sleep(retry_delay)
            elif retry_count >= max_retries:
                safe_print(
                    "Max retries ({}) reached, giving up for this cycle".format(
                        max_retries
                    )
                )
                break

            time.sleep_ms(100)

        agg = {}


# ---- REPL 校正便捷 ----
# pH校正：
#   from sensors.ph import check_ph_calibration; check_ph_calibration(load_config()["ph"])
#   from sensors.ph import calculate_ph_calibration_params; calculate_ph_calibration_params(load_config()["ph"])
# 溫度校正：
#   from sensors.ds18b20 import check_temp_calibration; check_temp_calibration(ds_s, roms_s, ds_d, roms_d, offset, scale)
#   from sensors.ds18b20 import calculate_temp_calibration; calculate_temp_calibration(ds_s, roms_s, ds_d, roms_d)
# 其他校正：
#   from sensors.ph import ph_cal_from_config; ph_cal_from_config(load_config()["calibration"]["file"], load_config()["ph"])
#   from sensors.mq import mq_air_calibrate; mq_air_calibrate(adc135, adc137, load_config()["calibration"]["file"], 30)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import sys
        import io

        buf = io.StringIO()
        sys.print_exception(e, buf)
        msg_err = buf.getvalue()

        safe_print("--- CRASH DETECTED ---")
        safe_print(msg_err)

        try:
            cfg = load_config()
            wlan = network.WLAN(network.STA_IF)
            if not wlan.isconnected():
                safe_print("Crash Handler: WiFi disconnected, attempting reconnect...")
                connect_wifi(cfg)

            if wlan.isconnected():
                safe_print("Crash Handler: WiFi connected, sending report.")
                try:
                    date_iso = get_date_iso(cfg["time"]["timezone_offset_s"])
                except Exception:
                    date_iso = "unknown"
                try:
                    local_ip = wlan.ifconfig()[0]
                except Exception:
                    local_ip = ""

                error_payload = {
                    "sensorId": cfg["payload"]["sensor_id"],
                    "date": date_iso,
                    "local_ip": local_ip,
                    "msg_err": msg_err,
                }
                try:
                    try:
                        r = urequests.post(
                            cfg["api"]["url"],
                            json=error_payload,
                            headers=cfg["api"]["headers"],
                            timeout=5,
                        )
                    except TypeError:
                        r = urequests.post(
                            cfg["api"]["url"],
                            json=error_payload,
                            headers=cfg["api"]["headers"],
                        )
                    r.close()
                    safe_print("Crash Handler: Report sent.")
                except Exception as post_e:
                    safe_print(
                        "Crash Handler: Failed to send report: {}".format(post_e)
                    )
            else:
                safe_print(
                    "Crash Handler: Could not connect to WiFi, unable to send report."
                )

        except Exception as report_e:
            safe_print("Crash Handler: Error during reporting: {}".format(report_e))

        safe_print("Crash Handler: Rebooting in 5 seconds...")
        time.sleep(5)
        machine.reset()
