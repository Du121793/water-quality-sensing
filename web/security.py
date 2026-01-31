import ubinascii
import uhashlib

try:
    import urandom as _urandom
except Exception:
    import random as _urandom


# 取得隨機位元組
def _rand_bytes(length):
    out = []
    for _ in range(length):
        try:
            out.append(_urandom.getrandbits(8))
        except Exception:
            out.append(_urandom.randrange(256))
    return bytes(out)


# 產生密碼雜湊
def _hash_password(password, salt_hex):
    salt = ubinascii.unhexlify(salt_hex.encode())
    h = uhashlib.sha256()
    h.update(salt)
    h.update(password.encode())
    return ubinascii.hexlify(h.digest()).decode()


# 取得隨機 Salt（Hex）
def _generate_salt_hex():
    return ubinascii.hexlify(_rand_bytes(16)).decode()
