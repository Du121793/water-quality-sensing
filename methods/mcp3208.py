# MCP3208 SPI ADC 驅動
class MCP3208:
    # 初始化 MCP3208 物件
    def __init__(self, spi, cs_pin):
        self._spi = spi
        self._cs = cs_pin
        self._cs.value(1)

    # 讀取指定通道（0-7）
    def read(self, channel):
        ch = int(channel) & 0x07
        tx = bytearray(3)
        rx = bytearray(3)
        tx[0] = 0x06 | (ch >> 2)
        tx[1] = (ch & 0x03) << 6
        tx[2] = 0x00
        self._cs.value(0)
        self._spi.write_readinto(tx, rx)
        self._cs.value(1)
        return ((rx[1] & 0x0F) << 8) | rx[2]


# MCP3208 通道包裝成 ADC 介面
class MCP3208ADC:
    # 初始化 MCP3208ADC 物件
    def __init__(self, mcp, channel):
        self._mcp = mcp
        self._channel = channel

    # 讀取通道數值（0-4095）
    def read(self):
        return self._mcp.read(self._channel)
