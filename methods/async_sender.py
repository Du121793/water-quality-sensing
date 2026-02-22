import time
import urequests
try:
    import _thread
except Exception:
    _thread = None

from .utils import safe_print


# 檢查是否支援背景執行緒
def async_supported():
    return _thread is not None


# 初始化非同步傳送器，建立佇列與背景執行緒
def init_async_sender(api_cfg, mem_fn):
    if _thread is None:
        return None
    sleep_ms = max(10, int(api_cfg.get("async_worker_sleep_ms", 50)))
    max_queue = max(1, int(api_cfg.get("async_queue_size", 1)))
    state = {
        "queue": [],
        "results": [],
        "lock": _thread.allocate_lock(),
        "sleep_ms": sleep_ms,
        "max_queue": max_queue,
        "drop_oldest": bool(api_cfg.get("async_drop_oldest", True)),
        "mem_fn": mem_fn,
    }
    _thread.start_new_thread(_async_send_worker, (state,))
    return state


# 將傳送任務放入佇列
def enqueue_async(state, task):
    if state is None:
        return False
    lock = state["lock"]
    lock.acquire()
    try:
        if len(state["queue"]) >= state["max_queue"]:
            if state["drop_oldest"] and state["queue"]:
                state["queue"].pop(0)
            else:
                return False
        state["queue"].append(task)
        return True
    finally:
        lock.release()


# 取出背景傳送結果
def drain_async_results(state):
    if state is None:
        return []
    lock = state["lock"]
    lock.acquire()
    try:
        if not state["results"]:
            return []
        results = state["results"]
        state["results"] = []
        return results
    finally:
        lock.release()


# 背景執行緒：取佇列資料並送出
def _async_send_worker(state):
    while True:
        task = None
        lock = state["lock"]
        lock.acquire()
        try:
            if state["queue"]:
                task = state["queue"].pop(0)
        finally:
            lock.release()

        if task is None:
            time.sleep_ms(state["sleep_ms"])
            continue

        result = post_with_retry(task, poll_fn=None, mem_fn=state.get("mem_fn"))
        lock.acquire()
        try:
            state["results"].append(result)
        finally:
            lock.release()
        time.sleep_ms(state["sleep_ms"])


# 執行 HTTP POST，支援重試與錯誤回報
def post_with_retry(task, poll_fn=None, mem_fn=None):
    success = False
    retry_count = 0
    max_retries = int(task.get("max_retries", 6))
    max_retry_interval = int(task.get("max_retry_interval_s", 3))
    ssl_retry_max = int(task.get("ssl_retry_max_s", 6))
    last_error = ""
    status_code = None

    while not success and retry_count < max_retries:
        if poll_fn:
            poll_fn()
        try:
            if mem_fn:
                mem_fn("http_post_start")
            try:
                r = urequests.post(
                    task["api_url"],
                    json=task["payload"],
                    headers=task["headers"],
                    timeout=task.get("timeout_s"),
                )
            except TypeError:
                r = urequests.post(
                    task["api_url"],
                    json=task["payload"],
                    headers=task["headers"],
                )
            status_code = r.status_code
            safe_print("HTTP code:", status_code)
            r.close()
            if mem_fn:
                mem_fn("http_post_end")

            if status_code == 200:
                safe_print("Data sent successfully!")
                success = True
                last_error = ""
            else:
                retry_count += 1
                last_error = "HTTP {}".format(status_code)
                safe_print("HTTP error {}, retrying...".format(status_code))

        except Exception as e:
            retry_count += 1
            last_error = str(e)
            safe_print("POST error (attempt {}): {}".format(retry_count, last_error))
            if mem_fn:
                mem_fn("http_post_error")

        now = time.ticks_ms()
        if time.ticks_diff(now, task["start_ms"]) >= task["data_interval_ms"]:
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

    return {
        "ok": success,
        "status_code": status_code,
        "error": last_error,
        "date_iso": task.get("date_iso", ""),
    }
