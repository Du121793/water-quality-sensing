import json


# 讀取校正資料
def load_cal(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


# 儲存校正資料
def save_cal(path, data):
    with open(path, "w") as f:
        json.dump(data, f)
