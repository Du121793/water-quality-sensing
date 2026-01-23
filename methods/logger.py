try:
    import uos as os
except Exception:
    import os

from .utils import get_date_iso


class Logger:
    # 初始化記錄器
    def __init__(self, cfg):
        self._cfg = cfg
        self._enabled = False
        self._file = "logs.txt"
        self._max_lines = 30000
        self._view_lines = 200
        self._view_max_chars = 4096
        self._timezone_offset_s = 0
        self._line_count = None
        self.refresh()

    # 重新讀取設定
    def refresh(self):
        log_cfg = self._cfg.get("log", {})
        self._enabled = bool(log_cfg.get("enabled", True))
        self._file = log_cfg.get("file", "logs.txt")
        self._max_lines = int(log_cfg.get("max_lines", 30000))
        self._view_lines = int(log_cfg.get("view_lines", 200))
        self._view_max_chars = int(log_cfg.get("view_max_chars", 4096))
        self._timezone_offset_s = int(
            self._cfg.get("time", {}).get("timezone_offset_s", 0)
        )

    # 計算檔案行數
    def _count_lines(self):
        try:
            with open(self._file, "r") as f:
                count = 0
                for _ in f:
                    count += 1
            return count
        except Exception:
            return 0

    # 裁切檔案只保留最後幾行
    def _trim_lines(self):
        count = self._count_lines()
        if count <= self._max_lines:
            self._line_count = count
            return

        skip = count - self._max_lines
        tmp_file = self._file + ".tmp"
        try:
            with open(self._file, "r") as src, open(tmp_file, "w") as dst:
                idx = 0
                for line in src:
                    idx += 1
                    if idx <= skip:
                        continue
                    dst.write(line)
            try:
                os.remove(self._file)
            except Exception:
                pass
            os.rename(tmp_file, self._file)
            self._line_count = self._max_lines
        except Exception:
            self._line_count = None

    # 寫入一行紀錄
    def log(self, message):
        if not self._enabled:
            return
        line = "{} {}\n".format(get_date_iso(self._timezone_offset_s), message)
        try:
            with open(self._file, "a") as f:
                f.write(line)
        except Exception:
            return

        if self._line_count is None:
            self._line_count = self._count_lines()
        else:
            self._line_count += 1

        if self._line_count > self._max_lines:
            self._trim_lines()

    # 讀取最後幾行記錄
    def read_tail(self, lines=None):
        if lines is None:
            lines = self._view_lines
        lines = max(1, int(lines))
        max_chars = max(0, int(self._view_max_chars))
        buffer = []
        total_len = 0
        try:
            with open(self._file, "r") as f:
                for line in f:
                    text = line.rstrip()
                    buffer.append(text)
                    total_len += len(text) + 1
                    while buffer and (
                        len(buffer) > lines
                        or (max_chars and total_len > max_chars)
                    ):
                        removed = buffer.pop(0)
                        total_len -= len(removed) + 1
        except Exception:
            return []
        return buffer

    # 清除記錄檔
    def clear(self):
        try:
            with open(self._file, "w") as f:
                f.write("")
        except Exception:
            pass
        self._line_count = 0

    # 取得顯示行數
    def get_view_lines(self):
        return self._view_lines
