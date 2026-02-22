import json
try:
    import uos as os
except Exception:
    import os


# 讀取設定檔
def load_config(path="config.json"):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


# 儲存設定檔
def save_config(data, path="config.json"):
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f)
    try:
        try:
            os.rename(tmp_path, path)
        except Exception:
            try:
                os.remove(path)
            except Exception:
                pass
            os.rename(tmp_path, path)
    except Exception:
        # Best-effort cleanup if rename fails
        try:
            os.remove(tmp_path)
        except Exception:
            pass
