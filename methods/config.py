import json


# 讀取設定檔
def load_config(path="config.json"):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


# 儲存設定檔
def save_config(data, path="config.json"):
    with open(path, "w") as f:
        json.dump(data, f)
