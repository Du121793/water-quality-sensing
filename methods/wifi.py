import time
import machine
import network


# 檢查 SSID 是否有效
def _ssid_valid(ssid):
    return isinstance(ssid, str) and ssid.strip() != ""


# 檢查是否有可用的 Wi-Fi 帳密
def has_wifi_credentials(cfg):
    wifi_cfg = cfg.get("wifi", {})
    primary = wifi_cfg.get("primary", {})
    backup = wifi_cfg.get("backup", {})
    return _ssid_valid(primary.get("ssid", "")) or _ssid_valid(backup.get("ssid", ""))


# 設定加密 AP 參數
def _ap_config_secure(ap, ssid, password, channel, hidden, authmode):
    try:
        ap.config(
            essid=ssid,
            password=password,
            channel=channel,
            hidden=hidden,
            authmode=authmode,
        )
        return True
    except Exception:
        try:
            ap.config(
                ssid=ssid,
                password=password,
                channel=channel,
                hidden=hidden,
                authmode=authmode,
            )
            return True
        except Exception:
            return False


# 設定開放 AP 參數
def _ap_config_open(ap, ssid, channel, hidden):
    try:
        ap.config(
            essid=ssid,
            channel=channel,
            hidden=hidden,
            authmode=network.AUTH_OPEN,
        )
    except Exception:
        ap.config(
            ssid=ssid,
            channel=channel,
            hidden=hidden,
            authmode=network.AUTH_OPEN,
        )


# 啟動 AP 模式供設定用
def start_ap(cfg, log_fn=None):
    wifi_cfg = cfg["wifi"]
    ap_cfg = wifi_cfg.get("ap", {})
    ssid = ap_cfg.get("ssid") or "ESP32-SETUP"
    password = ap_cfg.get("password", "")
    channel = ap_cfg.get("channel", 6)
    hidden = bool(ap_cfg.get("hidden", False))
    force_open = bool(ap_cfg.get("force_open", False))
    ifcfg = ap_cfg.get("ifcfg")

    sta = network.WLAN(network.STA_IF)
    sta.active(False)

    ap = network.WLAN(network.AP_IF)
    ap.active(False)
    time.sleep(0.2)
    ap.active(True)
    for _ in range(10):
        if ap.active():
            break
        time.sleep(0.2)

    if force_open or not password or len(password) < 8:
        authmode = network.AUTH_OPEN
        _ap_config_open(ap, ssid, channel, hidden)
    else:
        auth_candidates = []
        if hasattr(network, "AUTH_WPA_WPA2_PSK"):
            auth_candidates.append(network.AUTH_WPA_WPA2_PSK)
        if hasattr(network, "AUTH_WPA2_PSK"):
            auth_candidates.append(network.AUTH_WPA2_PSK)
        if not auth_candidates:
            auth_candidates.append(network.AUTH_OPEN)

        configured = False
        authmode = network.AUTH_OPEN
        for candidate in auth_candidates:
            if _ap_config_secure(ap, ssid, password, channel, hidden, candidate):
                authmode = candidate
                configured = True
                break

        if not configured:
            authmode = network.AUTH_OPEN
            _ap_config_open(ap, ssid, channel, hidden)

    ap.active(True)
    time.sleep(0.2)

    if ifcfg:
        ap.ifconfig(tuple(ifcfg))

    if log_fn:
        try:
            essid = ap.config("essid")
        except Exception:
            essid = ap.config("ssid")
        log_fn(
            "AP started: {} (ssid={}, channel={}, hidden={}, active={}, authmode={}, pwd_len={}, force_open={})".format(
                ap.ifconfig()[0],
                essid,
                channel,
                hidden,
                ap.active(),
                authmode,
                len(password or ""),
                force_open,
            )
        )
    print("AP started:", ap.ifconfig())
    return ap


# 嘗試使用指定帳密連線 Wi-Fi
def connect_wifi_with_credentials(
    ssid, password, use_static_ip, static_ifcfg, max_attempts=1, log_fn=None
):
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        if use_static_ip:
            wlan.ifconfig(tuple(static_ifcfg))
        wlan.disconnect()
        time.sleep(0.5)

        print("Connecting to {}...".format(ssid))
        if log_fn:
            log_fn("Connecting to WiFi: {}".format(ssid))
        wlan.connect(ssid, password)

        t0 = time.ticks_ms()
        while not wlan.isconnected() and time.ticks_diff(time.ticks_ms(), t0) < 15000:
            print(".", end="")
            time.sleep(0.5)

        if wlan.isconnected():
            print("\nWiFi connected to {}: {}".format(ssid, wlan.ifconfig()))
            if log_fn:
                log_fn("WiFi connected: {}".format(ssid))
            return True
        print("\nFailed to connect to {}".format(ssid))
        if log_fn:
            log_fn("WiFi connect failed: {}".format(ssid))
        return False
    except Exception as e:
        print("\nConnection error: {}".format(e))
        if log_fn:
            log_fn("WiFi connect error: {}".format(e))
        return False


# 交替嘗試主備 Wi-Fi 直到連線成功
def connect_wifi(cfg, set_led_color, log_fn=None):
    wifi_failures = 0
    connection_attempts = 0

    wifi_cfg = cfg["wifi"]
    primary_cfg = wifi_cfg["primary"]
    backup_cfg = wifi_cfg["backup"]
    primary_ok = _ssid_valid(primary_cfg.get("ssid", ""))
    backup_ok = _ssid_valid(backup_cfg.get("ssid", ""))

    if not primary_ok and not backup_ok:
        print("No WiFi SSID set, starting AP mode...")
        if log_fn:
            log_fn("No SSID, switching to AP mode")
        start_ap(cfg, log_fn=log_fn)
        return "ap"

    use_primary = True if primary_ok else False

    while True:
        connection_attempts += 1

        if connection_attempts > wifi_cfg["max_connection_attempts"]:
            print("Too many connection attempts, performing soft reset...")
            set_led_color(10, 10, 0)
            time.sleep(2)
            machine.reset()

        if use_primary and primary_ok:
            print("Attempting primary WiFi ({})...".format(connection_attempts))
            if connect_wifi_with_credentials(
                primary_cfg["ssid"],
                primary_cfg["password"],
                wifi_cfg["use_static_ip"],
                wifi_cfg["static_ifcfg"],
                log_fn=log_fn,
            ):
                wifi_failures = 0
                return "sta"
            print("Primary WiFi failed")
        elif backup_ok:
            print("Attempting backup WiFi ({})...".format(connection_attempts))
            if connect_wifi_with_credentials(
                backup_cfg["ssid"],
                backup_cfg["password"],
                wifi_cfg["use_static_ip"],
                wifi_cfg["static_ifcfg"],
                log_fn=log_fn,
            ):
                wifi_failures = 0
                return "sta"
            print("Backup WiFi failed")
        else:
            print("No available WiFi credentials, starting AP mode...")
            if log_fn:
                log_fn("No SSID, switching to AP mode")
            start_ap(cfg, log_fn=log_fn)
            return "ap"

        wifi_failures += 1
        if primary_ok and backup_ok:
            use_primary = not use_primary

        if wifi_failures >= wifi_cfg["reset_after_failures"]:
            print(
                "WiFi failed {} times, performing soft reset...".format(wifi_failures)
            )
            set_led_color(10, 0, 10)
            time.sleep(2)
            machine.reset()

        print(
            "WiFi failed (failures: {}), retrying in 3 seconds...".format(
                wifi_failures
            )
        )
        set_led_color(10, 0, 0)
        time.sleep(3)
