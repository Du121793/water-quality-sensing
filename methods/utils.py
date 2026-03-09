import time


# 安全列印，避免輸出例外中斷主流程
def safe_print(*a, **kw):
    try:
        print(*a, **kw)
        return
    except Exception:
        pass

    try:
        output = " ".join(str(arg) for arg in a)
        output = "".join(ch for ch in output if ord(ch) < 128)
        if "end" in kw:
            print(output, end=kw.get("end"))
        else:
            print(output)
    except Exception:
        pass


# 記錄記憶體使用狀態
def log_mem(tag, log_fn=None, force_gc=False):
    try:
        import gc
    except Exception:
        return

    try:
        if force_gc:
            gc.collect()
        free = gc.mem_free()
        alloc = gc.mem_alloc()
        safe_print("[MEM] {} free={} alloc={}".format(tag, free, alloc))
        if log_fn:
            log_fn("MEM {} free={} alloc={}".format(tag, free, alloc))
    except Exception:
        return


# 取得 ISO 格式時間字串
def get_date_iso(timezone_offset_s):
    ts = time.time() + timezone_offset_s
    y, m, d, hh, mm, ss, _, _ = time.localtime(ts)
    return "%04d-%02d-%02dT%02d:%02d:%02d" % (y, m, d, hh, mm, ss)


# 取得 UTC ISO 格式字串
def get_date_iso_utc():
    y, m, d, hh, mm, ss, _, _ = time.gmtime()
    return "%04d-%02d-%02dT%02d:%02d:%02d" % (y, m, d, hh, mm, ss)


# 檢查電源穩定性
def check_power_stability(pin, samples=5, delay_ms=10, max_delta=100):
    try:
        from machine import ADC, Pin
    except Exception:
        return False

    try:
        test_adc = ADC(Pin(pin))
        test_adc.atten(ADC.ATTN_11DB)
        test_reading = test_adc.read()
        if test_reading is None or test_reading < 0:
            return False

        readings = []
        for _ in range(samples):
            readings.append(test_adc.read())
            time.sleep_ms(delay_ms)
        if max(readings) - min(readings) > max_delta:
            return False
        return True
    except Exception:
        return False
