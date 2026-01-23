from machine import Pin
import neopixel

_np = None


# 初始化 LED 控制
def init_led(pin, num):
    global _np
    _np = neopixel.NeoPixel(Pin(pin), num)


# 設定 LED 顏色
def set_led_color(r, g, b):
    _np[0] = (r, g, b)
    _np.write()
