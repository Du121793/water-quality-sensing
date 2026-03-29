import time
import machine
try:
    import ustruct as struct
except Exception:
    import struct

from methods.utils import safe_print

_last_ph_values = []


# 初始化 pH RS485 UART
def init_ph_rs485(rs485_cfg):
    uart_id = int(rs485_cfg.get("uart_id", 2))
    baudrate = int(rs485_cfg.get("baudrate", 4800))
    tx = int(rs485_cfg.get("tx", 18))
    rx = int(rs485_cfg.get("rx", 21))
    timeout_ms = int(rs485_cfg.get("timeout_ms", 300))
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


# 計算 Modbus RTU CRC16
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


# 讀取保持暫存器 (0x03)
def _read_holding_registers(uart, addr, start, count, timeout_ms):
    payload = bytearray(
        [(start >> 8) & 0xFF, start & 0xFF, (count >> 8) & 0xFF, count & 0xFF]
    )
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


# 寫入多個暫存器 (0x10)
def _write_multiple_registers(uart, addr, start, values, timeout_ms):
    count = len(values)
    byte_count = count * 2
    payload = bytearray(
        [
            (start >> 8) & 0xFF,
            start & 0xFF,
            (count >> 8) & 0xFF,
            count & 0xFF,
            byte_count,
        ]
    )
    for value in values:
        payload.append((value >> 8) & 0xFF)
        payload.append(value & 0xFF)
    frame = _build_frame(addr, 0x10, payload)
    _uart_flush(uart)
    uart.write(frame)

    expected_len = 8
    resp = _uart_read_exact(uart, expected_len, timeout_ms)
    if not resp or len(resp) != expected_len:
        return False, "timeout"
    if resp[0] != addr or resp[1] != 0x10:
        return False, "func_mismatch"
    if resp[2] != ((start >> 8) & 0xFF) or resp[3] != (start & 0xFF):
        return False, "addr_mismatch"
    if resp[4] != ((count >> 8) & 0xFF) or resp[5] != (count & 0xFF):
        return False, "count_mismatch"
    crc = _crc16(resp[:-2])
    if resp[-2] != (crc & 0xFF) or resp[-1] != ((crc >> 8) & 0xFF):
        return False, "crc_error"
    return True, ""


# 平滑 pH 讀值
def _smooth_ph_value(ph, smoothing_window):
    _last_ph_values.append(ph)
    if len(_last_ph_values) > smoothing_window:
        _last_ph_values.pop(0)
    if len(_last_ph_values) >= 2:
        return sum(_last_ph_values) / len(_last_ph_values)
    return ph


# 讀取 RS485 pH 感測器
def ph_rs485_read(uart, ph_cfg):
    if not uart:
        return {"ok": False, "error": "uart_not_ready"}
    rs_cfg = ph_cfg.get("rs485", {})
    addr = int(rs_cfg.get("addr", 3))
    timeout_ms = int(rs_cfg.get("timeout_ms", 300))
    retries = int(rs_cfg.get("retries", 1))
    last_error = ""

    for _ in range(retries + 1):
        data, err = _read_holding_registers(uart, addr, 0x0000, 2, timeout_ms)
        if data:
            try:
                raw_ph = struct.unpack(">h", data[0:2])[0]
                raw_temp = struct.unpack(">h", data[2:4])[0]
            except Exception:
                last_error = "decode_error"
                continue
            ph = raw_ph / 100.0
            temp_c = raw_temp / 10.0
            if ph != ph or temp_c != temp_c:
                last_error = "nan"
                continue
            min_ph = float(ph_cfg.get("min", 0.0))
            max_ph = float(ph_cfg.get("max", 14.0))
            ph = max(min_ph, min(max_ph, ph))
            smoothing_window = int(ph_cfg.get("smoothing_window", 1))
            if smoothing_window > 1:
                ph = _smooth_ph_value(ph, smoothing_window)
            return {
                "ok": True,
                "ph": round(ph, 2),
                "temp_c": round(temp_c, 1),
                "raw_ph": raw_ph,
                "raw_temp": raw_temp,
                "error": "",
            }
        last_error = err or "read_failed"

    if ph_cfg.get("debug") and last_error:
        safe_print("pH RS485 讀取錯誤: {}".format(last_error))
    return {"ok": False, "error": last_error}


# 兩點校正寫入
def ph_rs485_calibrate_point(uart, ph_cfg, point_index, ph_value):
    if not uart:
        return False, "uart_not_ready"
    rs_cfg = ph_cfg.get("rs485", {})
    addr = int(rs_cfg.get("addr", 3))
    timeout_ms = int(rs_cfg.get("timeout_ms", 300))
    if point_index not in (1, 2):
        return False, "point_invalid"
    try:
        value_int = int(round(float(ph_value) * 100))
    except Exception:
        return False, "value_invalid"
    if value_int < 0:
        value_int = 0
    if value_int > 1400:
        value_int = 1400
    ok, err = _write_multiple_registers(
        uart, addr, 0x0120, [point_index, value_int], timeout_ms
    )
    if ok:
        return True, ""
    return False, err
