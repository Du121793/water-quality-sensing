import time
import machine
try:
    import ustruct as struct
except Exception:
    import struct

from methods.utils import safe_print, get_date_iso


# 初始化溶氧感測器 UART
def init_do(do_cfg):
    uart_id = int(do_cfg.get("uart_id", 2))
    baudrate = int(do_cfg.get("baudrate", 4800))
    tx = int(do_cfg.get("tx", 18))
    rx = int(do_cfg.get("rx", 21))
    timeout_ms = int(do_cfg.get("timeout_ms", 300))
    try:
        uart = machine.UART(
            uart_id,
            baudrate=baudrate,
            bits=8,
            parity=None,
            stop=1,
            tx=machine.Pin(tx),
            rx=machine.Pin(rx),
            timeout=timeout_ms,
        )
    except TypeError:
        uart = machine.UART(
            uart_id,
            baudrate=baudrate,
            bits=8,
            parity=None,
            stop=1,
            tx=tx,
            rx=rx,
            timeout=timeout_ms,
        )
    return uart


# Modbus RTU CRC16
def _crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


# 組出 Modbus RTU 封包
def _build_frame(addr, func, payload):
    frame = bytearray([addr, func])
    frame.extend(payload)
    crc = _crc16(frame)
    frame.append(crc & 0xFF)
    frame.append((crc >> 8) & 0xFF)
    return frame


# 清空 UART 緩衝區
def _uart_flush(uart):
    try:
        while uart.any():
            uart.read()
    except Exception:
        uart.read()


# 讀取固定長度資料
def _uart_read_exact(uart, length, timeout_ms):
    buf = bytearray()
    start = time.ticks_ms()
    while len(buf) < length:
        if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
            return None
        chunk = uart.read(length - len(buf))
        if chunk:
            buf.extend(chunk)
        else:
            time.sleep_ms(5)
    return bytes(buf)


# 讀取暫存器 (0x03)
def _read_holding_registers(uart, addr, start, count, timeout_ms):
    payload = bytearray([(start >> 8) & 0xFF, start & 0xFF, (count >> 8) & 0xFF, count & 0xFF])
    frame = _build_frame(addr, 0x03, payload)
    _uart_flush(uart)
    uart.write(frame)

    expected_len = 5 + count * 2
    resp = _uart_read_exact(uart, expected_len, timeout_ms)
    if not resp or len(resp) != expected_len:
        return None, "timeout"
    if resp[0] != addr:
        return None, "addr_mismatch"
    if resp[1] & 0x80:
        return None, "modbus_error_{:02x}".format(resp[2])
    if resp[1] != 0x03:
        return None, "func_mismatch"
    if resp[2] != count * 2:
        return None, "bytecount_mismatch"
    crc = _crc16(resp[:-2])
    if resp[-2] != (crc & 0xFF) or resp[-1] != ((crc >> 8) & 0xFF):
        return None, "crc_error"
    return resp[3:-2], ""


# 寫入單一暫存器 (0x06)
def _write_single_register(uart, addr, reg, value, timeout_ms):
    payload = bytearray(
        [(reg >> 8) & 0xFF, reg & 0xFF, (value >> 8) & 0xFF, value & 0xFF]
    )
    frame = _build_frame(addr, 0x06, payload)
    _uart_flush(uart)
    uart.write(frame)

    expected_len = 8
    resp = _uart_read_exact(uart, expected_len, timeout_ms)
    if not resp or len(resp) != expected_len:
        return False, "timeout"
    crc = _crc16(resp[:-2])
    if resp[-2] != (crc & 0xFF) or resp[-1] != ((crc >> 8) & 0xFF):
        return False, "crc_error"
    if resp[:6] != frame[:6]:
        return False, "echo_mismatch"
    return True, ""


# 讀取溶氧資料
def do_read(uart, do_cfg):
    if not uart:
        return {"ok": False, "error": "uart_not_ready"}
    addr = int(do_cfg.get("addr", 1))
    timeout_ms = int(do_cfg.get("timeout_ms", 300))
    retries = int(do_cfg.get("retries", 1))
    last_error = ""

    for _ in range(retries + 1):
        data, err = _read_holding_registers(uart, addr, 0x0000, 6, timeout_ms)
        if data:
            try:
                do_sat = struct.unpack(">f", data[0:4])[0]
                do_mg_l = struct.unpack(">f", data[4:8])[0]
                do_temp_c = struct.unpack(">f", data[8:12])[0]
            except Exception:
                last_error = "decode_error"
                continue
            if do_sat != do_sat or do_mg_l != do_mg_l or do_temp_c != do_temp_c:
                last_error = "nan"
                continue
            return {
                "ok": True,
                "do_sat": round(do_sat, 2),
                "do_mg_l": round(do_mg_l, 2),
                "do_temp_c": round(do_temp_c, 2),
                "error": "",
            }
        last_error = err or "read_failed"

    if do_cfg.get("debug") and last_error:
        safe_print("DO read error: {}".format(last_error))
    return {"ok": False, "error": last_error}


# 寫入鹽度與氣壓補償
def do_apply_compensation(uart, cfg, save_config_fn, salinity_ppt=None, pressure_kpa=None):
    do_cfg = cfg.get("do", {})
    addr = int(do_cfg.get("addr", 1))
    timeout_ms = int(do_cfg.get("timeout_ms", 300))
    ok = True
    errors = []

    if salinity_ppt is None:
        salinity_ppt = do_cfg.get("salinity_ppt")
    if pressure_kpa is None:
        pressure_kpa = do_cfg.get("pressure_kpa")

    if isinstance(salinity_ppt, (int, float)):
        value = int(round(float(salinity_ppt)))
        if value < 0:
            value = 0
        success, err = _write_single_register(uart, addr, 0x1020, value, timeout_ms)
        if not success:
            ok = False
            errors.append(err)
    if isinstance(pressure_kpa, (int, float)):
        value = int(round(float(pressure_kpa) * 100))
        if value < 0:
            value = 0
        success, err = _write_single_register(uart, addr, 0x1022, value, timeout_ms)
        if not success:
            ok = False
            errors.append(err)

    do_cfg["salinity_ppt"] = salinity_ppt
    do_cfg["pressure_kpa"] = pressure_kpa
    if ok:
        do_cfg["last_calibration_iso"] = get_date_iso(
            cfg.get("time", {}).get("timezone_offset_s", 0)
        )
    cfg["do"] = do_cfg
    save_config_fn(cfg)

    return ok, ",".join(errors)


# 執行零點或 100% 飽和校正
def do_calibrate(uart, cfg, save_config_fn, mode):
    do_cfg = cfg.get("do", {})
    addr = int(do_cfg.get("addr", 1))
    timeout_ms = int(do_cfg.get("timeout_ms", 300))
    if mode == "zero":
        value = 0x0001
    elif mode == "span":
        value = 0x0002
    else:
        return False, "mode_invalid"

    success, err = _write_single_register(uart, addr, 0x1010, value, timeout_ms)
    if success:
        do_cfg["last_calibration_iso"] = get_date_iso(
            cfg.get("time", {}).get("timezone_offset_s", 0)
        )
        cfg["do"] = do_cfg
        save_config_fn(cfg)
        return True, ""
    return False, err
