import time


# 累積平均用
def agg_add(agg, key, value):
    if isinstance(value, (int, float)):
        item = agg.get(key)
        if not item:
            item = {"sum": 0.0, "count": 0}
        item["sum"] += float(value)
        item["count"] += 1
        agg[key] = item


# 取得平均值
def agg_avg(agg, key):
    item = agg.get(key)
    if item and item.get("count", 0) > 0:
        return item["sum"] / item["count"]
    return None


# 判斷是否應該進行取樣
def should_sample(now_ms, last_send_ms, interval_ms, quiet_ms, enabled):
    if not enabled:
        return True
    if last_send_ms is None:
        return True
    since_send = time.ticks_diff(now_ms, last_send_ms)
    if 0 <= since_send < quiet_ms:
        return False
    time_to_send = interval_ms - since_send
    if time_to_send <= quiet_ms:
        return False
    return True
