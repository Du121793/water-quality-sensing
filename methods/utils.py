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


# 計算中位數
def median(values):
    nums = [v for v in values if isinstance(v, (int, float))]
    if not nums:
        return None
    nums.sort()
    mid = len(nums) // 2
    if len(nums) % 2 == 1:
        return float(nums[mid])
    return (nums[mid - 1] + nums[mid]) / 2.0


# 以 MAD 方式取得保留索引
def filter_indices_mad(values, k=3.0, min_valid=3):
    indexed = [(i, v) for i, v in enumerate(values) if isinstance(v, (int, float))]
    if not indexed:
        return []
    if not isinstance(k, (int, float)) or k <= 0:
        return [i for i, _ in indexed]
    med = median([v for _, v in indexed])
    if med is None:
        return [i for i, _ in indexed]
    devs = [abs(v - med) for _, v in indexed]
    mad = median(devs)
    if mad is None or mad == 0:
        return [i for i, _ in indexed]
    threshold = k * 1.4826 * mad
    kept = [i for i, v in indexed if abs(v - med) <= threshold]
    if len(kept) < int(min_valid):
        return [i for i, _ in indexed]
    return kept


# 依索引計算平均值
def avg_by_indices(values, indices):
    total = 0.0
    count = 0
    for idx in indices:
        if idx < 0 or idx >= len(values):
            continue
        v = values[idx]
        if isinstance(v, (int, float)):
            total += float(v)
            count += 1
    if count == 0:
        return None
    return total / count
